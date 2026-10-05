# Ubuntu desktop profile integration

The user approved an independent Ubuntu compatibility profile supporting
.deb/APT, Snap and Flatpak on 2026-10-05. KWin/Plasma remains the approved
window-manager route. ForgeOS owns exact Ubuntu package versions, signed
repository provenance, privileged installation and the independent image;
ForgeStore owns jobs and published application records.

The existing Arch session script, dependency inventory and schema-1 receipt
contract remain unchanged. An explicit `--profile ubuntu-26.04` produces a
schema-2 `plasma-session` receipt with `runtimeProfile: ubuntu-26.04` instead
of `archSnapshot`. ForgeOS must pin the new receipt independently and accept
it only in its Ubuntu profile. A package-name inventory is not a signed or
version-locked Ubuntu dependency closure.

Stage `plasma/session/forge-kwin-session-ubuntu` as
`usr/libexec/forge-desktop/forge-kwin-session`, `tools/ubuntu_desktop.py` as
`usr/libexec/forge-desktop/ubuntu-desktop` (both mode 0755), and
`plasma/dependencies-ubuntu.json` as
`usr/share/forge-desktop/plasma/dependencies.json`. Other licensed theme,
session entry and CompatForge assets keep their existing paths and modes.
The helper is MIT project code and introduces no Python dependencies.

## Ubuntu first-login favorites

Version 0.2.1 adds a separate Ubuntu first-login layout source at
`plasma/look-and-feel-ubuntu/contents/layouts/org.kde.plasma.desktop-layout.js`.
The Arch layout source and its five original favorites remain unchanged.
Ubuntu uses the real desktop IDs `org.kde.dolphin.desktop`,
`org.kde.konsole.desktop`, `forge-store.desktop` and `systemsettings.desktop`.
A read-only UID-1000 query in the Ubuntu candidate confirmed all four entries
and their icons exist; the four old XFCE/Firefox favorites were absent.

The public Plasma scripting API `applicationExists(storageId)` filters out
missing targets before writing first-login launchers. This query does not
launch applications. The new Ubuntu product base must separately pin and
install the ForgeStore artifact, its desktop entry and hicolor icon, as well
as the OS-owned Dolphin/Konsole/System Settings package closure. These are
runtime dependencies of this layout, not bundled application implementations.
Kate and Firefox are not pinned before installation and acceptance.

The default applies only when the upstream first-login layout is created.
Installing the new bundle does not rewrite an existing user's launcher list,
reset Plasma configuration or restart the shell. The VM upgrade and any
explicit existing-user favorite changes require separate saved-state and
real UI evidence.

To stage the reviewed repository assets automatically, with the profile
selecting the correct layout, use a clean exact-commit checkout:

```
python3 tools/build_plasma_bundle.py --repository-assets --profile ubuntu-26.04 \
  --output /absolute/new-bundle-directory --version 0.2.1
```

The original `--staging` interface remains available and mutually exclusive
with `--repository-assets`; Ubuntu staged inputs must include the Ubuntu
layout. The repository stager copies the original MIT license and all theme,
catalogue and session assets with exact modes, without changing source files.
The 22-payload bundle contains no fonts; pinned font packages remain OS-owned.
The `applicationExists` behavior is tested with the real JavaScript script
in a host Node harness representing only external Plasma objects. This is
not evidence of real Plasma rendering or an existing-user migration.

The ordinary-user session prepares XDG paths before launching upstream
Plasma. It retains existing valid data-directory order and XDG_DATA_HOME,
then appends missing `/usr/local/share` and `/usr/share`, Flatpak user and
system exports and `/var/lib/snapd/desktop`, without duplicating paths.
Paths remain present before the first package is installed. Relative,
control-containing, colon-ambiguous and unbounded paths fail visibly. Both
the incoming and final expanded search path are bounded to 64 entries and
16 KiB of UTF-8; individual and generated paths are bounded to 4096 UTF-8
bytes. Invalid surrogate encodings fail with a validation error. The
wrapper chooses only known executable Plasma DBus session helpers, preferring
Ubuntu amd64's packaged
`/usr/lib/x86_64-linux-gnu/libexec/plasma-dbus-run-session-if-needed`
and retaining `/usr/libexec/plasma-dbus-run-session-if-needed` and
`/usr/lib/plasma-dbus-run-session-if-needed` as fixed compatibility paths.
The multiarch path was confirmed with `dpkg-query -L plasma-workspace` in the
Ubuntu 26.04 candidate. It never derives a command from application
metadata. Neither session launch nor refresh accepts root.

KDE discovers and launches original desktop entries. KSycoca and kded monitor
changes during the session; no Forge entry copies, vendor Exec rewriting or
Plasma restarts are required. An ordinary-user GUI process can request an
explicit full cache refresh after a completed native package operation:

```
/usr/bin/python3 /usr/libexec/forge-desktop/ubuntu-desktop refresh
```

Refresh executes only `/usr/bin/kbuildsycoca6 --noincremental`, preserves the
session environment and has a 30-second timeout. It removes stale cache
records after uninstall too. Call it in the graphical user's existing
session, including its DBus and XDG menu environment; the privileged package
service must not rebuild a root-owned desktop cache. Failure is reported and
must not turn a failed install or refresh into GUI acceptance.

## Window capability assessment and remaining gates

Normal move, resize, maximize, restore, minimize, fullscreen, tiling and
focus switching use upstream KWin. The reviewed Forge Aurorae decoration
and Fusion widget remain intact. Fusion rechecks active task eligibility
and each supported capability on click; it excludes fullscreen, minimized,
non-window and the previously verified Firefox client decoration.

This increment does not change those window controls without a demonstrated
runtime failure. The current Fusion TasksModel does not explicitly filter
by output or virtual desktop. Its current-output behavior therefore remains
a specific two-output acceptance gap, alongside other client decorations,
scale factors and dynamic monitor changes. Test before widening Fusion
eligibility or claiming the complete window matrix passed.

Host tests cover environment/path bounds, fixed command selection, root
rejection, receipt/profile isolation and bundle tampering. They do not prove
Ubuntu boot, real KDE refresh, application launches, Snap confinement,
APT/Flatpak installation or window behavior. These require the independent
Ubuntu VM: install one pinned application per delivery type, observe its
new launcher, launch through KDE, perform a real function and save/reopen,
exercise controls, uninstall and observe removal. Retain the M3/M4/M5
performance and stability gates, original Arch/Windows state and recovery.

## Upstream references

- [KDE KSycoca](https://api.kde.org/ksycoca.html): automatic cache detection,
  kded directory monitoring and cache-change notification.
- [KDE XDG hierarchy](https://userbase.kde.org/KDE_System_Administration/XDG_Filesystem_Hierarchy)
- [Desktop entry specification](https://xdg.pages.freedesktop.org/xdg-specs/desktop-entry/latest-single/)
- [KDE TasksModel public source](https://raw.githubusercontent.com/KDE/plasma-workspace/Plasma/6.6/libtaskmanager/tasksmodel.h)
- [Plasma scripting API](https://develop.kde.org/docs/plasma/scripting/api/)
- [Plasma 6.6 ScriptEngine API export](https://raw.githubusercontent.com/KDE/plasma-workspace/Plasma/6.6/shell/scripting/scriptengine.cpp)
