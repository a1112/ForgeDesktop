import QtQuick
import QtTest
import org.kde.taskmanager as TaskManager
import org.kde.plasma.plasmoid
TestCase {
    name: "WindowControls"
    when: windowShown
    visible: true
    width: 400
    height: 100
    property var applet
    property var tasks
    property var buttons

    function windowRow(identity) {
        let row = {};
        row[Qt.DisplayRole] = "Test window";
        row[TaskManager.AbstractTasksModel.AppId] = "org.forge.test.desktop";
        for (const role of [TaskManager.AbstractTasksModel.IsWindow,
                            TaskManager.AbstractTasksModel.IsActive,
                            TaskManager.AbstractTasksModel.IsMaximized,
                            TaskManager.AbstractTasksModel.CanSetNoBorder,
                            TaskManager.AbstractTasksModel.HasNoBorder,
                            TaskManager.AbstractTasksModel.IsMinimizable,
                            TaskManager.AbstractTasksModel.IsMaximizable,
                            TaskManager.AbstractTasksModel.IsClosable]) {
            row[role] = true;
        }
        row[TaskManager.AbstractTasksModel.IsFullScreen] = false;
        row[TaskManager.AbstractTasksModel.IsMinimized] = false;
        row[TaskManager.AbstractTasksModel.WinIdList] = [identity];
        return row;
    }

    function controlItems(item, result) {
        if (item.down !== undefined && item.text !== undefined) {
            result[item.text === "−" ? "minimize" : item.text === "▣" ? "restore" : "close"] = item;
        }
        for (const child of item.children || []) {
            controlItems(child, result);
        }
    }

    function init() {
        const component = Qt.createComponent("../../../plasma/plasmoids/org.forge.windowcontrols/contents/ui/main.qml");
        compare(component.status, Component.Ready, component.errorString());
        applet = component.createObject(this, { width: 120, height: 32 });
        verify(applet !== null);
        tasks = findChild(applet, "windowControlsTestTasks");
        verify(tasks !== null);
        tasks.rows = [windowRow("9cf0e382-caa6-4b59-8758-7e90e398ab01"), windowRow("9cf0e382-caa6-4b59-8758-7e90e398ab02")];
        tasks.activeTask = 0;
        tasks.modelReset();
        buttons = {};
        controlItems(applet, buttons);
        verify(buttons.minimize !== undefined);
        verify(buttons.restore !== undefined);
        verify(buttons.close !== undefined);
        wait(0);
        tryCompare(applet, "fused", true);
        verify(waitForRendering(applet));
        verify(buttons.minimize.x < buttons.restore.x);
        verify(buttons.restore.x < buttons.close.x);
    }

    function cleanup() {
        applet.destroy();
        applet = null;
        tasks = null;
        buttons = null;
        wait(0);
    }

    function actionData() {
        return [{ tag: "minimize", action: "minimize" }, { tag: "restore", action: "restore" }, { tag: "close", action: "close" }];
    }
    function capabilityRole(action) {
        return action === "minimize" ? TaskManager.AbstractTasksModel.IsMinimizable
             : action === "restore" ? TaskManager.AbstractTasksModel.IsMaximizable
             : TaskManager.AbstractTasksModel.IsClosable;
    }

    function test_pointerSameWindow_data() { return actionData(); }
    function test_pointerSameWindow(data) {
        mouseClick(buttons[data.action], 20, 16);
        compare(tasks.requests.length, 1);
        compare(tasks.requests[0].action, data.action);
        compare(tasks.requests[0].index, 0);
    }

    function test_pointerSwitchCannotActOnAnotherWindow_data() { return actionData(); }
    function test_pointerSwitchCannotActOnAnotherWindow(data) {
        const button = buttons[data.action];
        mousePress(button, 20, 16);
        verify(button.down);
        tasks.activeTask = 1;
        mouseRelease(button, 20, 16);
        compare(tasks.requests.length, 0, "a released press for A must never act on B");
    }

    function test_rowReuseCannotActOnNewIdentity_data() { return actionData(); }
    function test_rowReuseCannotActOnNewIdentity(data) {
        const button = buttons[data.action];
        mousePress(button, 20, 16);
        tasks.rows[0][TaskManager.AbstractTasksModel.WinIdList] = ["9cf0e382-caa6-4b59-8758-7e90e398ab03"];
        tasks.dataChanged();
        mouseRelease(button, 20, 16);
        compare(tasks.requests.length, 0, "the same model row is not the same window");
    }

    function test_capabilitySignalsRefreshEnabled_data() { return actionData(); }
    function test_capabilitySignalsRefreshEnabled(data) {
        const role = capabilityRole(data.action);
        const button = buttons[data.action];
        compare(button.enabled, true);
        const serial = applet.modelSerial;
        tasks.rows[0][role] = false;
        tasks.dataChanged();
        compare(applet.modelSerial, serial + 1);
        compare(applet.fused, true);
        compare(button.enabled, false);
        tasks.rows[0][role] = true;
        tasks.dataChanged();
        compare(button.enabled, true);
    }

    function test_capabilityLostWhilePressed_data() { return actionData(); }
    function test_capabilityLostWhilePressed(data) {
        const button = buttons[data.action];
        mousePress(button, 20, 16);
        tasks.rows[0][capabilityRole(data.action)] = false;
        tasks.dataChanged();
        mouseRelease(button, 20, 16);
        compare(tasks.requests.length, 0);
    }

    function test_cancelledPressDoesNotSurvive() {
        const button = buttons.close;
        mousePress(button, 20, 16);
        mouseMove(button, 200, 16);
        mouseRelease(button, 200, 16);
        compare(tasks.requests.length, 0);
        button.clicked();
        compare(tasks.requests.length, 0, "a cancelled press cannot authorize a click");
        tasks.activeTask = 1;
        mouseClick(button, 20, 16);
        compare(tasks.requests.length, 1);
        compare(tasks.requests[0].index, 1);
    }

    function test_keyboardSameWindow_data() { return actionData(); }
    function test_keyboardSameWindow(data) {
        buttons[data.action].forceActiveFocus();
        keyClick(Qt.Key_Space);
        compare(tasks.requests.length, 1);
        compare(tasks.requests[0].action, data.action);
        compare(tasks.requests[0].index, 0);
    }

    function test_keyboardSwitchCannotActOnAnotherWindow() {
        buttons.close.forceActiveFocus();
        keyPress(Qt.Key_Space);
        tasks.activeTask = 1;
        keyRelease(Qt.Key_Space);
        compare(tasks.requests.length, 0);
    }

    function test_invalidIdentity_data() {
        return [
            { tag: "missing", ids: undefined }, { tag: "empty", ids: [] },
            { tag: "multiple", ids: ["a", "b"] }, { tag: "null", ids: [null] },
            { tag: "object", ids: [{}] }, { tag: "boolean", ids: [true] },
            { tag: "emptyString", ids: [""] }, { tag: "notUuid", ids: ["undefined"] },
            { tag: "numericString", ids: ["123"] }, { tag: "fraction", ids: [1.5] },
            { tag: "nullUuid", ids: ["00000000-0000-0000-0000-000000000000"] },
            { tag: "unmatchedBrace", ids: ["{9cf0e382-caa6-4b59-8758-7e90e398ab01"] },
            { tag: "objectAsList", ids: ({ 0: "9cf0e382-caa6-4b59-8758-7e90e398ab01", length: 1 }) },
            { tag: "negative", ids: [-1] }, { tag: "zero", ids: [0] },
            { tag: "unsafeNumber", ids: [9007199254740992] },
            { tag: "notNumber", ids: [NaN] }, { tag: "infinity", ids: [Infinity] }
        ];
    }
    function test_invalidIdentity(data) {
        tasks.rows[0][TaskManager.AbstractTasksModel.WinIdList] = data.ids;
        tasks.dataChanged();
        mouseClick(buttons.close, 20, 16);
        compare(tasks.requests.length, 0, "invalid or ambiguous identities fail closed");
    }

    function test_numericX11Identity() {
        tasks.rows[0][TaskManager.AbstractTasksModel.WinIdList] = [4294967295];
        tasks.dataChanged();
        mouseClick(buttons.close, 20, 16);
        compare(tasks.requests.length, 1);
    }

    function test_uuidEquivalentPublicForms() {
        mousePress(buttons.close, 20, 16);
        tasks.rows[0][TaskManager.AbstractTasksModel.WinIdList] = ["{9CF0E382-CAA6-4B59-8758-7E90E398AB01}"];
        tasks.dataChanged();
        mouseRelease(buttons.close, 20, 16);
        compare(tasks.requests.length, 1);
    }

    function test_cppPublicListCompatibility_data() {
        return [{ tag: "wayland", ids: Plasmoid.configuration.waylandIds() },
                { tag: "x11", ids: Plasmoid.configuration.x11Ids() }];
    }
    function test_cppPublicListCompatibility(data) {
        tasks.rows[0][TaskManager.AbstractTasksModel.WinIdList] = data.ids;
        tasks.dataChanged();
        mouseClick(buttons.close, 20, 16);
        compare(tasks.requests.length, 1, "Qt C++ QVariantList identities must work through the real QML engine");
    }

    function test_accessibleSameWindow_data() { return actionData(); }
    function test_accessibleSameWindow(data) {
        verify(Plasmoid.configuration.accessiblePress(buttons[data.action]), "Qt accessible press action must be available");
        compare(tasks.requests.length, 1, "a screen-reader action must dispatch exactly once without a pointer press");
        compare(tasks.requests[0].action, data.action);
        compare(tasks.requests[0].index, 0);
    }

    function test_accessibleDisabled_data() { return actionData(); }
    function test_accessibleDisabled(data) {
        tasks.rows[0][capabilityRole(data.action)] = false;
        tasks.dataChanged();
        verify(Plasmoid.configuration.accessiblePress(buttons[data.action]));
        compare(tasks.requests.length, 0);
    }

    function test_accessibleIneligible() {
        tasks.rows[0][TaskManager.AbstractTasksModel.IsFullScreen] = true;
        tasks.dataChanged();
        verify(Plasmoid.configuration.accessiblePress(buttons.close));
        compare(tasks.requests.length, 0);
    }

    function test_accessibleConsumesOldPointerIntent() {
        mousePress(buttons.close, 20, 16);
        tasks.activeTask = 1;
        verify(Plasmoid.configuration.accessiblePress(buttons.close));
        compare(tasks.requests.length, 1);
        compare(tasks.requests[0].index, 1);
        mouseRelease(buttons.close, 20, 16);
        compare(tasks.requests.length, 1, "the old pointer release must not dispatch a second action");
        buttons.close.clicked();
        compare(tasks.requests.length, 1, "the accessibility action must not leave an armed token");
    }

    function test_readsExactlyOnePublicIdentityPerPhase() {
        tasks.roleReads[TaskManager.AbstractTasksModel.WinIdList] = 0;
        mousePress(buttons.close, 20, 16);
        compare(tasks.roleReads[TaskManager.AbstractTasksModel.WinIdList], 1);
        mouseRelease(buttons.close, 20, 16);
        compare(tasks.roleReads[TaskManager.AbstractTasksModel.WinIdList], 2);
        compare(tasks.requests.length, 1);
        buttons.close.clicked();
        compare(tasks.requests.length, 1, "a consumed press must not be reusable");
    }

    function test_typedIdentityDoesNotMatchDifferentType() {
        tasks.rows[0][TaskManager.AbstractTasksModel.WinIdList] = [123];
        tasks.dataChanged();
        mousePress(buttons.close, 20, 16);
        tasks.rows[0][TaskManager.AbstractTasksModel.WinIdList] = ["123"];
        tasks.dataChanged();
        mouseRelease(buttons.close, 20, 16);
        compare(tasks.requests.length, 0);
    }

    function test_ineligibleWhilePressed_data() {
        return [
            { tag: "restored", role: TaskManager.AbstractTasksModel.IsMaximized, value: false },
            { tag: "fullscreen", role: TaskManager.AbstractTasksModel.IsFullScreen, value: true },
            { tag: "minimized", role: TaskManager.AbstractTasksModel.IsMinimized, value: true }
        ];
    }
    function test_ineligibleWhilePressed(data) {
        mousePress(buttons.close, 20, 16);
        tasks.rows[0][data.role] = data.value;
        tasks.dataChanged();
        mouseRelease(buttons.close, 20, 16);
        compare(tasks.requests.length, 0);
    }
}
