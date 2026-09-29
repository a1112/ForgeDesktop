import json
from pathlib import Path
import tempfile
import unittest

from tools.stage_ros_theme import stage_theme, ROS_FILES
from tools.build_plasma_bundle import eligible_path, validate_ros_theme


class RosThemeTests(unittest.TestCase):
    def test_theme_stages_only_closed_list_and_keeps_auth_upstream(self):
        with tempfile.TemporaryDirectory() as directory:
            payloads = stage_theme(Path(directory) / "stage")
            self.assertEqual(set(payloads), set(ROS_FILES.values()))
            self.assertTrue(all(eligible_path(name) for name in payloads))
            validate_ros_theme(payloads)
            qml = next(data[0] for name, data in payloads.items() if name.endswith("LockScreen.qml"))
            self.assertIn(b"Upstream.LockScreen", qml)
            self.assertNotIn(b"authenticator", qml)
            self.assertNotIn(b"Qt.quit", qml)

    def test_partial_theme_and_changed_upstream_auth_delegate_rejected(self):
        with tempfile.TemporaryDirectory() as directory:
            payloads = stage_theme(Path(directory) / "stage")
            key = next(name for name in payloads if name.endswith("LockScreen.qml"))
            bad = dict(payloads)
            bad[key] = (bad[key][0].replace(b"Upstream.LockScreen", b"Item"), 0o644)
            with self.assertRaises(ValueError):
                validate_ros_theme(bad)
            del payloads[key]
            with self.assertRaises(ValueError):
                validate_ros_theme(payloads)

    def test_stage_does_not_replace_existing_path(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "stage"
            stage_theme(path)
            with self.assertRaises(FileExistsError):
                stage_theme(path)

    def test_shared_tokens_match_current_native_control_measurements(self):
        root = Path(__file__).resolve().parents[2]
        tokens = json.loads((root / "docs/design/r-os-tokens-v1.json").read_text())
        decoration = (root / "plasma/aurorae/ForgeDark/ForgeDarkrc").read_text()
        self.assertIn(f'TitleHeight={tokens["window"]["titleHeight"]}', decoration)
        self.assertIn(f'ButtonWidth={tokens["window"]["controlWidth"]}', decoration)
        qml = (root / "plasma/plasmoids/org.forge.windowcontrols/contents/ui/main.qml").read_text()
        self.assertIn(tokens["colors"]["closeHover"], qml)


if __name__ == "__main__":
    unittest.main()
