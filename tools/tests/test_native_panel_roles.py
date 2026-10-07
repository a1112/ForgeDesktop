"""Execute real layout/migration JavaScript against the public Plasma API boundary."""
import importlib.machinery
import importlib.util
import json
from pathlib import Path
import shutil
import subprocess
import unittest
import xml.etree.ElementTree as ET

from tools.build_plasma_bundle import eligible_path, validate_window_assets

ROOT = Path(__file__).resolve().parents[2]
WIDGET = "org.forge.windowcontrols"
CONFIG = "usr/share/plasma/plasmoids/org.forge.windowcontrols/contents/config/main.xml"
OLD_ORDER = ["org.kde.plasma.kickoff", WIDGET, "org.kde.plasma.pager",
             "org.kde.plasma.panelspacer", "org.kde.plasma.digitalclock",
             "org.kde.plasma.panelspacer", "org.kde.plasma.systemtray"]

# These objects model the documented public scripting API, not QML rendering.
# Execute the actual packaged scripts so accidental reset/reorder is observable.
HARNESS = r"""
const fs = require('fs');
const vm = require('vm');
const input = JSON.parse(fs.readFileSync(0, 'utf8'));
const all = [];
class Widget {
    constructor(type, index, config = {}) {
        this.type = type; this.index = index; this.config = config;
        this.currentConfigGroup = []; this.reloads = 0;
    }
    readConfig(key, fallback) { return Object.hasOwn(this.config, key) ? this.config[key] : fallback; }
    writeConfig(key, value) { this.config[key] = value; }
    reloadConfig() { this.reloads++; }
}
class Panel {
    constructor(spec = {}) {
        this.type = 'org.kde.panel'; this.location = 'top'; this.height = 32;
        this.floating = false; this.hiding = 'none'; this.items = []; all.push(this);
        Object.assign(this, spec);
        this.items = (spec.items || []).map((item, index) => new Widget(item.type, index, item.config));
    }
    addWidget(type) { const widget = new Widget(type, this.items.length); this.items.push(widget); return widget; }
    widgets() { return [...this.items].reverse(); } // Enumeration order is not visual order.
}
for (const spec of input.panels || []) new Panel(spec);
const context = { Panel, panels: () => all, desktopsForActivity: () => [],
    currentActivity: () => '', applicationExists: () => false,
    knownWidgetTypes: ['org.forge.windowcontrols'] };
for (let run = 0; run < input.runs; run++) vm.runInNewContext(input.source, context);
process.stdout.write(JSON.stringify(all));
"""


class NativePanelRoleTests(unittest.TestCase):
    def execute(self, source, panels=None, runs=1):
        node = shutil.which("node")
        if not node:
            self.skipTest("Node is required to execute Plasma layout JavaScript")
        result = subprocess.run([node, "-e", HARNESS], input=json.dumps({
            "source": source, "panels": panels or [], "runs": runs}),
            text=True, capture_output=True, check=True, timeout=10)
        return json.loads(result.stdout)

    def migration(self):
        loader = importlib.machinery.SourceFileLoader("native_panel_style", str(ROOT / "plasma/session/forge-native-style"))
        module = importlib.util.module_from_spec(importlib.util.spec_from_loader(loader.name, loader))
        loader.exec_module(module)
        return getattr(module, "PANEL_MIGRATION_SCRIPT", "")

    def old_panel(self, **changes):
        panel = {"items": [{"type": name, "config": {}} for name in OLD_ORDER]}
        panel.update(changes)
        return panel

    def test_fresh_layout_puts_control_only_instance_after_system_tray(self):
        source = (ROOT / "plasma/look-and-feel/contents/layouts/org.kde.plasma.desktop-layout.js").read_text()
        panel, dock = self.execute(source)
        self.assertEqual([item["type"] for item in panel["items"]], OLD_ORDER + [WIDGET],
                         "Fusion controls must be the last panel item, after clock and system tray")
        self.assertEqual(panel["items"][1]["config"].get("displayRole"), "title")
        self.assertEqual(panel["items"][-1]["config"].get("displayRole"), "controls")
        self.assertEqual(dock["location"], "bottom")

    def test_exact_old_panel_migration_appends_controls_and_is_idempotent(self):
        panel, = self.execute(self.migration(), [self.old_panel()], runs=2)
        self.assertEqual([item["type"] for item in panel["items"]], OLD_ORDER + [WIDGET])
        self.assertEqual(panel["items"][1]["config"].get("displayRole"), "title")
        self.assertEqual(panel["items"][-1]["config"].get("displayRole"), "controls")
        self.assertEqual(panel["items"][1]["reloads"], 1)

    def test_custom_panels_and_non_default_roles_are_preserved(self):
        extra = self.old_panel()
        extra["items"].append({"type": "org.kde.plasma.showdesktop", "config": {}})
        reordered = self.old_panel()
        reordered["items"][0], reordered["items"][2] = reordered["items"][2], reordered["items"][0]
        custom_role = self.old_panel()
        custom_role["items"][1]["config"]["displayRole"] = "title"
        cases = [extra, reordered, custom_role, self.old_panel(height=40),
                 self.old_panel(location="bottom"), self.old_panel(floating=True),
                 self.old_panel(hiding="autohide")]
        baseline = self.execute("", cases)
        self.assertEqual(self.execute(self.migration(), cases, runs=2), baseline)

    def test_top_panel_side_margins_do_not_inset_far_right_close_button(self):
        tree = ET.fromstring((ROOT / "plasma/ros-theme/desktoptheme/widgets/panel-background.svg").read_bytes())
        widths = {element.attrib.get("id"): element.attrib.get("width") for element in tree.iter()}
        self.assertEqual(widths["north-hint-left-margin"], "0")
        self.assertEqual(widths["north-hint-right-margin"], "0")
        self.assertEqual(widths["south-hint-right-margin"], "6", "Dock geometry must remain intact")

    def test_qml_roles_hide_the_other_part_and_control_width_shrinks_without_maximize(self):
        qml = (ROOT / "plasma/plasmoids/org.forge.windowcontrols/contents/ui/main.qml").read_text()
        self.assertIn('Plasmoid.configuration.displayRole', qml)
        label = qml.split("Controls.Label {", 1)[1].split("WindowControl {", 1)[0]
        self.assertIn("visible: root.showTitle", label)
        for name in ("minimizeButton", "closeButton"):
            control = qml.split("id: " + name, 1)[1].split("WindowControl {", 1)[0]
            self.assertIn("visible: root.showControls", control)
        self.assertIn("canRestore ? 120 : 80", qml,
                      "control-only instance must not reserve the hidden maximize slot")

    def test_role_config_is_a_closed_required_asset(self):
        self.assertTrue(eligible_path(CONFIG), "KConfig roles need an explicit producer allowlist path")
        from tools.build_plasma_bundle import WINDOW_REQUIRED
        self.assertIn(CONFIG, WINDOW_REQUIRED)
        payloads = {}
        for directory, prefix in (("plasma/aurorae/ForgeDark", "usr/share/aurorae/themes/ForgeDark/"),
                                  ("plasma/plasmoids/org.forge.windowcontrols", "usr/share/plasma/plasmoids/org.forge.windowcontrols/")):
            for source in (ROOT / directory).rglob("*"):
                if source.is_file() and not source.name.endswith(".po"):
                    payloads[prefix + source.relative_to(ROOT / directory).as_posix()] = (source.read_bytes(), 0o644)
        validate_window_assets(payloads)
        del payloads[CONFIG]
        with self.assertRaises(ValueError):
            validate_window_assets(payloads)
        source = (ROOT / "plasma/plasmoids/org.forge.windowcontrols/contents/config/main.xml").read_bytes()
        for bad in (source.replace(b"combined", b"controls"), source + b"<!-- unreviewed -->", b'<!DOCTYPE kcfg [<!ENTITY x "bad">]><kcfg/>'):
            with self.subTest(bad=bad[:60]), self.assertRaises(ValueError):
                validate_window_assets({**payloads, CONFIG: (bad, 0o644)})


if __name__ == "__main__":
    unittest.main()
