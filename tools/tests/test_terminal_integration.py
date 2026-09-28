"""Terminal launch argument preservation and reversible personal settings."""
import configparser
import importlib.util
import json
import shutil
from pathlib import Path
import tempfile
import unittest
from unittest import mock
from types import SimpleNamespace

ROOT = Path(__file__).resolve().parents[2]


def module(name):
    spec = importlib.util.spec_from_file_location(name, ROOT / "plasma/terminal" / (name + ".py"))
    value = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(value)
    return value


class TerminalIntegrationTests(unittest.TestCase):
    def test_new_account_skeleton_selects_the_packaged_forge_layout(self):
        from tools.stage_plasma_bundle import stage
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            staged = root / "stage"
            stage(ROOT, staged)
            home = root / "new-user"
            shutil.copytree(staged / "etc/skel", home)
            config = configparser.ConfigParser(interpolation=None)
            config.read(home / ".config/kdeglobals", encoding="utf-8")
            selected = config.get("KDE", "LookAndFeelPackage")
            self.assertEqual(selected, "org.forge.desktop")
            package = staged / "usr/share/plasma/look-and-feel" / selected
            self.assertEqual(json.loads((package / "metadata.json").read_text())["KPlugin"]["Id"], selected)
            layout = package / "contents/layouts/org.kde.plasma.desktop-layout.js"
            self.assertIn("applications:org.forge.RTerm.desktop", layout.read_text())
            self.assertFalse((home / ".config/plasma-org.kde.plasma.desktop-appletsrc").exists())
            self.assertEqual(config.get("General", "TerminalApplication"), "forge-terminal")

    def test_existing_account_without_plasma_state_is_not_given_a_theme_or_layout(self):
        migration = module("terminal_defaults")
        with tempfile.TemporaryDirectory() as temporary:
            home = Path(temporary)
            migration.apply(home)
            config = configparser.ConfigParser(interpolation=None)
            config.read(home / ".config/kdeglobals", encoding="utf-8")
            self.assertFalse(config.has_option("KDE", "LookAndFeelPackage"))
            self.assertFalse((home / ".config/plasma-org.kde.plasma.desktop-appletsrc").exists())

    def test_large_valid_configuration_has_restorable_backup(self):
        migration = module("terminal_defaults")
        with tempfile.TemporaryDirectory() as temporary:
            home = Path(temporary)
            (home / ".config").mkdir()
            path = home / ".config/kdeglobals"
            original = b"[General]\nOther=" + b"x" * (2 * 1024 * 1024) + b"\n"
            path.write_bytes(original)
            migration.apply(home)
            migration.restore(home)
            self.assertEqual(path.read_bytes(), original)

    def test_offline_guest_uid_need_not_exist_on_builder(self):
        migration = module("terminal_defaults")
        with tempfile.TemporaryDirectory() as temporary:
            with mock.patch.object(migration, "os", SimpleNamespace(name="posix")):
                with mock.patch.dict("sys.modules", {"pwd": SimpleNamespace(getpwuid=mock.Mock(side_effect=KeyError))}):
                    migration.ensure_offline(Path(temporary))

    def test_only_reviewed_terminal_paths_are_bundle_eligible(self):
        from tools.build_plasma_bundle import eligible_path
        for name in ("usr/bin/forge-terminal", "usr/libexec/forge-desktop/terminal-defaults",
                     "usr/share/applications/org.forge.RTerm.desktop",
                     "usr/share/xfce4/helpers/forge-terminal.desktop",
                     "etc/skel/.config/kdeglobals", "etc/skel/.config/kglobalshortcutsrc",
                     "etc/skel/.config/xfce4/helpers.rc"):
            self.assertTrue(eligible_path(name), name)
        self.assertFalse(eligible_path("usr/bin/arbitrary-command"))

    def test_native_wayland_and_literal_arguments(self):
        launcher = module("forge_terminal")
        args = ["--cwd", "/home/forge/中文 space", "-e", "printf", "%s", "$(touch /tmp/should-not-exist)"]
        actual = launcher.command(args, {"WAYLAND_DISPLAY": "wayland-0", "DISPLAY": ":0"})
        self.assertEqual(actual, ["/usr/bin/rterm", "window", "--renderer", "cpu",
                                  "--display-backend", "wayland", "--class", "org.forge.RTerm", *args])

    def test_launcher_inherits_desktop_working_directory_without_shell_expansion(self):
        launcher = module("forge_terminal")
        arguments = ["-e", "/usr/bin/program", "含 空格", "$(literal)"]
        with mock.patch.object(launcher.os, "getcwd", return_value="/home/forge/项目 space"):
            with mock.patch.object(launcher.sys, "argv", ["forge-terminal", *arguments]):
                with mock.patch.dict(launcher.os.environ, {"WAYLAND_DISPLAY": "wayland-0"}):
                    with mock.patch.object(launcher.os, "execv") as execute:
                        launcher.main()
        execute.assert_called_once_with("/usr/bin/rterm", [
            "/usr/bin/rterm", "window", "--renderer", "cpu", "--display-backend", "wayland",
            "--class", "org.forge.RTerm", "--cwd", "/home/forge/项目 space", *arguments])

    def test_x11_and_no_display(self):
        launcher = module("forge_terminal")
        self.assertIn("x11", launcher.command([], {"DISPLAY": ":0"}))
        with self.assertRaises(ValueError):
            launcher.command([], {})

    def test_migration_is_idempotent_preserves_other_settings_and_rolls_back(self):
        migration = module("terminal_defaults")
        with tempfile.TemporaryDirectory() as temporary:
            home = Path(temporary)
            config = home / ".config"
            config.mkdir()
            original = b"# personal\n[KDE]\nLookAndFeelPackage=org.example.personal\n[General]\nTerminalApplication=xfce4-terminal\nColorScheme=MyColors\n"
            (config / "kdeglobals").write_bytes(original)
            layout = b"[Containments][7]\nplugin=org.kde.panel\nlocation=3\n[Containments][7][Applets][9][Configuration][General]\nlaunchers=applications:firefox.desktop,applications:xfce4-terminal.desktop\ncustom=keep\n"
            (config / "plasma-org.kde.plasma.desktop-appletsrc").write_bytes(layout)
            migration.apply(home)
            first = (config / "kdeglobals").read_bytes()
            self.assertIn(b"TerminalApplication=forge-terminal", first)
            self.assertIn(b"ColorScheme=MyColors", first)
            self.assertIn(b"[KDE]\nLookAndFeelPackage=org.example.personal\n", first)
            expected_layout = layout.replace(b"applications:xfce4-terminal.desktop", b"applications:org.forge.RTerm.desktop")
            self.assertEqual(expected_layout, (config / "plasma-org.kde.plasma.desktop-appletsrc").read_bytes())
            migration.apply(home)
            self.assertEqual(first, (config / "kdeglobals").read_bytes())
            migration.restore(home)
            self.assertEqual(original, (config / "kdeglobals").read_bytes())
            self.assertEqual(layout, (config / "plasma-org.kde.plasma.desktop-appletsrc").read_bytes())
            self.assertFalse((config / "xfce4/helpers.rc").exists())

    def test_changed_user_preferences_are_not_overwritten_by_restore(self):
        migration = module("terminal_defaults")
        with tempfile.TemporaryDirectory() as temporary:
            home = Path(temporary)
            migration.apply(home)
            path = home / ".config/kdeglobals"
            path.write_text(path.read_text().replace("forge-terminal", "another-terminal"))
            with self.assertRaises(ValueError):
                migration.restore(home)
            self.assertIn("another-terminal", path.read_text())

    def test_symlinked_configuration_is_rejected_before_writes(self):
        migration = module("terminal_defaults")
        with tempfile.TemporaryDirectory() as temporary:
            home = Path(temporary) / "home"
            home.mkdir()
            other = Path(temporary) / "other"
            other.mkdir()
            try:
                (home / ".config").symlink_to(other, target_is_directory=True)
            except OSError:
                self.skipTest("symlink privilege unavailable")
            with self.assertRaises(ValueError):
                migration.apply(home)
            self.assertEqual(list(other.iterdir()), [])


if __name__ == "__main__":
    unittest.main()
