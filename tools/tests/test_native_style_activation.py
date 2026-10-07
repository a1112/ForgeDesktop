"""Explicit native style activation preserves existing KWin preferences."""
import importlib.machinery
import importlib.util
from pathlib import Path
import subprocess
import unittest

from tools.build_plasma_bundle import eligible_path, validate_ros_theme
from tools.stage_ros_theme import stage_theme
import tempfile

ROOT = Path(__file__).resolve().parents[2]


class NativeStyleActivationTests(unittest.TestCase):
    def module(self):
        path = ROOT / "plasma/session/forge-native-style"
        self.assertTrue(path.is_file(), "safe native style activation is missing")
        loader = importlib.machinery.SourceFileLoader("native_style", str(path))
        spec = importlib.util.spec_from_loader(loader.name, loader)
        module = importlib.util.module_from_spec(spec)
        loader.exec_module(module)
        return module

    def runner(self, initial=None, fail_reload=False):
        state = dict(initial or {})
        calls = []
        def run(argv, **kwargs):
            calls.append(argv)
            if argv[0] == "kreadconfig6":
                key = tuple(argv[argv.index(flag) + 1] for flag in ("--file", "--group", "--key"))
                value = state.get(key, argv[argv.index("--default") + 1])
                return subprocess.CompletedProcess(argv, 0, value + "\n", "")
            if argv[0] == "kwriteconfig6":
                key = tuple(argv[argv.index(flag) + 1] for flag in ("--file", "--group", "--key"))
                state[key] = argv[-1]
            if fail_reload and argv[0] == "qdbus6":
                raise subprocess.CalledProcessError(1, argv, stderr="KWin unavailable")
            return subprocess.CompletedProcess(argv, 0, "", "")
        return run, state, calls

    def test_missing_keys_initialized_and_reloaded_without_resetting_layout(self):
        module = self.module()
        runner, state, calls = self.runner()
        module.activate(runner=runner, uid=1000)
        self.assertEqual(state[("kwinrc", "org.kde.kdecoration2", "ButtonsOnLeft")], "XIA")
        self.assertEqual(state[("kwinrc", "org.kde.kdecoration2", "ButtonsOnRight")], "")
        self.assertEqual(state[("kwinrc", "Windows", "BorderlessMaximizedWindows")], "true")
        self.assertEqual(calls[-1], ["qdbus6", "org.kde.KWin", "/KWin", "reconfigure"])
        self.assertFalse(any("--resetLayout" in argv for argv in calls))
        writes = sum(argv[0] == "kwriteconfig6" for argv in calls)
        module.activate(runner=runner, uid=1000)
        self.assertEqual(sum(argv[0] == "kwriteconfig6" for argv in calls), writes)

    def test_existing_custom_and_empty_values_preserved_and_second_run_idempotent(self):
        module = self.module()
        initial = {("kwinrc", "org.kde.kdecoration2", "ButtonsOnLeft"): "",
                   ("kwinrc", "org.kde.kdecoration2", "ButtonsOnRight"): "AIAX",
                   ("kwinrc", "Windows", "BorderlessMaximizedWindows"): "false"}
        runner, state, calls = self.runner(initial)
        module.activate(runner=runner, uid=1000)
        module.activate(runner=runner, uid=1000)
        self.assertEqual(state, initial)
        self.assertFalse(any(argv[0] == "kwriteconfig6" for argv in calls))

    def test_marker_value_is_not_mistaken_for_missing_user_preference(self):
        module = self.module()
        initial = {("kwinrc", "org.kde.kdecoration2", "ButtonsOnLeft"): "__forge_missing_a__"}
        runner, state, calls = self.runner(initial)
        module.activate(runner=runner, uid=1000)
        self.assertEqual(state[next(iter(initial))], "__forge_missing_a__")

    def test_root_rejected_before_any_commands_and_reload_failure_not_hidden(self):
        module = self.module()
        runner, state, calls = self.runner()
        with self.assertRaises(PermissionError):
            module.activate(runner=runner, uid=0)
        self.assertEqual(calls, [])
        runner, state, calls = self.runner(fail_reload=True)
        with self.assertRaises(subprocess.CalledProcessError):
            module.activate(runner=runner, uid=1000)

    def test_top_panel_explicitly_disables_floating(self):
        layout = (ROOT / "plasma/look-and-feel/contents/layouts/org.kde.plasma.desktop-layout.js").read_text()
        self.assertIn("topPanel.floating = false;", layout)

    def test_dock_writes_typed_launcher_list_not_escaped_single_string(self):
        layout = (ROOT / "plasma/look-and-feel/contents/layouts/org.kde.plasma.desktop-layout.js").read_text()
        self.assertIn('tasks.writeConfig("launchers", launchers);', layout)
        self.assertNotIn('launchers.join(",")', layout)

    def test_activation_assets_are_closed_and_modified_script_rejected(self):
        script = "usr/libexec/forge-desktop/forge-native-style"
        entry = "usr/share/applications/org.forge.NativeStyle.desktop"
        with tempfile.TemporaryDirectory() as directory:
            payloads = stage_theme(Path(directory) / "stage")
            self.assertIn(script, payloads)
            self.assertIn(entry, payloads)
            self.assertTrue(eligible_path(script) and eligible_path(entry))
            self.assertEqual(payloads[script][1], 0o755)
            validate_ros_theme(payloads)
            payloads[script] = (payloads[script][0] + b"\nprint('unexpected')\n", 0o755)
            with self.assertRaises(ValueError):
                validate_ros_theme(payloads)


if __name__ == "__main__":
    unittest.main()
