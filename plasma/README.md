# ForgeDesktop KWin/Plasma candidate files

`session/forge-kwin-session` is a fixed ordinary-user wrapper for the upstream
Plasma Wayland launcher. `session/forgedesktop-kwin.desktop` makes the candidate
selectable at login and advertises KDE first so its session services and portal
backend are selected. The wrapper launches the Arch `plasma-workspace` helper;
the exact path must be checked against the pinned 2026/08/01 package before
image construction.

Stage the three source files at these paths, and copy `LICENSE-MIT` to the
license path, before running `tools/build_plasma_bundle.py`:

```text
usr/libexec/forge-desktop/forge-kwin-session
usr/share/wayland-sessions/forgedesktop-kwin.desktop
usr/share/forge-desktop/plasma/dependencies.json
usr/share/licenses/forge-desktop/LICENSE
```

Only the session script is executable. The producer records the source commit
and exact bytes in `bundle.json`. `dependencies.json` names the two essential
upstream runtime packages and declares licenses for any bundled visual assets.
The full package closure and its licenses belong in ForgeOS's separate signed
lock. ForgeOS must pin the receipt digest separately and verify that closure.
This candidate has no Forge visual package yet and never changes the default
login session. The existing Smithay and XFCE login entries remain available.
