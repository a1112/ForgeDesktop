import QtQml
QtObject {
    objectName: "windowControlsTestTasks"
    enum GroupMode { GroupDisabled = 0 }
    enum SortMode { SortDisabled = 0 }
    property int groupMode
    property int sortMode
    property bool separateLaunchers
    property int activeTask: 0
    property var rows: []
    property var requests: []
    property var roleReads: ({})
    signal dataChanged()
    signal rowsInserted()
    signal rowsRemoved()
    signal modelReset()
    function data(index, role) {
        roleReads[role] = (roleReads[role] || 0) + 1;
        return rows[index] ? rows[index][role] : undefined;
    }
    function requestToggleMinimized(index) { requests = requests.concat([{ action: "minimize", index: index }]); }
    function requestToggleMaximized(index) { requests = requests.concat([{ action: "restore", index: index }]); }
    function requestClose(index) { requests = requests.concat([{ action: "close", index: index }]); }
}
