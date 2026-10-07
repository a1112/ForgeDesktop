# R-OS native theme candidate

The approved R-OS visual contract uses graphite surfaces (#171a21 background,
#232730 elevated content, #20242c toolbars), #e5e7eb text, #9ca3af secondary
text and #60a5fa accent. Native title rows and the top panel target 32 pixels.
Grouped close/minimize/maximize controls are on the left: red #ff5f57,
yellow #febc2e and green #28c840, with 12-pixel dots inside 24-by-32 hit areas.
Aurorae title corners use 12-pixel SVG geometry. Client contents can obscure
the inner bottom arc within the existing 3-pixel borders; full-frame rounding
requires visual qualification. KWin owns title dragging, resizing,
maximize, tiling, workspaces and window actions; Fusion still checks the current
eligible task and leaves verified client-decorated Firefox controls intact.
The shared token file uses Qt #AARRGGBB for eight-digit colors. CSS consumers
must convert alpha order instead of copying those strings directly.

ForgeROS.colors supplies Qt/KDE colors through the optional Forge look-and-feel
defaults. An original Plasma style supplies the top panel, Dock and task frame;
other widgets inherit the installed Breeze Dark fallback. Live blur and contrast
effects remain disabled. The Dock uses the public `dodgewindows` hiding mode.
At 100% scale its 56-pixel panel, 6-pixel panel margins and 2-pixel task margins
target a 40-pixel icon; icon artwork stays owned by installed application packages.
Task backgrounds use 6-pixel SVG corners.

Original GTK 3 and GTK 4 styles cover file managers, text editors, terminal UI,
toolbars, sidebars, menus, tabs, selection, focus, scrollbars and common controls.
The candidate session selects ForgeROS:dark only when the theme is installed
and GTK_THEME has no explicit override. It writes no home files, dconf keys,
terminal profiles or existing application settings. User GTK CSS, terminal
content/palettes, Firefox/Electron interiors and libadwaita-owned styling can
still differ. The CSS contains no external assets or resource imports; the entry
file imports only its packaged `gtk-dark.css` sibling. Existing XFCE and user
configuration remain recoverable. The shell wrapper is optional and does not
switch the default session.

The extra R-OS shell package provides a small lock-screen branding layer by
inheriting the complete installed upstream LockScreen QML component. The exact
source target is plasma-desktop and kscreenlocker 6.7.3, matching the recorded
ForgeOS kwin-desktop package lock. It does not implement a password box, handle
PAM, call Qt.quit, or alter authentication. It inherits the upstream API-v2
viewVisible contract and all existing authentication/accessibility behavior.
It is an optional Plasma/Shell package and **is not selected as the lock shell
by the look-and-feel defaults**. Installing assets is not runtime qualification.

For an image staging tree, add all source/destination pairs in
`tools.stage_ros_theme.ROS_FILES` alongside the existing Plasma files; their
MIT license entries are in plasma/dependencies.json. `stage_ros_theme.py DIR`
creates a fresh standalone overlay. The bundle validator refuses a ForgeROS
default without the entire theme set, an incomplete lock package, or an altered
upstream delegate. The normal closed receipt/hash verification still applies.

Before selecting the candidate lock shell in a disposable session, confirm the
installed upstream QML import path and exact Plasma 6.7.3 packages. Run the real
KScreenLocker testing window, then a genuine lock/unlock cycle with incorrect
password, correct password, Chinese layout, multi-output focus, repeated errors,
sleep/resume and shell/greeter crash recovery. Confirm that closing a browser or
R-OS server cannot unlock the machine. Keep the existing upstream shell selected
until these tests pass; the local WSL compiler does not contain that runtime.

The 2026-10-07 source update is packaging and visual-contract qualification,
not new native runtime evidence. The available WSL distributions do not contain
the matching GTK/KWin/Plasma rendering runtime. Recheck ordinary and Fusion
controls, focus rings, GTK checkbox/menu glyphs, Thunar/Mousepad/Terminal/Qt
applications, scaling, Dock work area and CSD behavior in the exact pinned guest
before treating the geometry or application appearance as runtime-qualified.

Reviewed upstream interfaces (source inspection, not runtime certification):
- https://github.com/KDE/plasma-desktop/blob/v6.7.3/desktoppackage/contents/lockscreen/LockScreen.qml
- https://github.com/KDE/kscreenlocker/blob/v6.7.3/greeter/greeterapp.cpp
- https://github.com/KDE/kscreenlocker/blob/v6.7.3/greeter/pamauthenticators.h
- https://develop.kde.org/docs/plasma/aurorae/
- https://github.com/KDE/aurorae/blob/v6.7.3/v1/qml/aurorae.qml
- https://develop.kde.org/docs/plasma/theme/theme-details/
- https://develop.kde.org/docs/plasma/theme/theme-elements/
- https://develop.kde.org/docs/plasma/scripting/api/
- https://github.com/KDE/plasma-desktop/blob/v6.7.3/applets/taskmanager/qml/code/LayoutMetrics.js
- https://docs.gtk.org/gtk3/running.html
- https://docs.gtk.org/gtk3/css-properties.html
- https://docs.gtk.org/gtk4/class.CssProvider.html
