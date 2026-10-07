"""Native visual package stays complete, inert, and session scoped."""
import json
from pathlib import Path
import tempfile
import unittest
import xml.etree.ElementTree as ET

from tools.build_plasma_bundle import eligible_path, validate_ros_theme, validate_window_assets
from tools.stage_ros_theme import stage_theme

ROOT = Path(__file__).resolve().parents[2]
GTK_ROOT = "usr/share/themes/ForgeROS/"
PANEL_ROOT = "usr/share/plasma/desktoptheme/forge/"
NEW_FILES = {GTK_ROOT + "index.theme", *(GTK_ROOT + f"gtk-{version}.0/{name}"
             for version in (3, 4) for name in ("gtk.css", "gtk-dark.css")),
             *(PANEL_ROOT + name for name in ("metadata.json", "plasmarc", "colors",
                                             "widgets/panel-background.svg", "widgets/tasks.svg"))}


class NativeVisualContractTests(unittest.TestCase):
    def stage(self):
        temp = tempfile.TemporaryDirectory()
        self.addCleanup(temp.cleanup)
        return stage_theme(Path(temp.name) / "stage")

    def test_native_app_and_panel_theme_are_complete_closed_assets(self):
        payloads = self.stage()
        self.assertTrue(NEW_FILES <= set(payloads), "native GTK/panel theme not staged")
        self.assertTrue(all(eligible_path(name) for name in NEW_FILES))
        validate_ros_theme(payloads)
        inventory = json.loads((ROOT / "plasma/dependencies.json").read_bytes())
        self.assertTrue(NEW_FILES <= set(inventory["assetLicenses"]))
        for name in NEW_FILES:
            bad = dict(payloads)
            del bad[name]
            with self.subTest(missing=name), self.assertRaises(ValueError):
                validate_ros_theme(bad)

    def test_unreviewed_gtk_payload_and_external_css_are_rejected(self):
        payloads = self.stage()
        self.assertTrue(NEW_FILES <= set(payloads), "native GTK/panel theme not staged")
        for suffix in ("gtk-3.0/settings.ini", "gtk-4.0/unreviewed.css", "engine.so"):
            self.assertFalse(eligible_path(GTK_ROOT + suffix))
        for version in (3, 4):
            key = GTK_ROOT + f"gtk-{version}.0/gtk-dark.css"
            for extra in (b'\n@import url("https://example.invalid/style.css");',
                          b'\nwindow { background-image: url("file:///etc/shadow"); }',
                          b'\n@import "other.css";', b"x" * (64 * 1024)):
                bad = dict(payloads)
                bad[key] = (bad[key][0] + extra, 0o644)
                with self.subTest(version=version, extra=extra[:32]), self.assertRaises(ValueError):
                    validate_ros_theme(bad)

    def test_gtk_escaped_external_imports_and_urls_are_rejected(self):
        payloads = self.stage()
        for version in (3, 4):
            key = GTK_ROOT + f"gtk-{version}.0/gtk-dark.css"
            for extra in (br'@\69mport "other.css";',
                          br'window { background-image: u\72l("other.svg"); }'):
                bad = dict(payloads)
                bad[key] = (bad[key][0] + b"\n" + extra, 0o644)
                with self.subTest(version=version, extra=extra), self.assertRaises(ValueError):
                    validate_ros_theme(bad)

    def test_dock_adds_native_store_after_settings_only_when_installed(self):
        layout = (ROOT / "plasma/look-and-feel/contents/layouts/org.kde.plasma.desktop-layout.js").read_text()
        self.assertIn('if (applicationExists("org.gnome.Software.desktop"))', layout)
        self.assertIn('launchers.push("applications:org.gnome.Software.desktop");', layout)
        self.assertLess(layout.index('"applications:systemsettings.desktop"'),
                        layout.index('"applications:org.gnome.Software.desktop"'))

    def test_panel_theme_rejects_active_svg_and_live_blur(self):
        payloads = self.stage()
        self.assertTrue(NEW_FILES <= set(payloads), "native GTK/panel theme not staged")
        svg = PANEL_ROOT + "widgets/panel-background.svg"
        config = PANEL_ROOT + "plasmarc"
        tasks = PANEL_ROOT + "widgets/tasks.svg"
        variants = ((svg, payloads[svg][0].replace(b"<svg ", b'<svg onload="evil()" ', 1)),
                    (tasks, payloads[tasks][0].replace(b"<svg ", b'<svg onload="evil()" ', 1)),
                    (svg, payloads[svg][0].replace(b"<svg ", b"<g ", 1).replace(b"</svg>", b"</g>")),
                    (config, payloads[config][0].replace(b"enabled=false", b"enabled=true", 1)))
        for key, data in variants:
            bad = dict(payloads)
            bad[key] = (data, 0o644)
            with self.subTest(key=key), self.assertRaises(ValueError):
                validate_ros_theme(bad)

    def test_candidate_gtk_override_preserves_user_choice_and_does_not_write_home(self):
        source = (ROOT / "plasma/session/forge-kwin-session").read_text()
        self.assertIn('export GTK_THEME="${GTK_THEME:-ForgeROS:dark}"', source)
        self.assertNotRegex(source, r"\b(?:cp|mv|sed|gsettings|kwriteconfig|mkdir)\b|\.config/")

    def test_original_r_os_controls_follow_shared_geometry_and_order(self):
        tokens = json.loads((ROOT / "docs/design/r-os-tokens-v1.json").read_bytes())
        self.assertEqual(tokens["window"]["controlWidth"], 48)
        self.assertEqual(tokens["window"]["fusionControlWidth"], 40)
        self.assertEqual(tokens["window"]["cornerRadius"], 12)
        self.assertNotIn("controlDiameter", tokens["window"])
        config = (ROOT / "plasma/aurorae/ForgeDark/ForgeDarkrc").read_text()
        self.assertIn("LeftButtons=\nRightButtons=IAX\n", config)
        self.assertIn("ButtonWidth=48\n", config)
        qml = (ROOT / "plasma/plasmoids/org.forge.windowcontrols/contents/ui/main.qml").read_text()
        self.assertLess(qml.index("Controls.Label"), qml.index("id: minimizeButton"))
        self.assertLess(qml.index("id: minimizeButton"), qml.index("id: restoreButton"))
        self.assertLess(qml.index("id: restoreButton"), qml.index("id: closeButton"))
        self.assertNotIn("TrafficControl", qml)
        self.assertNotIn("dotColor", qml)
        for color in ("#ff5f57", "#febc2e", "#28c840"):
            self.assertNotIn(color, qml)
        self.assertIn("Layout.preferredWidth: 40", qml)
        self.assertIn('"#ef4444"', qml)

    def test_aurorae_glyphs_are_visible_in_normal_inactive_and_hover_states(self):
        for name in ("minimize", "maximize", "restore", "close"):
            tree = ET.fromstring((ROOT / f"plasma/aurorae/ForgeDark/{name}.svg").read_bytes())
            for state in ("active-center", "inactive-center", "hover-center", "pressed-center"):
                group = next(element for element in tree.iter() if element.attrib.get("id") == state)
                glyphs = [element for element in group.iter() if element.tag.endswith("path") or element.tag.endswith("line")]
                self.assertTrue(glyphs, f"{name} {state} glyph must be visible without hover")
                self.assertTrue(all(element.attrib.get("opacity", "1") != "0" for element in glyphs))
                hit = next(element for element in group if element.tag.endswith("rect"))
                self.assertEqual((hit.attrib.get("width"), hit.attrib.get("height")), ("48", "32"))

    def test_packaging_rejects_old_left_traffic_layout(self):
        from tools.build_plasma_bundle import WINDOW_REQUIRED, WINDOW_DECOR_ROOT, WINDOW_WIDGET_QML, WINDOW_WIDGET_METADATA, WINDOW_WIDGET_CONFIG, WINDOW_CATALOG
        payloads = {}
        for key in WINDOW_REQUIRED | {WINDOW_CATALOG}:
            if key.startswith(WINDOW_DECOR_ROOT):
                source = ROOT / "plasma/aurorae/ForgeDark" / key.removeprefix(WINDOW_DECOR_ROOT)
            elif key == WINDOW_WIDGET_QML:
                source = ROOT / "plasma/plasmoids/org.forge.windowcontrols/contents/ui/main.qml"
            elif key == WINDOW_WIDGET_METADATA:
                source = ROOT / "plasma/plasmoids/org.forge.windowcontrols/metadata.json"
            elif key == WINDOW_WIDGET_CONFIG:
                source = ROOT / "plasma/plasmoids/org.forge.windowcontrols/contents/config/main.xml"
            else:
                source = ROOT / "plasma/plasmoids/org.forge.windowcontrols/contents/locale/zh_CN/LC_MESSAGES/plasma_applet_org.forge.windowcontrols.mo"
            payloads[key] = (source.read_bytes(), 0o644)
        key = WINDOW_DECOR_ROOT + "ForgeDarkrc"
        payloads[key] = (b"[General]\nLeftButtons=XIA\nRightButtons=\n[Layout]\nTitleHeight=32\nButtonWidth=24\n", 0o644)
        with self.assertRaises(ValueError):
            validate_window_assets(payloads)

    def test_gtk_csd_buttons_use_original_width_and_close_hover(self):
        for version in (3, 4):
            css = (ROOT / f"plasma/ros-theme/gtk/gtk-{version}.0/gtk-dark.css").read_text()
            controls = css.split(".titlebar button.titlebutton", 1)[1]
            self.assertIn("min-width: 48px", controls)
            self.assertIn("min-height: 32px", controls)
            self.assertIn("button.titlebutton.close:hover", controls)
            self.assertIn("#ef4444", controls)

    def test_fusion_unavailable_maximize_button_is_hidden_instead_of_placeholder(self):
        qml = (ROOT / "plasma/plasmoids/org.forge.windowcontrols/contents/ui/main.qml").read_text()
        restore = qml.split("id: restoreButton", 1)[1].split("WindowControl {", 1)[0]
        self.assertIn("visible: enabled", restore,
                      "RowLayout must remove the unavailable maximize item, not leave a gray placeholder")

    def test_dock_icon_geometry_uses_supported_task_frame_margins(self):
        payloads = self.stage()
        self.assertTrue(NEW_FILES <= set(payloads), "native GTK/panel theme not staged")
        layout = (ROOT / "plasma/look-and-feel/contents/layouts/org.kde.plasma.desktop-layout.js").read_text()
        self.assertIn('dock.hiding = "dodgewindows";', layout)
        self.assertIn("topPanel.height = 32;", layout)
        self.assertIn("dock.height = 56;", layout)
        panel = ET.fromstring(payloads[PANEL_ROOT + "widgets/panel-background.svg"][0])
        tasks = ET.fromstring(payloads[PANEL_ROOT + "widgets/tasks.svg"][0])
        def height(tree, name):
            return int(next(element.attrib["height"] for element in tree.iter()
                            if element.attrib.get("id") == name))
        # The pinned iconTasks subtracts its frame margins from available height.
        self.assertEqual(56 - height(panel, "south-hint-top-margin")
                         - height(panel, "south-hint-bottom-margin")
                         - height(tasks, "normal-hint-top-margin")
                         - height(tasks, "normal-hint-bottom-margin"), 40)
        self.assertEqual(height(panel, "north-hint-top-margin")
                         + height(panel, "north-hint-bottom-margin"), 0,
                         "32px top panel must leave 32px content for Fusion controls")


if __name__ == "__main__":
    unittest.main()
