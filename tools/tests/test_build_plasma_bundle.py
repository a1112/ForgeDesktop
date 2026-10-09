"""KWin/Plasma candidate artifact contract and rejection behavior."""

import hashlib
import json
import os
from pathlib import Path
import re
import shutil
import subprocess
import sys
import tempfile
import unittest

from tools.build_plasma_bundle import (create_bundle, eligible_path,
                                       validate_window_assets, verify_bundle)


SESSION = (b"#!/bin/sh\nset -eu\n"
           b'[ "$(/usr/bin/id -u)" -ne 0 ] || exit 1\n'
           b"export QT_QUICK_BACKEND=software\n"
           b"export XMODIFIERS=@im=fcitx\n"
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
                b'"runtimePackages":["fcitx5","fcitx5-chinese-addons","fcitx5-gtk","fcitx5-qt","kwin","plasma-workspace"],'
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

    def test_compatforge_sync_bundle_is_closed_and_preserves_executable_mode(self):
        root = Path(__file__).resolve().parents[2]
        assets = {
            "usr/libexec/forge-desktop/forge_provider_contract.py": (root / "tools/forge_provider_contract.py", 0o644),
            "usr/libexec/forge-desktop/compatforge-provider-lock-v1.json": (root / "tools/compatforge-provider-lock-v1.json", 0o644),
            "usr/libexec/forge-desktop/compatforge-desktop-sync": (root / "tools/compatforge_desktop.py", 0o755),
            "usr/lib/systemd/user/forge-compatforge-desktop-sync.service": (root / "services/compatforge/forge-compatforge-desktop-sync.service", 0o644),
            "usr/lib/systemd/user/forge-compatforge-desktop-sync.timer": (root / "services/compatforge/forge-compatforge-desktop-sync.timer", 0o644),
        }
        for name, (source, mode) in assets.items():
            self.assertTrue(eligible_path(name))
            path = self.stage / name
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_bytes(source.read_bytes().replace(b"\r\n", b"\n"))
            path.chmod(mode)
        inventory = self.stage / "usr/share/forge-desktop/plasma/dependencies.json"
        value = json.loads(inventory.read_bytes())
        value["runtimePackages"] = ["desktop-file-utils", "fcitx5", "fcitx5-chinese-addons", "fcitx5-gtk", "fcitx5-qt", "kwin", "plasma-workspace", "python"]
        value["assetLicenses"] = {name: "MIT" for name in assets}
        inventory.write_text(json.dumps(value), encoding="utf-8")
        receipt = verify_bundle(self.output, self.build())
        self.assertEqual(receipt["files"]["usr/libexec/forge-desktop/compatforge-desktop-sync"]["mode"], 0o755)

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

    def test_provider_adapter_and_mandatory_lock_cannot_be_omitted_from_bundle(self):
        from tools.build_plasma_bundle import stage_repository_assets, COMPAT_LOCK
        repo = Path(__file__).resolve().parents[2]
        full_stage = self.root / "contract-stage"
        stage_repository_assets(repo, full_stage)
        lock = full_stage / COMPAT_LOCK
        original = lock.read_bytes()
        lock.unlink()
        with self.assertRaisesRegex(ValueError, "incomplete CompatForge|asset license records"):
            create_bundle(full_stage, self.output, "0.1.0", "a" * 40)
        value = json.loads(original)
        value["commands"] = {}
        lock.write_text(json.dumps(value))
        lock.chmod(0o644)
        with self.assertRaisesRegex(ValueError, "mandatory provider requirements"):
            create_bundle(full_stage, self.output, "0.1.0", "a" * 40)
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
        self.assertIn(b"export XMODIFIERS=@im=fcitx\n",
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
            destination.chmod(0o644)
        dependencies = self.stage / "usr/share/forge-desktop/plasma/dependencies.json"
        visual_inventory = json.loads((repo / "plasma/dependencies.json").read_bytes())
        declared = visual_inventory["assetLicenses"]
        self.assertTrue(set(visual_files.values()) <= set(declared))
        visual_inventory["assetLicenses"] = {
            key: declared[key] for key in visual_files.values()}
        dependencies.write_text(json.dumps(visual_inventory))
        pin = self.build()
        self.assertEqual(set(verify_bundle(self.output, pin)["files"]),
                         set(self.files) | set(visual_files.values()))
        defaults = (self.output / visual_files[
            "plasma/look-and-feel/contents/defaults"]).read_text()
        self.assertIn("[kwinrc][Wayland]\n"
                      "InputMethod[$e]=/usr/share/applications/org.fcitx.Fcitx5.desktop\n",
                      defaults)
        self.assertTrue({"fcitx5", "fcitx5-chinese-addons", "fcitx5-gtk", "fcitx5-qt"}
                        <= set(visual_inventory["runtimePackages"]))
        kde_group = re.search(r"(?ms)^\[kdeglobals\]\[KDE\]\n(.*?)(?=^\[|\Z)", defaults)
        self.assertIsNotNone(kde_group)
        factor = re.search(r"(?m)^AnimationDurationFactor=([0-9.]+)$",
                           kde_group.group(1))
        self.assertIsNotNone(factor)
        self.assertGreater(float(factor.group(1)), 0)
        self.assertLessEqual(float(factor.group(1)), 0.5)
        layout = (self.output / visual_files[
            "plasma/look-and-feel/contents/layouts/org.kde.plasma.desktop-layout.js"])
        layout_bytes = layout.read_bytes()
        self.assertIn(b'dock.lengthMode = "custom";', layout_bytes)
        for desktop_id in (b'thunar.desktop', b'xfce4-terminal.desktop',
                           b'org.xfce.mousepad.desktop', b'firefox.desktop',
                           b'systemsettings.desktop'):
            self.assertIn(b'applications:' + desktop_id, layout_bytes)

    def test_visual_theme_rejects_other_virtual_keyboard_and_missing_ime(self):
        repo = Path(__file__).resolve().parents[2]
        root = self.stage / "usr/share/plasma/look-and-feel/org.forge.desktop"
        for source in (repo / "plasma/look-and-feel").rglob("*"):
            if source.is_file():
                target = root / source.relative_to(repo / "plasma/look-and-feel")
                target.parent.mkdir(parents=True, exist_ok=True)
                shutil.copyfile(source, target)
                target.chmod(0o644)
        dep = self.stage / "usr/share/forge-desktop/plasma/dependencies.json"
        dep.write_bytes((repo / "plasma/dependencies.json").read_bytes())
        defaults = root / "contents/defaults"
        original = defaults.read_text()
        defaults.write_text(original.replace("org.fcitx.Fcitx5.desktop",
                                             "other.desktop"))
        with self.assertRaises(ValueError):
            self.build()
        defaults.write_text(original)
        inventory = json.loads(dep.read_text())
        inventory["runtimePackages"].remove("fcitx5-chinese-addons")
        dep.write_text(json.dumps(inventory))
        with self.assertRaises(ValueError):
            self.build()

    def test_window_control_assets_are_closed_and_licensed(self):
        repo = Path(__file__).resolve().parents[2]
        assets = {
            "plasma/aurorae/ForgeDark/metadata.desktop":
                "usr/share/aurorae/themes/ForgeDark/metadata.desktop",
            "plasma/aurorae/ForgeDark/ForgeDarkrc":
                "usr/share/aurorae/themes/ForgeDark/ForgeDarkrc",
            **{f"plasma/aurorae/ForgeDark/{name}.svg":
               f"usr/share/aurorae/themes/ForgeDark/{name}.svg"
               for name in ("decoration", "minimize", "maximize", "restore", "close")},
            "plasma/plasmoids/org.forge.windowcontrols/metadata.json":
                "usr/share/plasma/plasmoids/org.forge.windowcontrols/metadata.json",
            "plasma/plasmoids/org.forge.windowcontrols/contents/ui/main.qml":
                "usr/share/plasma/plasmoids/org.forge.windowcontrols/contents/ui/main.qml",
            "plasma/plasmoids/org.forge.windowcontrols/contents/locale/zh_CN/LC_MESSAGES/plasma_applet_org.forge.windowcontrols.mo":
                "usr/share/plasma/plasmoids/org.forge.windowcontrols/contents/locale/zh_CN/LC_MESSAGES/plasma_applet_org.forge.windowcontrols.mo",
        }
        for source, destination in assets.items():
            with self.subTest(source=source):
                self.assertTrue((repo / source).is_file())
                self.assertTrue(eligible_path(destination))
                path = self.stage / destination
                path.parent.mkdir(parents=True, exist_ok=True)
                shutil.copyfile(repo / source, path)
                path.chmod(0o644)
        shutil.copyfile(repo / "plasma/dependencies.json",
                        self.stage / "usr/share/forge-desktop/plasma/dependencies.json")
        for source, destination, mode in (
            ("tools/compatforge_desktop.py", "usr/libexec/forge-desktop/compatforge-desktop-sync", 0o755),
            ("tools/forge_provider_contract.py", "usr/libexec/forge-desktop/forge_provider_contract.py", 0o644),
            ("tools/compatforge-provider-lock-v1.json", "usr/libexec/forge-desktop/compatforge-provider-lock-v1.json", 0o644),
            ("services/compatforge/forge-compatforge-desktop-sync.service", "usr/lib/systemd/user/forge-compatforge-desktop-sync.service", 0o644),
            ("services/compatforge/forge-compatforge-desktop-sync.timer", "usr/lib/systemd/user/forge-compatforge-desktop-sync.timer", 0o644),
        ):
            destination = self.stage / destination
            destination.parent.mkdir(parents=True, exist_ok=True)
            destination.write_bytes((repo / source).read_bytes().replace(b"\r\n", b"\n"))
            destination.chmod(mode)
        # The reviewed product bundle includes both the look-and-feel and
        # window-control assets, so stage the complete visual package.
        look_root = repo / "plasma/look-and-feel"
        for source in look_root.rglob("*"):
            if source.is_file():
                destination = (self.stage / "usr/share/plasma/look-and-feel/org.forge.desktop"
                               / source.relative_to(look_root))
                destination.parent.mkdir(parents=True, exist_ok=True)
                shutil.copyfile(source, destination)
                destination.chmod(0o644)
        declared = json.loads((repo / "plasma/dependencies.json").read_bytes())[
            "assetLicenses"]
        self.assertTrue(set(assets.values()) <= set(declared))
        pin = self.build()
        self.assertTrue(set(assets.values()) <= set(verify_bundle(self.output, pin)["files"]))

    def test_fusion_widget_controls_only_current_eligible_task(self):
        repo = Path(__file__).resolve().parents[2]
        qml = (repo / "plasma/plasmoids/org.forge.windowcontrols/contents/ui/main.qml")
        self.assertTrue(qml.is_file())
        source = qml.read_text()
        for role in ("IsWindow", "IsActive", "IsMaximized", "IsFullScreen",
                     "IsMinimized", "IsClosable", "IsMinimizable",
                     "IsMaximizable", "CanSetNoBorder", "HasNoBorder"):
            self.assertIn("TaskManager.AbstractTasksModel." + role, source)
        self.assertIn("tasks.activeTask", source)
        self.assertIn("function actOnActiveTask", source)
        self.assertIn("if (!eligible(index))", source)
        self.assertNotRegex(source, r"\b(?:Process|DBus|openUrlExternally|eval)\b")

    def test_fusion_widget_draws_controls_in_panel_item(self):
        # A compactRepresentation is not instantiated in the fixed-width
        # panel applet on the pinned Plasma runtime. Keep the controls as
        # visual children of the PlasmoidItem and give their glyphs a color.
        repo = Path(__file__).resolve().parents[2]
        source = (repo / "plasma/plasmoids/org.forge.windowcontrols/contents/ui/main.qml"
                  ).read_text()
        self.assertNotIn("compactRepresentation:", source)
        self.assertIn("RowLayout {", source)
        self.assertEqual(source.count('color: "#e6edf5"'), 3)

    def test_fusion_excludes_verified_client_decorated_firefox(self):
        repo = Path(__file__).resolve().parents[2]
        source = (repo / "plasma/plasmoids/org.forge.windowcontrols/contents/ui/main.qml"
                  ).read_text()
        self.assertIn("TaskManager.AbstractTasksModel.AppId", source)
        self.assertIn('"firefox.desktop"', source)
        self.assertIn("!clientDecorated(index)", source)

    def test_window_assets_reject_missing_external_and_wrong_metadata(self):
        repo = Path(__file__).resolve().parents[2]
        roots = (
            (repo / "plasma/aurorae/ForgeDark", "usr/share/aurorae/themes/ForgeDark/"),
            (repo / "plasma/plasmoids/org.forge.windowcontrols",
             "usr/share/plasma/plasmoids/org.forge.windowcontrols/"),
        )
        payloads = {}
        for source_root, destination_root in roots:
            for source in source_root.rglob("*"):
                if source.is_file():
                    payloads[destination_root + source.relative_to(source_root).as_posix()
                             ] = (source.read_bytes(), 0o644)
        validate_window_assets(payloads)
        close = "usr/share/aurorae/themes/ForgeDark/close.svg"
        metadata = "usr/share/plasma/plasmoids/org.forge.windowcontrols/metadata.json"
        variants = []
        missing = dict(payloads)
        missing.pop(close)
        variants.append(missing)
        external = dict(payloads)
        external[close] = (payloads[close][0].replace(
            b'fill="#1c2535"', b'fill="url(http://example.invalid/a)"', 1), 0o644)
        variants.append(external)
        wrong_id = dict(payloads)
        wrong_id[metadata] = (payloads[metadata][0].replace(
            b'"org.forge.windowcontrols"', b'"other"'), 0o644)
        variants.append(wrong_id)
        catalogue = ("usr/share/plasma/plasmoids/org.forge.windowcontrols/contents/"
                     "locale/zh_CN/LC_MESSAGES/plasma_applet_org.forge.windowcontrols.mo")
        missing_catalogue = dict(payloads)
        missing_catalogue.pop(catalogue)
        variants.append(missing_catalogue)
        for data in (b"\xde\x12\x04\x95", payloads[catalogue][0].replace(
                "当前窗口：%1".encode(), "当前窗口：%2".encode())):
            invalid_catalogue = dict(payloads)
            invalid_catalogue[catalogue] = (data, 0o644)
            variants.append(invalid_catalogue)
        for variant in variants:
            with self.subTest(variant=len(variant), digest=hashlib.sha256(
                    b"".join(value[0] for value in variant.values())).hexdigest()[:8]):
                with self.assertRaises(ValueError):
                    validate_window_assets(variant)

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
