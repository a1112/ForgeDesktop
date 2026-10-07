// ForgeDesktop's first-login layout uses only the public Plasma scripting API.
var desktopsArray = desktopsForActivity(currentActivity());
for (var i = 0; i < desktopsArray.length; i++) {
    var desktop = desktopsArray[i];
    desktop.wallpaperPlugin = "org.kde.image";
    desktop.currentConfigGroup = ["Wallpaper", "org.kde.image", "General"];
    desktop.writeConfig("Image", "file:///usr/share/plasma/look-and-feel/org.forge.desktop/contents/wallpapers/forge.svg");
}

var topPanel = new Panel;
topPanel.location = "top";
topPanel.height = 32;
topPanel.floating = false;
topPanel.addWidget("org.kde.plasma.kickoff");
var windowTitle = topPanel.addWidget("org.forge.windowcontrols");
windowTitle.currentConfigGroup = ["General"];
windowTitle.writeConfig("displayRole", "title");
topPanel.addWidget("org.kde.plasma.pager");
topPanel.addWidget("org.kde.plasma.panelspacer");
topPanel.addWidget("org.kde.plasma.digitalclock");
topPanel.addWidget("org.kde.plasma.panelspacer");
topPanel.addWidget("org.kde.plasma.systemtray");
var windowControls = topPanel.addWidget("org.forge.windowcontrols");
windowControls.currentConfigGroup = ["General"];
windowControls.writeConfig("displayRole", "controls");

var dock = new Panel;
dock.location = "bottom";
dock.height = 56;
dock.hiding = "dodgewindows";
dock.alignment = "center";
dock.lengthMode = "custom";
dock.length = 560;
dock.minimumLength = 560;
dock.maximumLength = 560;
var tasks = dock.addWidget("org.kde.plasma.icontasks");
tasks.currentConfigGroup = ["General"];
var launchers = [
    "applications:thunar.desktop",
    "applications:xfce4-terminal.desktop",
    "applications:org.xfce.mousepad.desktop",
    "applications:firefox.desktop",
    "applications:systemsettings.desktop"
];
if (applicationExists("org.gnome.Software.desktop")) {
    launchers.push("applications:org.gnome.Software.desktop");
}
tasks.writeConfig("launchers", launchers);
dock.addWidget("org.kde.plasma.showdesktop");
