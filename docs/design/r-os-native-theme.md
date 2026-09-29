# R-OS native theme candidate

The current R-OS TSX design is the reference: dark surfaces, white/gray text,
blue-400 accent, red-500 close hover, 32-pixel title row and 48-pixel controls.
The shared token file uses Qt #AARRGGBB for eight-digit colors. CSS consumers
must convert alpha order instead of copying those strings directly.

ForgeROS.colors now supplies native Qt/KDE colors through the existing Forge
look-and-feel defaults. Aurorae title colors and Fusion close hover use the
same palette. Existing GTK/application contents and client-drawn decorations
are application-owned. Software rendering does not enable live blur.

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

Reviewed upstream interfaces (source inspection, not runtime certification):
- https://github.com/KDE/plasma-desktop/blob/v6.7.3/desktoppackage/contents/lockscreen/LockScreen.qml
- https://github.com/KDE/kscreenlocker/blob/v6.7.3/greeter/greeterapp.cpp
- https://github.com/KDE/kscreenlocker/blob/v6.7.3/greeter/pamauthenticators.h
