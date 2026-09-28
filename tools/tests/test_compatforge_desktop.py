import importlib.util
import json
import tempfile
import unittest
from unittest import mock
from pathlib import Path

MODULE = Path(__file__).parents[1] / "compatforge_desktop.py"
spec = importlib.util.spec_from_file_location("compatforge_desktop", MODULE)
desktop = importlib.util.module_from_spec(spec)
spec.loader.exec_module(desktop)


def export(name="压缩 文件 100%", generation="gen-job-1"):
    entry_id = "org.forgeos.CompatForge.7zip.main.desktop"
    content = ("[Desktop Entry]\nType=Application\nVersion=1.0\n"
               f"Name={name}\nExec=/usr/bin/compatforge-cli desktop-launch 7zip main -- %F\n"
               "TryExec=/usr/bin/compatforge-cli\nIcon=package-x-generic\nTerminal=false\n"
               "Categories=Utility;\nX-Forge-Managed=true\nStartupWMClass=7zfm.exe\n"
               "MimeType=application/zip;application/x-7z-compressed;\n")
    return {"schemaVersion": "1", "entries": [{"entryId": entry_id, "applicationId": "7zip",
             "generationId": generation, "desktopEntry": content}]}


class ReconcileTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.root = Path(self.temp.name)
        self.apps = self.root / "data" / "applications"
        self.state = self.root / "state"

    def tearDown(self):
        self.temp.cleanup()

    def sync(self, data):
        return desktop.reconcile(data, self.apps, self.state)

    def test_install_update_uninstall_preserves_user_mime_defaults(self):
        self.apps.mkdir(parents=True)
        defaults = self.apps / "mimeapps.list"
        defaults.write_text("[Default Applications]\ntext/plain=user.desktop;\n")
        data = export()
        entry = self.apps / data["entries"][0]["entryId"]
        self.assertEqual(self.sync(data)["written"], [entry.name])
        self.assertIn("Name=压缩 文件 100%", entry.read_text(encoding="utf-8"))
        self.assertEqual(self.sync(data)["written"], [])
        self.assertEqual(self.sync(export("Changed", "gen-job-2"))["written"], [entry.name])
        self.assertIn("Name=Changed", entry.read_text(encoding="utf-8"))
        self.assertEqual(self.sync({"schemaVersion": "1", "entries": []})["removed"], [entry.name])
        self.assertFalse(entry.exists())
        self.assertEqual(defaults.read_text(), "[Default Applications]\ntext/plain=user.desktop;\n")

    def test_foreign_files_and_user_edits_are_never_overwritten_or_deleted(self):
        data = export()
        entry = self.apps / data["entries"][0]["entryId"]
        self.apps.mkdir(parents=True)
        entry.write_text("foreign")
        self.assertEqual(self.sync(data)["conflicts"], [entry.name])
        self.assertEqual(entry.read_text(), "foreign")
        entry.unlink()
        self.sync(data)
        entry.write_text("user edit")
        self.assertEqual(self.sync(export("Changed"))["conflicts"], [entry.name])
        self.assertEqual(self.sync({"schemaVersion": "1", "entries": []})["conflicts"], [entry.name])
        self.assertEqual(entry.read_text(), "user edit")

    def test_invalid_entry_or_corrupt_manifest_fails_before_mutation(self):
        data = export()
        for bad in ["../../evil.desktop", "org.forgeos.CompatForge.CON.main.desktop"]:
            invalid = json.loads(json.dumps(data))
            invalid["entries"][0]["entryId"] = bad
            with self.assertRaises(ValueError):
                self.sync(invalid)
        invalid = export("Good\nExec=sh -c evil")
        with self.assertRaises(ValueError):
            self.sync(invalid)
        self.sync(data)
        path = self.state / "launchers-v1.json"
        path.write_text("{broken")
        with self.assertRaises(ValueError):
            self.sync({"schemaVersion": "1", "entries": []})
        self.assertTrue((self.apps / data["entries"][0]["entryId"]).exists())

    def test_entry_identity_rejected_before_filesystem_when_over_name_max(self):
        data = export()
        entry = data["entries"][0]
        app, launcher = "a" * 128, "b" * 128
        entry["entryId"] = f"org.forgeos.CompatForge.{app}.{launcher}.desktop"
        entry["applicationId"] = app
        entry["desktopEntry"] = entry["desktopEntry"].replace("desktop-launch 7zip main", f"desktop-launch {app} {launcher}")
        with self.assertRaises(ValueError):
            desktop.validate_export(data)

    def test_refuses_linked_application_directory(self):
        target = self.root / "target"
        target.mkdir()
        try:
            self.apps.parent.mkdir()
            self.apps.symlink_to(target, target_is_directory=True)
        except OSError:
            self.skipTest("symlink privilege unavailable")
        with self.assertRaises(ValueError):
            self.sync(export())
        self.assertEqual(list(target.iterdir()), [])

    def test_manifest_capacity_rejection_does_not_create_unowned_files(self):
        original_limit = desktop.MAX_ENTRIES
        desktop.MAX_ENTRIES = 1
        self.addCleanup(setattr, desktop, "MAX_ENTRIES", original_limit)
        self.sync(export())
        existing = self.apps / export()["entries"][0]["entryId"]
        existing.write_text("user override")
        alternate = export()
        entry = alternate["entries"][0]
        entry["entryId"] = entry["entryId"].replace("7zip", "other")
        entry["applicationId"] = "other"
        entry["desktopEntry"] = entry["desktopEntry"].replace("desktop-launch 7zip", "desktop-launch other")
        with self.assertRaises(ValueError):
            self.sync(alternate)
        self.assertFalse((self.apps / entry["entryId"]).exists())

    def test_recovers_entry_written_before_manifest_without_adopting_user_edits(self):
        original = desktop.atomic_write
        def fail_manifest(path, data, previous):
            if path.name == "launchers-v1.json":
                raise OSError("injected crash before manifest")
            return original(path, data, previous)
        with mock.patch.object(desktop, "atomic_write", fail_manifest):
            with self.assertRaises(OSError):
                self.sync(export())
        result = self.sync(export())
        self.assertEqual(result["conflicts"], [])
        self.assertFalse((self.state / "intent-v1.json").exists())
        entry = self.apps / export()["entries"][0]["entryId"]
        with mock.patch.object(desktop, "atomic_write", fail_manifest):
            with self.assertRaises(OSError):
                self.sync(export("Updated"))
        entry.write_text("user edit during interruption")
        self.assertEqual(self.sync(export("Updated"))["conflicts"], [entry.name])
        self.assertEqual(entry.read_text(), "user edit during interruption")

    def test_partial_multi_entry_transaction_finishes_safely(self):
        first = export()
        second = json.loads(json.dumps(first["entries"][0]))
        second["entryId"] = second["entryId"].replace("7zip", "another")
        second["applicationId"] = "another"
        second["desktopEntry"] = second["desktopEntry"].replace("desktop-launch 7zip", "desktop-launch another")
        first["entries"].append(second)
        self.sync(first)
        changed = json.loads(json.dumps(first))
        for entry in changed["entries"]:
            entry["desktopEntry"] = entry["desktopEntry"].replace("Name=压缩 文件 100%", "Name=Updated")
        original = desktop.atomic_write
        calls = []
        def fail_second(path, data, previous):
            if path.suffix == ".desktop":
                calls.append(path)
                if len(calls) == 2:
                    raise OSError("injected partial transaction")
            return original(path, data, previous)
        with mock.patch.object(desktop, "atomic_write", fail_second):
            with self.assertRaises(OSError):
                self.sync(changed)
        self.assertEqual(self.sync(changed)["conflicts"], [])
        for entry in changed["entries"]:
            self.assertIn("Name=Updated", (self.apps / entry["entryId"]).read_text(encoding="utf-8"))
        self.assertEqual(len(self.sync({"schemaVersion": "1", "entries": []})["removed"]), 2)


if __name__ == "__main__":
    unittest.main()
