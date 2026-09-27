import QtQuick
import QtQuick.Window

Window {
 id: background; visible: true; title: "forge.background"
 width: desktop.desktopWidth; height: desktop.desktopHeight
 color: "#101622"; flags: Qt.FramelessWindowHint
 Rectangle {anchors.fill: parent; gradient: Gradient {GradientStop {position: 0;color: "#142135"} GradientStop {position: 1;color: "#0b101a"}}}
 Rectangle {width: 460;height: 460;radius: 130;rotation: 32;x: parent.width * 0.64;y: 135;color: "#162c48";border.color: "#233d5c";border.width: 2}
 Rectangle {width: 280;height: 280;radius: 84;rotation: 32;x: parent.width * 0.69;y: 225;color: "#203e60"}
 Column {x: 76;y: parent.height * 0.38;spacing: 12
  Text {text: "FORGE";color: "#f1f5fc";font.pixelSize: 60;font.letterSpacing: 12;font.weight: Font.Light}
  Text {text: "A place for your work.";color: "#8394ac";font.pixelSize: 18}
 }
 Window {
  id: panel;visible: true;title: "forge.panel";width: desktop.desktopWidth;height: 38;flags: Qt.FramelessWindowHint;color: "#e6192230"
  Row {anchors.left: parent.left;anchors.leftMargin: 12;anchors.verticalCenter: parent.verticalCenter;spacing: 8
   Action {label: "◈  Forge";onClicked: desktop.showLauncher(!desktop.launcher)}
   Repeater {model: 4;Action {required property int index;label: String(index+1);selected: desktop.workspace===index;onClicked: desktop.switchWorkspace(index)}}
  }
  Text {anchors.centerIn: parent;text: desktop.clock;textFormat: Text.PlainText;color: "#e4eaf5";font.pixelSize: 12}
  Action {anchors.right: parent.right;anchors.rightMargin: 14;anchors.verticalCenter: parent.verticalCenter;label: "Displays";onClicked: displays.visible=true}
 }
 Window {
  id: displays;visible: false;title: "ForgeDesktop — Displays";width: 600;height: 420;color: "#192436"
  Column {anchors.fill: parent;anchors.margins: 24;spacing: 18
   Text {text: "Displays";font.pixelSize: 24;color: "#edf3ff"}
   Text {text: desktop.displayPending?"Keep these settings? Reverting automatically in 15 seconds.":"Scaling and layout apply immediately. Confirm to save.";color: "#adc2df";wrapMode: Text.Wrap;width: parent.width}
   Repeater {model: desktop.outputs;Column {required property var modelData;spacing: 8
    Text {text: "Output "+modelData.id+" · "+modelData.width+"×"+modelData.height+" · "+modelData.scale/10+"%";color: "white"}
    Row {spacing: 8;Repeater {model: [1000,1500,2000];Action {required property int modelData;label: modelData/10+"%";enabled: !desktop.displayPending;onClicked: {var o=parent.parent.modelData;desktop.configureOutput(o.id,modelData,o.x,o.y)}}}
     Action {label: "Place right";enabled: !desktop.displayPending;onClicked: {var o=parent.parent.modelData;desktop.configureOutput(o.id,o.scale,desktop.desktopWidth,0)}}
    }
   }}
   Row {spacing: 12;visible: desktop.displayPending
    Action {label: "Keep settings";onClicked: desktop.confirmDisplay(true)}
    Action {label: "Revert now";onClicked: desktop.confirmDisplay(false)}
   }
  }
 }
 Window {
  id: dock;visible: true;title: "forge.dock";width: desktop.desktopWidth;height: 84;flags: Qt.FramelessWindowHint;color: "transparent"
  property string hint: ""
  Text {anchors.horizontalCenter: parent.horizontalCenter;y: 0;width: 500;horizontalAlignment: Text.AlignHCenter;text: dock.hint;textFormat: Text.PlainText;elide: Text.ElideRight;color: "#edf3ff";font.pixelSize: 11}
  Rectangle {anchors.horizontalCenter: parent.horizontalCenter;anchors.top: parent.top;anchors.topMargin: 18;width: Math.min(parent.width-32,dockRow.implicitWidth+24);height: 62;radius: 18;color: "#ed1c2636";border.color: "#485466"
   Row {id: dockRow;anchors.centerIn: parent;spacing: 8
    Action {label: "▦";width: 48;height: 48;selected: desktop.launcher;onClicked: desktop.showLauncher(!desktop.launcher)}
    Repeater {model: desktop.applications.filter(function(a){return /firefox|thunar|terminal|mousepad|software/i.test(a.id)}).slice(0,5)
     Rectangle {required property var modelData;width: 48;height: 48;radius: 12;color: pinMouse.containsMouse ? "#3a4b66":"#29364b"
      Image {anchors.centerIn: parent;width: 36;height: 36;source: "image://apps/"+modelData.id;sourceSize.width: 48}
      MouseArea {id: pinMouse;anchors.fill: parent;hoverEnabled: true;onClicked: desktop.launch(modelData.id)}
     }
    }
    Rectangle {width: 1;height: 40;color: "#465267";anchors.verticalCenter: parent.verticalCenter}
    Repeater {model: desktop.windows.slice(-9)
     Rectangle {required property var modelData;width: 48;height: 48;radius: 12;color: modelData.focused ? "#365c94":"#253144";border.color: modelData.focused ? "#80afff":"#455066"
      Image {anchors.centerIn: parent;width: 34;height: 34;source: "image://apps/"+(modelData.appId || modelData.title || "Application");sourceSize.width: 48;opacity: modelData.minimized?0.5:1}
      Rectangle {anchors.bottom: parent.bottom;anchors.bottomMargin: 3;anchors.horizontalCenter: parent.horizontalCenter;width: 16;height: 3;radius: 2;color: modelData.workspace===desktop.workspace ? "#83aeff":"#617089"}
      MouseArea {anchors.fill: parent;hoverEnabled: true;onEntered: dock.hint=modelData.title || modelData.appId;onExited: dock.hint="";acceptedButtons: Qt.LeftButton|Qt.RightButton;onClicked: function(mouse){if(mouse.button===Qt.RightButton){taskWindow.target=modelData;desktop.showLauncher(true);taskWindow.open=true;}else desktop.windowCommand(modelData.focused&&!modelData.minimized?"minimize":"activate",modelData.id);}}
     }
    }
   }
  }
 }
 Window {
  id: launcher;visible: desktop.launcher;title: "forge.launcher";width: Math.min(760,desktop.desktopWidth);height: Math.max(100,desktop.desktopHeight-190);flags: Qt.FramelessWindowHint;color: "#f2202b3c"
  property string query: ""
  property bool tasks: false
  onVisibleChanged: if(visible)search.forceActiveFocus()
  Rectangle {anchors.fill: parent;anchors.margins: 1;radius: 18;color: "#202b3c";border.color: "#4b5d78"}
  Column {anchors.fill: parent;anchors.margins: 22;spacing: 14
   Row {width: parent.width;spacing: 10
    Text {text: taskWindow.open ? "Window controls":launcher.tasks?"Open windows":"Applications";color: "#f0f4fd";font.pixelSize: 22;width: parent.width-150}
    Action {label: launcher.tasks?"Apps":"Tasks";onClicked: {launcher.tasks=!launcher.tasks;taskWindow.open=false;}}
    Action {label: "×";onClicked: {taskWindow.open=false;desktop.showLauncher(false)}}
   }
   Rectangle {width: parent.width;height: 40;radius: 10;color: "#121d2d";border.color: "#415570"
    TextInput {id: search;anchors.fill: parent;anchors.margins: 12;color: "white";font.pixelSize: 14;clip: true;selectByMouse: true;onTextChanged: launcher.query=text.toLowerCase();Keys.onEscapePressed: desktop.showLauncher(false)
     Text {visible: !search.text && !search.activeFocus;text: "Search installed applications…";color: "#8194af";font.pixelSize: 14}
    }
   }
   Item {id: taskWindow;property bool open: false;property var target: ({});visible: open;width: parent.width;height: open?80:0
    Column {spacing: 10
     Text {text: taskWindow.target.title || "Window";textFormat: Text.PlainText;color: "#ccd7e9";width: launcher.width-50;elide: Text.ElideRight}
     Row {spacing: 5;Repeater {model: ["activate","minimize","maximize","fullscreen","normal","left","right","close"];Action {required property string modelData;label: modelData;onClicked: {desktop.windowCommand(modelData,taskWindow.target.id);desktop.showLauncher(false);taskWindow.open=false;}}}}
     Row {spacing: 5;Repeater {model: 4;Action {required property int index;label: "Move to "+(index+1);onClicked: {desktop.moveWindow(taskWindow.target.id,index);taskWindow.open=false;}}}}
    }
   }
   GridView {id: grid;width: parent.width;height: parent.height-174-(taskWindow.open?100:0);clip: true;cellWidth: 118;cellHeight: 100
    model: launcher.tasks ? desktop.windows.filter(function(a){return (a.title+" "+a.appId).toLowerCase().indexOf(launcher.query)>=0}) : desktop.applications.filter(function(a){return (a.name+" "+a.description+" "+a.id).toLowerCase().indexOf(launcher.query)>=0})
    delegate: Rectangle {required property var modelData;width: 108;height: 90;radius: 12;color: appMouse.containsMouse?"#35465f":"transparent"
     Image {anchors.horizontalCenter: parent.horizontalCenter;y: 6;width: 44;height: 44;source: "image://apps/"+modelData.id;sourceSize.width: 48}
     Text {x: 5;y: 58;width: 98;text: launcher.tasks ? modelData.title:modelData.name;textFormat: Text.PlainText;color: "#dbe5f4";font.pixelSize: 12;horizontalAlignment: Text.AlignHCenter;elide: Text.ElideRight}
     MouseArea {id: appMouse;anchors.fill: parent;hoverEnabled: true;acceptedButtons: Qt.LeftButton|Qt.RightButton;onClicked: function(mouse){if(launcher.tasks){if(mouse.button===Qt.RightButton){taskWindow.target=modelData;taskWindow.open=true;}else{desktop.windowCommand("activate",modelData.id);desktop.showLauncher(false);}}else desktop.launch(modelData.id)}}
    }
   }
   Text {text: desktop.error || desktop.metrics;textFormat: Text.PlainText;color: desktop.error?"#ffb2ad":"#8da4c2";font.pixelSize: 11;width: parent.width;wrapMode: Text.Wrap}
  }
 }
}
