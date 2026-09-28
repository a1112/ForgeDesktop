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
topPanel.height = 34;
topPanel.addWidget("org.kde.plasma.kickoff");
topPanel.addWidget("org.kde.plasma.pager");
topPanel.addWidget("org.kde.plasma.panelspacer");
topPanel.addWidget("org.kde.plasma.digitalclock");
topPanel.addWidget("org.kde.plasma.panelspacer");
topPanel.addWidget("org.kde.plasma.systemtray");

var dock = new Panel;
dock.location = "bottom";
dock.height = 62;
dock.alignment = "center";
dock.minimumLength = 560;
dock.maximumLength = 560;
dock.addWidget("org.kde.plasma.icontasks");
dock.addWidget("org.kde.plasma.showdesktop");
