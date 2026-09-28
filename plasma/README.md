# ForgeDesktop KWin/Plasma candidate files

`session/forge-kwin-session` is a fixed ordinary-user wrapper for the upstream
Plasma Wayland launcher. `session/forgedesktop-kwin.desktop` makes the candidate
selectable at login and advertises KDE first so its session services and portal
backend are selected. The wrapper launches the Arch `plasma-workspace` helper;
the exact path must be checked against the pinned 2026/08/01 package before
image construction.

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
