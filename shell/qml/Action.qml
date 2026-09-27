import QtQuick
Rectangle {
 id: control
 property string label: ""
 property bool selected: false
 signal clicked()
 width: Math.max(32, caption.implicitWidth + 22); height: 30; radius: 8
 color: selected ? "#385ca5" : hit.containsMouse ? "#344156" : "#202938"
 border.color: selected ? "#769cfa" : "#394355"
 Text {id: caption; anchors.centerIn: parent; text: control.label; textFormat: Text.PlainText; color: "#eff3fb"; font.pixelSize: 12}
 MouseArea {id: hit; anchors.fill: parent; hoverEnabled: true; onClicked: control.clicked()}
}
