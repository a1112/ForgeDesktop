"""KWin/Plasma candidate artifact contract and rejection behavior."""

import hashlib
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
import unittest

from tools.build_plasma_bundle import create_bundle, eligible_path, verify_bundle


SESSION = (b"#!/bin/sh\nset -eu\n"
           b'[ "$(/usr/bin/id -u)" -ne 0 ] || exit 1\n'
           b"export QT_QUICK_BACKEND=software\n"
           b"exec /usr/lib/plasma-dbus-run-session-if-needed "
           b"/usr/bin/startplasma-wayland\n")
ENTRY = (b"[Desktop Entry]\nName=ForgeDesktop (KWin)\n"
         b"Comment=ForgeOS KWin and Plasma Wayland candidate\n"
         b"Exec=/usr/libexec/forge-desktop/forge-kwin-session\n"
         b"TryExec=/usr/bin/startplasma-wayland\n"
         b"Type=Application\nDesktopNames=KDE;ForgeDesktop;\n")


class PlasmaBundleTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.stage = self.root / "stage"
        self.output = self.root / "bundle"
        self.files = {
            "usr/libexec/forge-desktop/forge-kwin-session": (SESSION, 0o755),
            "usr/share/wayland-sessions/forgedesktop-kwin.desktop": (ENTRY, 0o644),
            "usr/share/forge-desktop/plasma/dependencies.json": (
                b'{"schemaVersion":1,"archSnapshot":"2026/08/01",'
                b'"runtimePackages":["kwin","plasma-workspace"],'
                b'"assetLicenses":{}}\n', 0o644),
            "usr/share/licenses/forge-desktop/LICENSE": (b"MIT fixture\n", 0o644),
        }
        for relative, (data, mode) in self.files.items():
            target = self.stage / relative
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_bytes(data)
            target.chmod(mode)

    def build(self):
        return create_bundle(self.stage, self.output, "0.1.0", "a" * 40)

    def test_canonical_receipt_and_verified_files(self):
        pin = self.build()
        raw = (self.output / "bundle.json").read_bytes()
        self.assertEqual(pin, hashlib.sha256(raw).hexdigest())
        receipt = json.loads(raw)
        self.assertEqual(receipt["kind"], "plasma-session")
        self.assertEqual(receipt["archSnapshot"], "2026/08/01")
        self.assertEqual(receipt["sourceCommit"], "a" * 40)
        self.assertEqual(set(receipt["files"]), set(self.files))
        self.assertEqual(verify_bundle(self.output, pin), receipt)
        self.assertEqual(raw, (json.dumps(receipt, sort_keys=True,
                                          separators=(",", ":")) + "\n").encode())

    def test_rejects_unlisted_system_path_and_traversal(self):
        for path in ("etc/lightdm/lightdm.conf", "usr/share/plasma/../other",
                     "/usr/share/plasma/look-and-feel/x", "usr/share/kwin/scripts/x"):
            with self.subTest(path=path):
                self.assertFalse(eligible_path(path))
        extra = self.stage / "etc/lightdm/lightdm.conf"
        extra.parent.mkdir(parents=True)
        extra.write_text("user-session=forgedesktop-kwin")
        with self.assertRaises(ValueError):
            self.build()
        self.assertFalse(self.output.exists())

    def test_rejects_substituted_login_command_and_shell_body(self):
        entry = self.stage / "usr/share/wayland-sessions/forgedesktop-kwin.desktop"
        entry.write_bytes(ENTRY.replace(b"forge-kwin-session", b"other-session"))
        with self.assertRaises(ValueError):
            self.build()
        entry.write_bytes(ENTRY)
        script = self.stage / "usr/libexec/forge-desktop/forge-kwin-session"
        script.write_bytes(SESSION + b"/usr/bin/sh -c 'danger'\n")
        with self.assertRaises(ValueError):
            self.build()
        self.assertFalse(self.output.exists())

    def test_rejects_configparser_defaults_as_session_fields(self):
        entry = self.stage / "usr/share/wayland-sessions/forgedesktop-kwin.desktop"
        entry.write_bytes(ENTRY.replace(b"[Desktop Entry]", b"[DEFAULT]")
                          + b"[Desktop Entry]\n")
        with self.assertRaises(ValueError):
            self.build()

    def test_rejects_symlink_and_hardlink(self):
        script = self.stage / "usr/libexec/forge-desktop/forge-kwin-session"
        outside = self.root / "outside"
        outside.write_bytes(SESSION)
        script.unlink()
        try:
            script.symlink_to(outside)
        except OSError:
            self.skipTest("symlinks unavailable")
        with self.assertRaises(ValueError):
            self.build()
        script.unlink()
        os.link(outside, script)
        with self.assertRaises(ValueError):
            self.build()

    def test_rejects_missing_license_and_wrong_snapshot(self):
        license_file = self.stage / "usr/share/licenses/forge-desktop/LICENSE"
        license_file.unlink()
        with self.assertRaises(ValueError):
            self.build()
        license_file.write_bytes(b"MIT fixture\n")
        dependencies = self.stage / "usr/share/forge-desktop/plasma/dependencies.json"
        dependencies.write_text('{"schemaVersion":1,"archSnapshot":"latest"}')
        with self.assertRaises(ValueError):
            self.build()

    def test_requires_explicit_runtime_and_asset_license_records(self):
        # The producer must not publish an inventory with no named upstream
        # runtime or with no asset-license declaration.
        dependencies = self.stage / "usr/share/forge-desktop/plasma/dependencies.json"
        dependencies.write_text('{"schemaVersion":1,"archSnapshot":"2026/08/01"}')
        with self.assertRaises(ValueError):
            self.build()

    def test_detects_changed_payload_and_receipt(self):
        pin = self.build()
        script = self.output / "usr/libexec/forge-desktop/forge-kwin-session"
        script.write_bytes(script.read_bytes() + b"# changed\n")
        with self.assertRaises(ValueError):
            verify_bundle(self.output, pin)
        script.write_bytes(SESSION)
        receipt = self.output / "bundle.json"
        receipt.write_bytes(receipt.read_bytes() + b" ")
        with self.assertRaises(ValueError):
            verify_bundle(self.output, pin)

    def test_detects_duplicate_manifest_key_and_extra_output_file(self):
        pin = self.build()
        receipt = self.output / "bundle.json"
        original = receipt.read_bytes()
        raw = original.replace(b'"kind":"plasma-session"',
                                           b'"kind":"plasma-session","kind":"plasma-session"')
        receipt.write_bytes(raw)
        with self.assertRaises(ValueError):
            verify_bundle(self.output, hashlib.sha256(raw).hexdigest())
        receipt.write_bytes(original)
        self.output.joinpath("extra").write_text("unexpected")
        with self.assertRaises(ValueError):
            verify_bundle(self.output, pin)

    def test_rejects_hardlinked_receipt(self):
        pin = self.build()
        receipt = self.output / "bundle.json"
        external = self.root / "external-receipt"
        receipt.replace(external)
        os.link(external, receipt)
        with self.assertRaises(ValueError):
            verify_bundle(self.output, pin)

    def test_existing_output_is_never_replaced(self):
        self.output.mkdir()
        marker = self.output / "marker"
        marker.write_text("keep")
        with self.assertRaises(FileExistsError):
            self.build()
        self.assertEqual(marker.read_text(), "keep")

    def test_repository_session_files_build_as_reviewed(self):
        repo = Path(__file__).resolve().parents[2]
        self.assertIn(b"export QT_QUICK_BACKEND=software\n",
                      (repo / "plasma/session/forge-kwin-session").read_bytes())
        for source, relative in (
            ("plasma/session/forge-kwin-session",
             "usr/libexec/forge-desktop/forge-kwin-session"),
            ("plasma/session/forgedesktop-kwin.desktop",
             "usr/share/wayland-sessions/forgedesktop-kwin.desktop"),
        ):
            shutil.copyfile(repo / source, self.stage / relative)
        shutil.copyfile(repo / "LICENSE-MIT",
                        self.stage / "usr/share/licenses/forge-desktop/LICENSE")
        pin = self.build()
        self.assertEqual(verify_bundle(self.output, pin)["kind"], "plasma-session")

    def test_repository_visual_theme_is_bundled_with_license_records(self):
        repo = Path(__file__).resolve().parents[2]
        visual_files = {
            "plasma/look-and-feel/metadata.json":
                "usr/share/plasma/look-and-feel/org.forge.desktop/metadata.json",
            "plasma/look-and-feel/contents/defaults":
                "usr/share/plasma/look-and-feel/org.forge.desktop/contents/defaults",
            "plasma/look-and-feel/contents/layouts/org.kde.plasma.desktop-layout.js":
                "usr/share/plasma/look-and-feel/org.forge.desktop/contents/layouts/org.kde.plasma.desktop-layout.js",
            "plasma/look-and-feel/contents/wallpapers/forge.svg":
                "usr/share/plasma/look-and-feel/org.forge.desktop/contents/wallpapers/forge.svg",
        }
        for source, relative in visual_files.items():
            destination = self.stage / relative
            destination.parent.mkdir(parents=True, exist_ok=True)
            shutil.copyfile(repo / source, destination)
        dependencies = self.stage / "usr/share/forge-desktop/plasma/dependencies.json"
        shutil.copyfile(repo / "plasma/dependencies.json", dependencies)
        declared = json.loads(dependencies.read_bytes())["assetLicenses"]
        self.assertEqual(set(declared), set(visual_files.values()))
        pin = self.build()
        self.assertEqual(set(verify_bundle(self.output, pin)["files"]),
                         set(self.files) | set(visual_files.values()))
        layout = (self.output / visual_files[
            "plasma/look-and-feel/contents/layouts/org.kde.plasma.desktop-layout.js"])
        layout_bytes = layout.read_bytes()
        self.assertIn(b'dock.lengthMode = "custom";', layout_bytes)
        for desktop_id in (b'thunar.desktop', b'xfce4-terminal.desktop',
                           b'org.xfce.mousepad.desktop', b'firefox.desktop',
                           b'systemsettings.desktop'):
            self.assertIn(b'applications:' + desktop_id, layout_bytes)

    def test_rejects_private_window_api_in_theme_layout(self):
        relative = ("usr/share/plasma/look-and-feel/org.forge.desktop/contents/"
                    "layouts/org.kde.plasma.desktop-layout.js")
        layout = self.stage / relative
        layout.parent.mkdir(parents=True, exist_ok=True)
        layout.write_text("import WindowHeap from 'private';\n")
        dependencies = self.stage / "usr/share/forge-desktop/plasma/dependencies.json"
        record = json.loads(dependencies.read_bytes())
        record["assetLicenses"] = {relative: "MIT"}
        dependencies.write_text(json.dumps(record))
        with self.assertRaises(ValueError):
            self.build()

    def test_documented_direct_cli_starts(self):
        repo = Path(__file__).resolve().parents[2]
        result = subprocess.run([sys.executable,
                                 str(repo / "tools/build_plasma_bundle.py"), "--help"],
                                cwd=repo, capture_output=True, text=True, check=False)
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn("--staging", result.stdout)


if __name__ == "__main__":
    unittest.main()
