"""Release bundle producer contract, including the ForgeOS consumer shape."""

import hashlib
import json
import os
from pathlib import Path
import tempfile
import unittest

from tools.build_bundle import create_bundle, eligible_path


ELF = b"\x7fELF\x02\x01\x01" + bytes(9) + b"\x03\x00\x3e\x00" + bytes(44)


class BundleProducerTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.stage = self.root / "stage"
        self.output = self.root / "bundle"
        self.files = {
            "usr/bin/forge-compositor": (ELF, 0o755),
            "usr/libexec/forge-desktop/forge-shell": (ELF, 0o755),
            "usr/libexec/forge-desktop/forge-notificationd": (ELF, 0o755),
            "usr/libexec/forge-desktop/forge-session": (
                b"#!/bin/sh\nexec /usr/bin/forge-compositor\n", 0o755),
            "usr/share/wayland-sessions/forgedesktop.desktop": (
                b"[Desktop Entry]\nName=ForgeDesktop\n"
                b"Exec=/usr/libexec/forge-desktop/forge-session\n"
                b"TryExec=/usr/bin/forge-compositor\nType=Application\n"
                b"DesktopNames=ForgeDesktop\n", 0o644),
            "usr/share/forge-desktop/dependencies.json": (
                b'{"schemaVersion":1,"archSnapshot":"2026/08/01"}', 0o644),
            "usr/share/licenses/forge-desktop/LICENSE": (b"MIT license test fixture\n", 0o644),
        }
        for relative, (data, mode) in self.files.items():
            path = self.stage / relative
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_bytes(data)
            path.chmod(mode)

    def build(self):
        return create_bundle(self.stage, self.output, "0.1.0", "a" * 40)

    def test_produces_canonical_pinned_bundle(self):
        pin = self.build()
        raw = (self.output / "bundle.json").read_bytes()
        self.assertEqual(pin, hashlib.sha256(raw).hexdigest())
        receipt = json.loads(raw)
        self.assertEqual(set(receipt), {"schemaVersion", "target", "version",
                                        "sourceCommit", "archSnapshot", "files"})
        self.assertEqual(receipt["target"], "x86_64-linux-gnu")
        self.assertEqual(receipt["archSnapshot"], "2026/08/01")
        for relative, (data, mode) in self.files.items():
            self.assertEqual((self.output / relative).read_bytes(), data)
            self.assertEqual(receipt["files"][relative], {
                "sha256": hashlib.sha256(data).hexdigest(), "size": len(data),
                "mode": mode})
        self.assertEqual(raw, json.dumps(receipt, sort_keys=True,
                                         separators=(",", ":")).encode() + b"\n")

    def test_rejects_unexpected_file_without_publishing(self):
        extra = self.stage / "etc/lightdm/lightdm.conf"
        extra.parent.mkdir(parents=True)
        extra.write_text("user-session=forgedesktop")
        with self.assertRaises(ValueError):
            self.build()
        self.assertFalse(self.output.exists())

    def test_rejects_consumer_reserved_and_oversize_paths(self):
        for name in ("usr/share/forge-desktop/bundle.json",
                     "usr/share/forge-desktop/bundle.json/extra",
                     "usr/share/forge-desktop/" + "a" * 513):
            with self.subTest(name=name):
                self.assertFalse(eligible_path(name))

    def test_rejects_symlink_and_hardlink(self):
        target = self.stage / "usr/bin/forge-compositor"
        outside = self.root / "outside"
        outside.write_bytes(ELF)
        target.unlink()
        try:
            target.symlink_to(outside)
        except OSError:
            self.skipTest("symlinks unavailable")
        with self.assertRaises(ValueError):
            self.build()
        self.assertFalse(self.output.exists())
        target.unlink()
        os.link(outside, target)
        with self.assertRaises(ValueError):
            self.build()
        self.assertFalse(self.output.exists())

    def test_rejects_invalid_metadata_and_mode(self):
        dependencies = self.stage / "usr/share/forge-desktop/dependencies.json"
        dependencies.write_text("{}")
        with self.assertRaises(ValueError):
            self.build()
        dependencies.write_text('{"schemaVersion":1,"archSnapshot":"2026/08/01"}')
        compositor = self.stage / "usr/bin/forge-compositor"
        if os.name != "nt":
            compositor.chmod(0o4755)
            with self.assertRaises(ValueError):
                self.build()
            compositor.chmod(0o755)
        with self.assertRaises(ValueError):
            create_bundle(self.stage, self.output, "latest", "a" * 40)

    def test_rejects_substituted_session_command(self):
        entry = self.stage / "usr/share/wayland-sessions/forgedesktop.desktop"
        entry.write_bytes(self.files["usr/share/wayland-sessions/forgedesktop.desktop"][0]
                          .replace(b"forge-session", b"other-session"))
        with self.assertRaises(ValueError):
            self.build()
        self.assertFalse(self.output.exists())

    def test_does_not_replace_existing_release(self):
        self.output.mkdir()
        (self.output / "marker").write_text("keep")
        with self.assertRaises(FileExistsError):
            self.build()
        self.assertEqual((self.output / "marker").read_text(), "keep")

    def test_does_not_replace_broken_release_symlink(self):
        try:
            self.output.symlink_to(self.root / "missing-release", target_is_directory=True)
        except OSError:
            self.skipTest("symlinks unavailable")
        with self.assertRaises(FileExistsError):
            self.build()
        self.assertTrue(self.output.is_symlink())


if __name__ == "__main__":
    unittest.main()
