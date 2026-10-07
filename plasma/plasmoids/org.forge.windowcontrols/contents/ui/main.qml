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
    Layout.minimumWidth: fused ? 270 : 0
    Layout.preferredWidth: fused ? 270 : 0
    Layout.maximumWidth: fused ? 270 : 0
    implicitWidth: fused ? 270 : 0
    visible: fused

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

    function actOnActiveTask(action) {
        const index = tasks.activeTask;
        if (!eligible(index)) {
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
    component TrafficControl: Controls.Button {
        id: control
        required property color dotColor
        Layout.preferredWidth: 24
        Layout.preferredHeight: 32
        padding: 0
        opacity: enabled ? 1 : 0.4
        Controls.ToolTip.text: Accessible.name
        Controls.ToolTip.visible: hovered
        Controls.ToolTip.delay: 500
        contentItem: Item {
            Rectangle {
                anchors.centerIn: parent
                width: 12
                height: 12
                radius: 6
                color: control.dotColor
                scale: control.pressed ? 0.86 : 1
                Text {
                    anchors.centerIn: parent
                    text: control.text
                    color: "#171a21"
                    font.pixelSize: 11
                    visible: control.hovered || control.activeFocus
                }
            }
        }
        background: Rectangle {
            color: "transparent"
            radius: 6
            border.width: control.activeFocus ? 1 : 0
            border.color: "#60a5fa"
        }
    }

    RowLayout {
        anchors.fill: parent
        spacing: 0

        TrafficControl {
            id: closeButton
            text: "×"
            dotColor: "#ff5f57"
            enabled: root.fused && tasks.data(tasks.activeTask,
                TaskManager.AbstractTasksModel.IsClosable) === true
            Accessible.name: i18n("Close active window")
            onClicked: root.actOnActiveTask("close")
        }

        TrafficControl {
            id: minimizeButton
            text: "−"
            dotColor: "#febc2e"
            enabled: root.fused && tasks.data(tasks.activeTask,
                TaskManager.AbstractTasksModel.IsMinimizable) === true
            Accessible.name: i18n("Minimize active window")
            onClicked: root.actOnActiveTask("minimize")
        }

        TrafficControl {
            id: restoreButton
            text: "▣"
            dotColor: "#28c840"
            enabled: root.fused && tasks.data(tasks.activeTask,
                TaskManager.AbstractTasksModel.IsMaximizable) === true
            Accessible.name: i18n("Restore active window")
            onClicked: root.actOnActiveTask("restore")
        }

        Controls.Label {
            Layout.fillWidth: true
            Layout.minimumWidth: 0
            Layout.leftMargin: 8
            text: root.activeTitle
            color: "#e5e7eb"
            elide: Text.ElideRight
            verticalAlignment: Text.AlignVCenter
            Accessible.name: i18n("Active window: %1", text)
        }
    }
}
