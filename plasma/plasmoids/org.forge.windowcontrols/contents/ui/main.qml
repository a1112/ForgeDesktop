import QtQuick
import QtQuick.Controls as Controls
import QtQuick.Layouts
import org.kde.plasma.core as PlasmaCore
import org.kde.plasma.plasmoid
import org.kde.taskmanager as TaskManager

PlasmoidItem {
    id: root

    Plasmoid.title: qsTr("Window controls")
    Plasmoid.backgroundHints: PlasmaCore.Types.NoBackground
    Layout.minimumWidth: fused ? 270 : 0
    Layout.preferredWidth: fused ? 270 : 0
    Layout.maximumWidth: fused ? 270 : 0
    implicitWidth: fused ? 270 : 0
    visible: fused

    // TasksModel emits state changes; the serial makes data() bindings refresh.
    property int modelSerial: 0
    readonly property bool fused: {
        modelSerial;
        return eligible(tasks.activeTask);
    }
    readonly property string activeTitle: {
        modelSerial;
        return fused ? String(tasks.data(tasks.activeTask, Qt.DisplayRole) || "") : "";
    }

    function eligible(index) {
        return tasks.data(index, TaskManager.AbstractTasksModel.IsWindow) === true
            && tasks.data(index, TaskManager.AbstractTasksModel.IsActive) === true
            && tasks.data(index, TaskManager.AbstractTasksModel.IsMaximized) === true
            && tasks.data(index, TaskManager.AbstractTasksModel.IsFullScreen) !== true
            && tasks.data(index, TaskManager.AbstractTasksModel.IsMinimized) !== true
            && tasks.data(index, TaskManager.AbstractTasksModel.CanSetNoBorder) === true
            && tasks.data(index, TaskManager.AbstractTasksModel.HasNoBorder) === true;
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

    preferredRepresentation: compactRepresentation
    compactRepresentation: RowLayout {
        width: 270
        height: 32
        spacing: 0

        Controls.Label {
            Layout.fillWidth: true
            Layout.minimumWidth: 0
            text: root.activeTitle
            color: "#f0f4fb"
            elide: Text.ElideRight
            verticalAlignment: Text.AlignVCenter
            Accessible.name: qsTr("Active window: %1").arg(text)
        }

        Controls.Button {
            id: minimizeButton
            Layout.preferredWidth: 40
            Layout.preferredHeight: 32
            text: "−"
            enabled: root.fused && tasks.data(tasks.activeTask,
                TaskManager.AbstractTasksModel.IsMinimizable) === true
            Accessible.name: qsTr("Minimize active window")
            onClicked: root.actOnActiveTask("minimize")
            background: Rectangle {
                radius: 4
                color: minimizeButton.hovered ? "#33435a" : "transparent"
            }
        }

        Controls.Button {
            id: restoreButton
            Layout.preferredWidth: 40
            Layout.preferredHeight: 32
            text: "▣"
            enabled: root.fused && tasks.data(tasks.activeTask,
                TaskManager.AbstractTasksModel.IsMaximizable) === true
            Accessible.name: qsTr("Restore active window")
            onClicked: root.actOnActiveTask("restore")
            background: Rectangle {
                radius: 4
                color: restoreButton.hovered ? "#33435a" : "transparent"
            }
        }

        Controls.Button {
            id: closeButton
            Layout.preferredWidth: 40
            Layout.preferredHeight: 32
            text: "×"
            enabled: root.fused && tasks.data(tasks.activeTask,
                TaskManager.AbstractTasksModel.IsClosable) === true
            Accessible.name: qsTr("Close active window")
            onClicked: root.actOnActiveTask("close")
            background: Rectangle {
                radius: 4
                color: closeButton.hovered ? "#e5484d" : "transparent"
            }
        }
    }
}
