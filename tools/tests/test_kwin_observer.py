"""Execute the packaged KWin observer against its public signal boundary.

These tests exercise metadata publication, not KWin rendering or input delivery.
"""
import json
from pathlib import Path
import shutil
import subprocess
import unittest


ROOT = Path(__file__).resolve().parents[2]
SCRIPT = ROOT / "services/window-bridge/kwin-observer/contents/code/main.js"
HARNESS = r"""
const fs = require('fs');
const vm = require('vm');
const input = JSON.parse(fs.readFileSync(0, 'utf8'));
const published = [];
class Signal {
    constructor() { this.listeners = []; }
    connect(listener) { this.listeners.push(listener); }
    emit(...args) { for (const listener of this.listeners) listener(...args); }
}
const windows = {};
for (const spec of input.windows || []) {
    const window = Object.assign({internalId: spec.id, desktopWindow: false,
        dock: false, specialWindow: false, popupWindow: false, dialog: false,
        caption: 'Title', desktopFileName: 'org.example.App', transientFor: null,
        frameGeometry: {x: 0, y: 0, width: 640, height: 480}}, spec);
    for (const name of ['frameGeometryChanged', 'captionChanged', 'closed',
                        'transientChanged', 'desktopFileNameChanged']) {
        window[name] = new Signal();
    }
    windows[spec.id] = window;
}
for (const window of Object.values(windows)) {
    if (typeof window.transientFor === 'string') window.transientFor = windows[window.transientFor];
}
const workspace = {windowAdded: new Signal(), windowActivated: new Signal(),
    activeWindow: input.active === null ? null : windows[input.active],
    windowList: () => (input.initial || []).map(id => windows[id])};
const context = {workspace, callDBus: (service, path, interfaceName, method, encoded) => {
    if (service !== 'org.forge.WindowObserver1' || path !== '/WindowObserver' ||
        interfaceName !== 'org.forge.WindowObserver1' || method !== 'Observe') {
        throw new Error('Unexpected DBus endpoint');
    }
    published.push(JSON.parse(encoded));
}};
vm.runInNewContext(input.source, context);
for (const action of input.actions || []) {
    const window = windows[action.id];
    if (action.type === 'activate') {
        workspace.activeWindow = action.id === null ? null : window;
        workspace.windowActivated.emit(workspace.activeWindow);
    } else if (action.type === 'add') {
        workspace.windowAdded.emit(window);
    } else if (action.type === 'change') {
        const value = action.property === 'transientFor' && action.value !== null
            ? windows[action.value] : action.value;
        window[action.property] = value;
        window[action.signal].emit();
    } else if (action.type === 'close') {
        window.closed.emit();
    } else {
        throw new Error('Unexpected harness action');
    }
}
process.stdout.write(JSON.stringify(published));
"""


class KWinObserverTests(unittest.TestCase):
    def execute(self, *, windows=None, initial=None, active=None, actions=None):
        node = shutil.which("node")
        if not node:
            self.skipTest("Node is required to execute the packaged KWin observer")
        result = subprocess.run([node, "-e", HARNESS], input=json.dumps({
            "source": SCRIPT.read_text(encoding="utf-8"), "windows": windows or [],
            "initial": initial or [], "active": active, "actions": actions or []}),
            text=True, capture_output=True, check=True, timeout=10)
        return json.loads(result.stdout)

    def test_startup_publishes_existing_windows_before_current_activity(self):
        events = self.execute(windows=[{"id": "{one}"}, {"id": "{two}"}],
                              initial=["{one}", "{two}"], active="{two}")
        self.assertEqual([event["type"] for event in events], ["window", "window", "active"])
        self.assertEqual([event["id"] for event in events], ["{one}", "{two}", "{two}"])

    def test_startup_without_eligible_active_window_explicitly_clears(self):
        for current in (None, "desktop", "dock", "special"):
            with self.subTest(current=current):
                events = self.execute(windows=[{"id": "desktop", "desktopWindow": True},
                    {"id": "dock", "dock": True}, {"id": "special", "specialWindow": True}],
                    initial=["desktop", "dock", "special"], active=current)
                self.assertEqual(events, [{"type": "active", "id": None}])

    def test_each_activation_reports_eligible_identity_or_explicit_null(self):
        events = self.execute(windows=[{"id": "normal"}, {"id": "dialog", "dialog": True},
            {"id": "popup", "popupWindow": True, "specialWindow": True},
            {"id": "desktop", "desktopWindow": True}, {"id": "dock", "dock": True},
            {"id": "special", "specialWindow": True}], actions=[
                {"type": "activate", "id": id} for id in
                ("normal", None, "desktop", "dock", "special", "dialog", "popup")])
        self.assertEqual(events, [{"type": "active", "id": id} for id in
                                 (None, "normal", None, None, None, None, "dialog", "popup")])

    def test_public_transient_changes_publish_new_parent_without_changing_identity(self):
        events = self.execute(windows=[{"id": "parent"}, {"id": "other"},
            {"id": "child", "dialog": True, "transientFor": "parent"}],
            initial=["parent", "other", "child"], actions=[
                {"type": "change", "id": "child", "property": "transientFor",
                 "value": "other", "signal": "transientChanged"},
                {"type": "change", "id": "child", "property": "transientFor",
                 "value": None, "signal": "transientChanged"}])
        child = [event for event in events if event.get("id") == "child"]
        self.assertEqual([event["parent"] for event in child], ["parent", "other", None])
        self.assertTrue(all(event["kind"] == "dialog" for event in child))

    def test_public_app_id_changes_publish_fresh_advisory_hint(self):
        events = self.execute(windows=[{"id": "normal"}], initial=["normal"], actions=[
            {"type": "change", "id": "normal", "property": "desktopFileName",
             "value": "org.example.Changed", "signal": "desktopFileNameChanged"}])
        observations = [event for event in events if event["type"] == "window"]
        self.assertEqual([event["app_id"] for event in observations],
                         ["org.example.App", "org.example.Changed"])
        self.assertEqual(observations[0]["id"], observations[1]["id"])

    def test_existing_geometry_caption_added_and_closed_signals_remain_observations(self):
        events = self.execute(windows=[{"id": "later"}], actions=[
            {"type": "add", "id": "later"},
            {"type": "activate", "id": "later"},
            {"type": "change", "id": "later", "property": "caption",
             "value": "Changed", "signal": "captionChanged"},
            {"type": "change", "id": "later", "property": "frameGeometry",
             "value": {"x": 1.4, "y": 2.6, "width": 640.4, "height": 480.4},
             "signal": "frameGeometryChanged"},
            {"type": "close", "id": "later"}])
        self.assertEqual([event["type"] for event in events],
                         ["active", "window", "active", "window", "window", "closed"])
        self.assertEqual(events[1]["id"], "later", "Added window must be observed before activation")
        self.assertEqual(events[2], {"type": "active", "id": "later"})
        self.assertEqual(events[3]["caption"], "Changed")
        self.assertEqual(events[4]["geometry"], {"x": 1, "y": 3, "width": 640, "height": 480})
        self.assertEqual(events[-1], {"type": "closed", "id": "later"})


if __name__ == "__main__":
    unittest.main()
