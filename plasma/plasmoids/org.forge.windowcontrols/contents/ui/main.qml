import QtQuick
import QtQuick.Controls as Controls
import QtQuick.Layouts
import org.kde.plasma.core as PlasmaCore
import org.kde.plasma.plasmoid
import org.kde.taskmanager as TaskManager

PlasmoidItem {
    id: root

    Plasmoid.title: i18n("Window controls")
    Plasmoid.backgroundHints: PlasmaCore.Types.NoBackground
    Layout.minimumWidth: fused && showControls ? controlsWidth : 0
    Layout.preferredWidth: root.preferredWidth
    Layout.maximumWidth: root.preferredWidth
    implicitWidth: root.preferredWidth
    visible: fused

    // Existing custom applets retain combined mode; the Forge default layout
    // places title and controls in separate instances at the panel's two ends.
    readonly property string displayRole: ["title", "controls"].includes(Plasmoid.configuration.displayRole)
        ? Plasmoid.configuration.displayRole : "combined"
    readonly property bool showTitle: displayRole !== "controls"
    readonly property bool showControls: displayRole !== "title"
    readonly property bool canMinimize: {
        modelSerial;
        return fused && tasks.data(tasks.activeTask,
            TaskManager.AbstractTasksModel.IsMinimizable) === true;
    }
    readonly property bool canRestore: {
        modelSerial;
        return fused && tasks.data(tasks.activeTask,
            TaskManager.AbstractTasksModel.IsMaximizable) === true;
    }
    readonly property bool canClose: {
        modelSerial;
        return fused && tasks.data(tasks.activeTask,
            TaskManager.AbstractTasksModel.IsClosable) === true;
    }
    readonly property int controlsWidth: canRestore ? 120 : 80
    readonly property int preferredWidth: fused ? (showTitle ? 270 : controlsWidth) : 0

    // TasksModel emits state changes; the serial makes data() bindings refresh.
    property int modelSerial: 0
    // These clients draw their own title controls. Keep one set of buttons.
    readonly property var clientDecoratedAppIds: ["firefox.desktop"]
    readonly property bool fused: {
        modelSerial;
        return eligible(tasks.activeTask);
    }
    readonly property string activeTitle: {
        modelSerial;
        return fused ? String(tasks.data(tasks.activeTask, Qt.DisplayRole) || "") : "";
    }

    function clientDecorated(index) {
        const appId = String(tasks.data(index,
            TaskManager.AbstractTasksModel.AppId) || "").toLowerCase();
        return clientDecoratedAppIds.includes(appId);
    }

    function eligible(index) {
        return tasks.data(index, TaskManager.AbstractTasksModel.IsWindow) === true
            && tasks.data(index, TaskManager.AbstractTasksModel.IsActive) === true
            && tasks.data(index, TaskManager.AbstractTasksModel.IsMaximized) === true
            && tasks.data(index, TaskManager.AbstractTasksModel.IsFullScreen) !== true
            && tasks.data(index, TaskManager.AbstractTasksModel.IsMinimized) !== true
            && tasks.data(index, TaskManager.AbstractTasksModel.CanSetNoBorder) === true
            && tasks.data(index, TaskManager.AbstractTasksModel.HasNoBorder) === true
            && !clientDecorated(index);
    }

    function windowIdentity(index) {
        const ids = tasks.data(index, TaskManager.AbstractTasksModel.WinIdList);
        // Qt QVariantList sequences inherit Array's prototype but are not
        // necessarily reported as arrays by Array.isArray().
        if (!ids || typeof ids !== "object" || !Array.prototype.isPrototypeOf(ids)
                || ids.constructor !== Array || ids.length !== 1) {
            return "";
        }
        const id = ids[0];
        if (typeof id === "string") {
            const uuid = /^\{([0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12})\}$/i.exec(id)
                || /^([0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12})$/i.exec(id);
            if (uuid && uuid[1] !== "00000000-0000-0000-0000-000000000000") {
                return "uuid:" + uuid[1].toLowerCase();
            }
        } else if (typeof id === "number" && Number.isSafeInteger(id) && id > 0) {
            return "x11:" + id;
        }
        return "";
    }

    // Bind a press to one public window ID, not a model row that may be reused.
    // This is same-process UI intent, not a cross-process authorization token.
    function captureActiveIdentity() {
        const index = tasks.activeTask;
        return eligible(index) ? windowIdentity(index) : "";
    }

    function actOnActiveTask(action, pressedIdentity) {
        const index = tasks.activeTask;
        if (!pressedIdentity || !eligible(index) || windowIdentity(index) !== pressedIdentity) {
            return;
        }
        if (action === "minimize"
                && tasks.data(index, TaskManager.AbstractTasksModel.IsMinimizable) === true) {
            tasks.requestToggleMinimized(index);
        } else if (action === "restore"
                && tasks.data(index, TaskManager.AbstractTasksModel.IsMaximizable) === true) {
            tasks.requestToggleMaximized(index);
        } else if (action === "close"
                && tasks.data(index, TaskManager.AbstractTasksModel.IsClosable) === true) {
            tasks.requestClose(index);
        }
    }

    TaskManager.TasksModel {
        id: tasks
        groupMode: TaskManager.TasksModel.GroupDisabled
        sortMode: TaskManager.TasksModel.SortDisabled
        separateLaunchers: false
    }

    Connections {
        target: tasks
        function onActiveTaskChanged() { root.modelSerial++; }
        function onDataChanged() { root.modelSerial++; }
        function onRowsInserted() { root.modelSerial++; }
        function onRowsRemoved() { root.modelSerial++; }
        function onModelReset() { root.modelSerial++; }
    }

    // A fixed-width panel applet needs visual children on the PlasmoidItem.
    // The pinned Plasma runtime does not instantiate compactRepresentation here.
    component WindowControl: Controls.Button {
        id: control
        property bool closeControl: false
        property string controlAction
        property string pressedIdentity: ""
        onPressed: pressedIdentity = root.captureActiveIdentity()
        onCanceled: pressedIdentity = ""
        onClicked: {
            const identity = pressedIdentity;
            pressedIdentity = "";
            root.actOnActiveTask(controlAction, identity);
        }
        Accessible.onPressAction: {
            // Assistive actions are instantaneous and do not emit pressed().
            // Consume any older pointer press before resolving this new intent.
            pressedIdentity = "";
            if (enabled && visible) {
                root.actOnActiveTask(controlAction, root.captureActiveIdentity());
            }
        }
        Layout.minimumWidth: 40
        Layout.preferredWidth: 40
        Layout.maximumWidth: 40
        Layout.preferredHeight: 32
        padding: 0
        opacity: enabled ? 1 : 0.4
        Controls.ToolTip.text: Accessible.name
        Controls.ToolTip.visible: hovered
        Controls.ToolTip.delay: 500
        contentItem: Text {
            text: control.text
            color: control.hovered ? "#ffffff" : "#9ca3af"
            horizontalAlignment: Text.AlignHCenter
            verticalAlignment: Text.AlignVCenter
            font.pixelSize: 14
        }
        background: Rectangle {
            color: control.hovered ? (control.closeControl ? "#ef4444" : "#1affffff") : "transparent"
            radius: 0
            border.width: control.activeFocus ? 1 : 0
            border.color: "#60a5fa"
        }
    }

    RowLayout {
        anchors.fill: parent
        spacing: 0

        Controls.Label {
            visible: root.showTitle
            Layout.fillWidth: true
            Layout.minimumWidth: 0
            text: root.activeTitle
            color: "#e5e7eb"
            elide: Text.ElideRight
            verticalAlignment: Text.AlignVCenter
            Accessible.name: i18n("Active window: %1", text)
        }

        WindowControl {
            id: minimizeButton
            visible: root.showControls
            text: "−"
            controlAction: "minimize"
            enabled: root.canMinimize
            Accessible.name: i18n("Minimize active window")
        }

        WindowControl {
            id: restoreButton
            text: "▣"
            controlAction: "restore"
            enabled: root.canRestore
            visible: enabled && root.showControls
            Accessible.name: i18n("Restore active window")
        }

        WindowControl {
            id: closeButton
            visible: root.showControls
            text: "×"
            controlAction: "close"
            closeControl: true
            enabled: root.canClose
            Accessible.name: i18n("Close active window")
        }
    }
}
