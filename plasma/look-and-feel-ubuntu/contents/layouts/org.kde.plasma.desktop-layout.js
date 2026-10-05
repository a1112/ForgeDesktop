// Ubuntu first-login layout uses only the public Plasma scripting API.
var desktopsArray = desktopsForActivity(currentActivity());
for (var i = 0; i < desktopsArray.length; i++) {
    var desktop = desktopsArray[i];
    desktop.wallpaperPlugin = "org.kde.image";
    desktop.currentConfigGroup = ["Wallpaper", "org.kde.image", "General"];
    desktop.writeConfig("Image", "file:///usr/share/plasma/look-and-feel/org.forge.desktop/contents/wallpapers/forge.svg");
}

var topPanel = new Panel;
topPanel.location = "top";
topPanel.height = 34;
topPanel.addWidget("org.kde.plasma.kickoff");
topPanel.addWidget("org.kde.plasma.pager");
topPanel.addWidget("org.kde.plasma.panelspacer");
topPanel.addWidget("org.kde.plasma.digitalclock");
topPanel.addWidget("org.kde.plasma.panelspacer");
topPanel.addWidget("org.kde.plasma.systemtray");
topPanel.addWidget("org.forge.windowcontrols");

var dock = new Panel;
dock.location = "bottom";
dock.height = 62;
dock.alignment = "center";
dock.lengthMode = "custom";
dock.length = 560;
dock.minimumLength = 560;
dock.maximumLength = 560;
var tasks = dock.addWidget("org.kde.plasma.icontasks");
tasks.currentConfigGroup = ["General"];
var ubuntuFavorites = [
    "org.kde.dolphin.desktop",
    "org.kde.konsole.desktop",
    "forge-store.desktop",
    "systemsettings.desktop"
];
var launchers = [];
for (var j = 0; j < ubuntuFavorites.length; j++) {
    // KDE looks up the exact application storage ID; it does not launch it.
    if (applicationExists(ubuntuFavorites[j])) {
        launchers.push("applications:" + ubuntuFavorites[j]);
    }
}
tasks.writeConfig("launchers", launchers.join(","));
dock.addWidget("org.kde.plasma.showdesktop");
