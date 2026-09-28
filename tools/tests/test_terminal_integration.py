"""Terminal launch argument preservation and reversible personal settings."""
import configparser
import base64
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
    def legacy_shortcut_receipt(self, migration, home, before=None, status="applied"):
        migration.apply(home)
        state = migration.load_state(home)
        after = b"[org.forge.RTerm.desktop]\n_launch=Ctrl+Alt+T,Ctrl+Alt+T,R-Term\n_k_friendly_name=R-Term\n"
        if before:
            after += b"[org.kde.konsole.desktop]\n_launch=none,none,Terminal\n"
        state["files"][".config/kglobalshortcutsrc"] = {
            "before": None if before is None else base64.b64encode(before).decode(),
            "after": base64.b64encode(after).decode(), "afterSha256": migration.sha(after)}
        state["status"] = status
        migration.save_state(home, state)
        return state

    def test_restore_legacy_receipt_disables_omitted_desktop_default_and_restores_old_binding(self):
        migration = module("terminal_defaults")
        with tempfile.TemporaryDirectory() as temporary:
            home = Path(temporary)
            before = b"[org.kde.konsole.desktop]\n_launch=Ctrl+Alt+T,Ctrl+Alt+T,Konsole\n"
            self.legacy_shortcut_receipt(migration, home, before)
            path = home / ".config/kglobalshortcutsrc"
            path.write_bytes(b"[kwin]\ncustom=unchanged\n")
            migration.restore(home)
            config = path.read_bytes()
            self.assertEqual(migration.ini_entry(config, "services][org.forge.RTerm.desktop", "_launch")[2], "none")
            self.assertEqual(migration.ini_entry(config, "services][org.kde.konsole.desktop", "_launch")[2], "Ctrl+Alt+T")
            self.assertIn(b"custom=unchanged", config)

    def test_restore_legacy_receipt_rejects_later_services_binding_before_any_write(self):
        migration = module("terminal_defaults")
        with tempfile.TemporaryDirectory() as temporary:
            home = Path(temporary)
            self.legacy_shortcut_receipt(migration, home)
            (home / ".config/kglobalshortcutsrc").write_bytes(b"[services][org.forge.RTerm.desktop]\n_launch=Meta+Return\n")
            before = {name: migration.read(home / name) for name in migration.CONFIGS}
            with self.assertRaises(ValueError):
                migration.restore(home)
            self.assertEqual(before, {name: migration.read(home / name) for name in migration.CONFIGS})

    def test_apply_uses_services_and_restore_recovers_preexisting_effective_bindings(self):
        migration = module("terminal_defaults")
        for old in (b"[services][org.forge.RTerm.desktop]\n_launch=Meta+Return\n",
                    b"[org.forge.RTerm.desktop]\n_launch=Meta+Return,Ctrl+Alt+T,Personal\n"):
            with self.subTest(old=old), tempfile.TemporaryDirectory() as temporary:
                home = Path(temporary)
                (home / ".config").mkdir()
                path = home / ".config/kglobalshortcutsrc"
                path.write_bytes(old + b"[services][org.kde.konsole.desktop]\n_launch=Ctrl+Alt+T\n")
                migration.apply(home)
                config = path.read_bytes()
                self.assertEqual(migration.ini_entry(config, "services][org.forge.RTerm.desktop", "_launch")[2], "Ctrl+Alt+T")
                self.assertEqual(migration.ini_entry(config, "services][org.kde.konsole.desktop", "_launch")[2], "none")
                self.assertIsNone(migration.ini_entry(config, "org.forge.RTerm.desktop", "_launch")[2])
                migration.restore(home)
                self.assertEqual(migration.ini_entry(path.read_bytes(), "services][org.forge.RTerm.desktop", "_launch")[2], "Meta+Return")
                self.assertEqual(migration.ini_entry(path.read_bytes(), "services][org.kde.konsole.desktop", "_launch")[2], "Ctrl+Alt+T")

    def test_prior_restored_receipt_repairs_only_shortcut_default_once(self):
        migration = module("terminal_defaults")
        with tempfile.TemporaryDirectory() as temporary:
            home = Path(temporary)
            self.legacy_shortcut_receipt(migration, home, status="restored")
            path = home / ".config/kglobalshortcutsrc"
            path.write_bytes(b"[kwin]\ncustom=keep\n")
            kde = home / ".config/kdeglobals"
            kde.write_bytes(b"[General]\nTerminalApplication=after-restore-choice\n")
            migration.restore(home)
            self.assertEqual(migration.ini_entry(path.read_bytes(), "services][org.forge.RTerm.desktop", "_launch")[2], "none")
            self.assertIn(b"after-restore-choice", kde.read_bytes())
            restored = path.read_bytes()
            migration.restore(home)
            self.assertEqual(restored, path.read_bytes())

    def test_restore_matches_kde_legacy_and_services_precedence(self):
        migration = module("terminal_defaults")
        for legacy_active, expected in (("Meta+Return", "Meta+Return"), ("Ctrl+Alt+T", "Meta+Space")):
            with self.subTest(legacy=legacy_active), tempfile.TemporaryDirectory() as temporary:
                home = Path(temporary)
                (home / ".config").mkdir()
                path = home / ".config/kglobalshortcutsrc"
                path.write_text("[services][org.forge.RTerm.desktop]\n_launch=Meta+Space\n"
                                "[org.forge.RTerm.desktop]\n_launch=" + legacy_active + ",Ctrl+Alt+T,R-Term\n")
                migration.apply(home)
                migration.restore(home)
                self.assertEqual(migration.ini_entry(path.read_bytes(), "services][org.forge.RTerm.desktop", "_launch")[2], expected)

    def test_restore_protects_later_old_terminal_binding_and_unchanged_rterm_binding(self):
        migration = module("terminal_defaults")
        with tempfile.TemporaryDirectory() as temporary:
            home = Path(temporary)
            (home / ".config").mkdir()
            path = home / ".config/kglobalshortcutsrc"
            path.write_bytes(b"[services][org.kde.konsole.desktop]\n_launch=Ctrl+Alt+T\n")
            migration.apply(home)
            path.write_bytes(path.read_bytes().replace(b"_launch=none", b"_launch=Meta+K"))
            before = {name: migration.read(home / name) for name in migration.CONFIGS}
            with self.assertRaises(ValueError):
                migration.restore(home)
            self.assertEqual(before, {name: migration.read(home / name) for name in migration.CONFIGS})
        with tempfile.TemporaryDirectory() as temporary:
            home = Path(temporary)
            (home / ".config").mkdir()
            path = home / ".config/kglobalshortcutsrc"
            path.write_bytes(b"[services][org.forge.RTerm.desktop]\n_launch=Ctrl+Alt+T\n")
            migration.apply(home)
            path.write_bytes(path.read_bytes().replace(b"Ctrl+Alt+T", b"Meta+Return"))
            migration.restore(home)
            self.assertIn(b"_launch=Meta+Return", path.read_bytes())

    def test_apply_changes_only_the_complete_dock_launcher_token(self):
        migration = module("terminal_defaults")
        with tempfile.TemporaryDirectory() as temporary:
            home = Path(temporary)
            config = home / ".config"
            config.mkdir()
            path = config / "plasma-org.kde.plasma.desktop-appletsrc"
            original = (b"[Containments][7][Applets][9][Configuration][General]\n"
                        b"launchers=applications:xfce4-terminal.desktop.custom,applications:xfce4-terminal.desktop,applications:custom.desktop\r\n")
            path.write_bytes(original)
            migration.apply(home)
            self.assertEqual(path.read_bytes(), original.replace(
                b",applications:xfce4-terminal.desktop,", b",applications:org.forge.RTerm.desktop,"))

    def test_apply_rejects_owned_ini_conflicts_before_receipt_or_settings_writes(self):
        migration = module("terminal_defaults")
        cases = (
            ("kdeglobals", b"[General][$i]\nTerminalApplication=personal\n"),
            ("kdeglobals", b"[General]\nTerminalApplication[$i]=personal\n"),
            ("kdeglobals", b"[General]\nTerminalApplication=one\n[General]\nTerminalApplication=two\n"),
            ("kglobalshortcutsrc", b"[org.forge.RTerm.desktop][$i]\n_launch=Meta+T,none,Personal\n"),
            ("kglobalshortcutsrc", b"[org.forge.RTerm.desktop]\n_launch[$i]=Meta+T,none,Personal\n"),
            ("kglobalshortcutsrc", b"[org.forge.RTerm.desktop]\n_launch=one\n[org.forge.RTerm.desktop]\n_launch=two\n"),
            ("kglobalshortcutsrc", b"[org.kde.konsole.desktop][$i]\n_launch=Ctrl+Alt+T,none,Terminal\n"),
            ("kglobalshortcutsrc", b"[services][$i]\n[services][org.forge.RTerm.desktop]\n_launch=Meta+T\n"),
            ("kglobalshortcutsrc", b"[services][org.forge.RTerm.desktop]\n_launch[$i]=Meta+T\n"),
            ("kglobalshortcutsrc", b"[services][org.forge.RTerm.desktop]\n_launch=Meta+T\n[services][org.forge.RTerm.desktop]\n_launch=Meta+R\n"),
            ("plasma-org.kde.plasma.desktop-appletsrc", b"[Containments][7][$i]\nlaunchers=applications:xfce4-terminal.desktop\n"),
            ("plasma-org.kde.plasma.desktop-appletsrc", b"[Containments][7]\nlaunchers[$i]=applications:xfce4-terminal.desktop\n"),
            ("plasma-org.kde.plasma.desktop-appletsrc", b"[Containments][7]\nlaunchers=applications:xfce4-terminal.desktop\n[Containments][7]\nlaunchers=applications:custom.desktop\n"),
        )
        for filename, raw in cases:
            with self.subTest(filename=filename, raw=raw), tempfile.TemporaryDirectory() as temporary:
                home = Path(temporary)
                (home / ".config").mkdir()
                (home / ".config" / filename).write_bytes(raw)
                before = {name: migration.read(home / name) for name in migration.CONFIGS}
                with self.assertRaises(ValueError):
                    migration.apply(home)
                self.assertEqual(before, {name: migration.read(home / name) for name in migration.CONFIGS})
                self.assertFalse((home / migration.STATE).exists())

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
            shortcuts = (home / ".config/kglobalshortcutsrc").read_bytes()
            self.assertEqual(module("terminal_defaults").ini_entry(
                shortcuts, "services][org.forge.RTerm.desktop", "_launch")[2], "Ctrl+Alt+T")

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

    def test_wayland_session_never_falls_back_to_inherited_x11_display(self):
        launcher = module("forge_terminal")
        actual = launcher.command([], {"XDG_SESSION_TYPE": "wayland", "DISPLAY": ":0"})
        self.assertEqual(actual[actual.index("--display-backend") + 1], "wayland")

    def test_x11_session_ignores_nested_wayland_display(self):
        launcher = module("forge_terminal")
        actual = launcher.command([], {"XDG_SESSION_TYPE": "x11", "DISPLAY": ":0",
                                       "WAYLAND_DISPLAY": "nested-wayland"})
        self.assertEqual(actual[actual.index("--display-backend") + 1], "x11")

    def test_unknown_session_type_uses_available_display_and_pure_tty_is_rejected(self):
        launcher = module("forge_terminal")
        actual = launcher.command([], {"XDG_SESSION_TYPE": "unknown", "WAYLAND_DISPLAY": "wayland-0"})
        self.assertEqual(actual[actual.index("--display-backend") + 1], "wayland")
        with self.assertRaises(ValueError):
            launcher.command([], {"XDG_SESSION_TYPE": "tty"})

    def test_launcher_inherits_desktop_working_directory_without_shell_expansion(self):
        launcher = module("forge_terminal")
        arguments = ["-e", "/usr/bin/program", "含 空格", "$(literal)"]
        with mock.patch.object(launcher.os, "getcwd", return_value="/home/forge/项目 space"):
            with mock.patch.object(launcher.sys, "argv", ["forge-terminal", *arguments]):
                with mock.patch.dict(launcher.os.environ, {"WAYLAND_DISPLAY": "wayland-0"}, clear=True):
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

    def test_restore_preserves_post_login_colors_shortcuts_and_dock_customization(self):
        migration = module("terminal_defaults")
        with tempfile.TemporaryDirectory() as temporary:
            home = Path(temporary)
            config = home / ".config"
            config.mkdir()
            kde = config / "kdeglobals"
            kde.write_bytes(b"[General]\nTerminalApplication=xfce4-terminal\n")
            layout = config / "plasma-org.kde.plasma.desktop-appletsrc"
            group = b"[Containments][7][Applets][9][Configuration][General]\n"
            layout.write_bytes(group + b"launchers=applications:firefox.desktop,applications:xfce4-terminal.desktop\n")
            migration.apply(home)
            receipt_before = (home / migration.STATE).read_bytes()
            kde.write_bytes(kde.read_bytes() + b"[Colors:Window]\nBackgroundNormal=35,38,41\n")
            shortcuts = config / "kglobalshortcutsrc"
            shortcuts.write_bytes(shortcuts.read_bytes() + b"[personal]\ncustom=Meta+X,none,My action\n")
            layout.write_bytes(group + b"launchers=applications:custom.desktop,applications:org.forge.RTerm.desktop,applications:firefox.desktop\ncustom=keep\n")
            migration.restore(home)
            self.assertIn(b"TerminalApplication=xfce4-terminal", kde.read_bytes())
            self.assertNotIn(b"TerminalService=", kde.read_bytes())
            self.assertIn(b"BackgroundNormal=35,38,41", kde.read_bytes())
            self.assertIn(b"custom=Meta+X,none,My action", shortcuts.read_bytes())
            self.assertNotIn(b"_launch=Ctrl+Alt+T", shortcuts.read_bytes())
            self.assertEqual(layout.read_bytes(), group + b"launchers=applications:custom.desktop,applications:xfce4-terminal.desktop,applications:firefox.desktop\ncustom=keep\n")
            restored = {name: migration.read(home / name) for name in migration.CONFIGS}
            migration.restore(home)
            self.assertEqual(restored, {name: migration.read(home / name) for name in migration.CONFIGS})
            self.assertEqual(json.loads(receipt_before)["files"], migration.load_state(home)["files"])

    def test_restore_conflicts_preflight_all_files_before_any_write(self):
        migration = module("terminal_defaults")
        for target in ("terminal", "shortcut", "dock", "ambiguous_dock"):
            with self.subTest(target=target), tempfile.TemporaryDirectory() as temporary:
                home = Path(temporary)
                config = home / ".config"
                config.mkdir()
                layout = config / "plasma-org.kde.plasma.desktop-appletsrc"
                layout.write_bytes(b"[Containments][7][Applets][9][Configuration][General]\nlaunchers=applications:xfce4-terminal.desktop\n")
                migration.apply(home)
                if target == "terminal":
                    path, old, new = config / "kdeglobals", b"forge-terminal", b"personal-terminal"
                elif target == "shortcut":
                    path, old, new = config / "kglobalshortcutsrc", b"_launch=Ctrl+Alt+T", b"_launch=Meta+Return"
                else:
                    path, old = layout, b"applications:org.forge.RTerm.desktop"
                    new = b"applications:personal.desktop" if target == "dock" else old + b"," + old
                path.write_bytes(path.read_bytes().replace(old, new))
                before = {name: migration.read(home / name) for name in migration.CONFIGS}
                with self.assertRaises(ValueError):
                    migration.restore(home)
                self.assertEqual(before, {name: migration.read(home / name) for name in migration.CONFIGS})
                self.assertEqual(migration.load_state(home)["status"], "applied")

    def test_restore_leaves_preexisting_rterm_preferences_and_unchanged_files_alone(self):
        migration = module("terminal_defaults")
        with tempfile.TemporaryDirectory() as temporary:
            home = Path(temporary)
            config = home / ".config"
            config.mkdir()
            kde = config / "kdeglobals"
            kde.write_bytes(b"[General]\nTerminalApplication=forge-terminal\nTerminalService=org.forge.RTerm.desktop\n")
            migration.apply(home)
            kde.write_bytes(b"[General]\nTerminalApplication=personal-terminal\nTerminalService=personal.desktop\n")
            layout = config / "plasma-org.kde.plasma.desktop-appletsrc"
            layout.write_bytes(b"[personal-panel]\nlaunchers=applications:org.forge.RTerm.desktop\n")
            migration.restore(home)
            self.assertIn(b"personal-terminal", kde.read_bytes())
            self.assertEqual(layout.read_bytes(), b"[personal-panel]\nlaunchers=applications:org.forge.RTerm.desktop\n")

    def test_restore_accepts_plasma_removing_new_shortcut_group_and_creating_layout(self):
        migration = module("terminal_defaults")
        with tempfile.TemporaryDirectory() as temporary:
            home = Path(temporary)
            migration.apply(home)
            config = home / ".config"
            kde = config / "kdeglobals"
            kde.write_bytes(b"[Colors:Window]\nBackgroundNormal=35,38,41\n" + kde.read_bytes()
                            + b"ColorSchemeHash=plasma-generated\n")
            shortcuts = config / "kglobalshortcutsrc"
            plasma_shortcuts = "[kwin]\n_k_friendly_name=KWin\nWindow Close=Alt+F4,Alt+F4,关闭窗口\n".encode()
            shortcuts.write_bytes(plasma_shortcuts)
            layout = config / "plasma-org.kde.plasma.desktop-appletsrc"
            plasma_layout = b"[Containments][2]\nplugin=org.kde.panel\nlocation=4\n"
            layout.write_bytes(plasma_layout)
            migration.restore(home)
            self.assertEqual(shortcuts.read_bytes(), plasma_shortcuts +
                             b"[services][org.forge.RTerm.desktop]\n_launch=none\n")
            self.assertEqual(layout.read_bytes(), plasma_layout)
            self.assertIn(b"BackgroundNormal=35,38,41", kde.read_bytes())
            self.assertIn(b"ColorSchemeHash=plasma-generated", kde.read_bytes())
            self.assertNotIn(b"TerminalApplication=", kde.read_bytes())

    def test_restore_rejects_duplicate_owned_key_or_group_without_partial_writes(self):
        migration = module("terminal_defaults")
        for extra in (b"TerminalApplication=personal-terminal\n",
                      b"[General]\nTerminalApplication=forge-terminal\n"):
            with self.subTest(extra=extra), tempfile.TemporaryDirectory() as temporary:
                home = Path(temporary)
                migration.apply(home)
                path = home / ".config/kdeglobals"
                path.write_bytes(path.read_bytes() + extra)
                before = {name: migration.read(home / name) for name in migration.CONFIGS}
                with self.assertRaises(ValueError):
                    migration.restore(home)
                self.assertEqual(before, {name: migration.read(home / name) for name in migration.CONFIGS})

    def test_restore_rejects_owned_group_flags_before_any_write(self):
        migration = module("terminal_defaults")
        for filename, group in (("kdeglobals", "General"),
                                ("kglobalshortcutsrc", "org.forge.RTerm.desktop")):
            for flag in ("$i", "$d"):
                with self.subTest(filename=filename, flag=flag), tempfile.TemporaryDirectory() as temporary:
                    home = Path(temporary)
                    migration.apply(home)
                    path = home / ".config" / filename
                    header = ("[" + group + "]").encode()
                    path.write_bytes(path.read_bytes().replace(header, header + ("[" + flag + "]").encode()))
                    before = {name: migration.read(home / name) for name in migration.CONFIGS}
                    with self.assertRaisesRegex(ValueError, "group flags"):
                        migration.restore(home)
                    self.assertEqual(before, {name: migration.read(home / name) for name in migration.CONFIGS})
                    self.assertEqual(migration.load_state(home)["status"], "applied")

    def test_interrupted_semantic_restore_can_be_retried_from_original_receipt(self):
        migration = module("terminal_defaults")
        with tempfile.TemporaryDirectory() as temporary:
            home = Path(temporary)
            migration.apply(home)
            path = home / ".config/kdeglobals"
            path.write_bytes(path.read_bytes() + b"[Colors:Window]\nBackgroundNormal=1,2,3\n")
            original_put = migration.put
            count = 0

            def interrupted(*args):
                nonlocal count
                count += 1
                if count == 2:
                    raise OSError("interrupted restore")
                original_put(*args)

            with mock.patch.object(migration, "put", side_effect=interrupted):
                with self.assertRaises(OSError):
                    migration.restore(home)
            self.assertEqual(migration.load_state(home)["status"], "applied")
            migration.restore(home)
            self.assertNotIn(b"TerminalApplication=", path.read_bytes())
            self.assertIn(b"BackgroundNormal=1,2,3", path.read_bytes())
            self.assertEqual(migration.load_state(home)["status"], "restored")

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
