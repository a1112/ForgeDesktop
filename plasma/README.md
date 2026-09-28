# ForgeDesktop KWin/Plasma candidate files

`session/forge-kwin-session` is a fixed ordinary-user wrapper for the upstream
Plasma Wayland launcher. `session/forgedesktop-kwin.desktop` makes the candidate
selectable at login and advertises KDE first so its session services and portal
backend are selected. The wrapper launches the Arch `plasma-workspace` helper;
the exact path must be checked against the pinned 2026/08/01 package before
image construction. In this software-rendered VM candidate the wrapper selects
Qt Quick's software scene graph backend for the ForgeDesktop session. This
environment is session-local; selecting XFCE does not inherit it. The software
backend omits some Qt Quick shader effects and requires application checks.

Stage the source files at these paths, and copy `LICENSE-MIT` to the license
path, before running `tools/build_plasma_bundle.py`:

```text
usr/libexec/forge-desktop/forge-kwin-session
usr/share/wayland-sessions/forgedesktop-kwin.desktop
usr/share/forge-desktop/plasma/dependencies.json
usr/share/licenses/forge-desktop/LICENSE
usr/share/plasma/look-and-feel/org.forge.desktop/metadata.json
usr/share/plasma/look-and-feel/org.forge.desktop/contents/defaults
usr/share/plasma/look-and-feel/org.forge.desktop/contents/layouts/org.kde.plasma.desktop-layout.js
usr/share/plasma/look-and-feel/org.forge.desktop/contents/wallpapers/forge.svg
usr/share/aurorae/themes/ForgeDark/metadata.desktop
usr/share/aurorae/themes/ForgeDark/ForgeDarkrc
usr/share/aurorae/themes/ForgeDark/decoration.svg
usr/share/aurorae/themes/ForgeDark/minimize.svg
usr/share/aurorae/themes/ForgeDark/maximize.svg
usr/share/aurorae/themes/ForgeDark/restore.svg
usr/share/aurorae/themes/ForgeDark/close.svg
usr/share/plasma/plasmoids/org.forge.windowcontrols/metadata.json
usr/share/plasma/plasmoids/org.forge.windowcontrols/contents/ui/main.qml
```

Only the session script is executable. The producer records the source commit
and exact bytes in `bundle.json`. `dependencies.json` names the two essential
upstream runtime packages and declares licenses for any bundled visual assets.
The full package closure and its licenses belong in ForgeOS's separate signed
lock. ForgeOS must pin the receipt digest separately and verify that closure.
The global theme uses public Plasma 6 theme and layout paths. It is installed
as an option: selecting it in the isolated user session applies the Forge
wallpaper, dark Breeze palette, top status panel and compact bottom task panel.
The bundle never changes the default login session or an existing user's
Plasma configuration. The Smithay and XFCE login entries remain available.

The Forge Dark Aurorae decoration handles ordinary server-decorated windows.
The top-panel widget requests actions for the current maximized task through
Plasma's task model. KWin still owns focus, movement, tiling and permissions.
The widget excludes the verified `firefox.desktop` client-drawn header so its
own controls remain the only set. Other client-drawn AppIds require an explicit
compatibility check before adding them to that exclusion. The optional Forge
theme sets borderless maximized windows for Fusion Mode; do not apply
that setting to another session or an existing user's profile automatically.
