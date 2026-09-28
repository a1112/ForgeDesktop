# KWin/Plasma ForgeDesktop design

Date: 2026-09-28. The user selected mature, complete window behavior as the
primary objective and approved KWin/Plasma as ForgeDesktop's new main route.
This decision supersedes the compositor choice in `native-desktop.md`; the
existing Smithay implementation and its M1/M2 evidence remain available as an
experimental session. XFCE remains the recovery desktop.

## Decision and alternatives

1. **KWin Wayland with Plasma workspace (selected).** Use the upstream window
   manager, compositor, session services and supported extension points. Build
   ForgeDesktop's visual identity as a Plasma look-and-feel package, panel
   layout/widgets, task switcher and small KWin scripts/effects where needed.
   This offers the shortest path to mature window behavior and daily services.
2. KWin with a wholly separate Forge QML shell. This preserves more of the
   present shell implementation, but recreates Plasma's panel, launcher,
   settings and session integration and would require more control plumbing.
3. Continue the Smithay compositor as the product default. It gives complete
   control of rendering and protocol support, but the M3-M5 desktop behavior
   remains substantial product work. Retain this route for experiments.

The selected route does not assert lower memory, CPU use or input latency.
Benchmark it against the existing Smithay candidate and the recorded R-OS
baseline under identical guest settings. The present 400 MiB PSS and other
published performance gates remain visible; any proposed change to a gate
requires measured evidence and a separate user decision before default switch.

## Ownership and session

ForgeDesktop owns the Forge theme, panel layout, launch surface, window
shortcuts/effects, acceptance tests and user-facing desktop integration. It
packages supported Plasma and KWin extensions without forking upstream KWin or
using private QML APIs. ForgeOS owns exact signed Arch package closure,
provenance, verified installation, login-session entry, policy and image
composition. CompatForge continues to own Windows compatibility runtime work.

Add a distinct `ForgeDesktop (KWin)` Wayland login session to an isolated image.
The session launches the pinned upstream Plasma Wayland path and applies
ForgeDesktop's versioned system defaults to new users. It must not overwrite a
user's existing Plasma configuration. Keep the Smithay session, XFCE recovery
session, existing home data and current image; no automatic default change.
Verify the LightDM-to-Plasma user session in the test image before assuming the
existing greeter can launch it. A login-manager change, if needed, gets its own
design and recovery gate.

## User interface and window behavior

Keep the R-OS-inspired dark palette, top bar, bottom Dock, colorful icons,
rounded controls and low-motion defaults, with recorded visual-asset licenses.
Use Plasma's supported theme, widget and panel APIs for the bar, Dock, app grid,
search, clock, notification center and quick controls. Use KWin's documented
scripting/effect APIs only for behavior that upstream settings do not cover.
Ordinary applications remain native GTK, Qt, Electron and XWayland clients.
The Forge launcher uses desktop-entry semantics; registered Forge applications
continue through their existing authorized launch broker.

Accept window focus, move/resize, maximize/minimize, fullscreen, tile/snap,
Alt-Tab, overview, virtual desktops, two outputs, hotplug and 100/150/200%
scaling. Test keyboard and pointer paths, multi-window drag/drop, XWayland
focus, tray and notifications. Do not claim macOS/Windows parity from a feature
list alone: the interaction and recovery tests must be observed in the guest.

## Services, trust and failure behavior

Use upstream Plasma/KDE integration for settings, session lock and the KDE
portal backend, including screenshot/ScreenCast consent and PipeWire. Check
portal backend selection explicitly so GTK file chooser behavior remains
available where appropriate. Use Fcitx 5 for Chinese input and verify Wayland
and XWayland candidate placement. Revalidate QEMU clipboard and noVNC behavior
in this new session; the present fragmented noVNC symptom has no proven
compositor root cause. Keep application permissions in the existing ForgeOS
services and keep the desktop session unprivileged.

If the UI shell exits, restart it without losing KWin-managed client windows.
If KWin exits, return to the login manager without unlocking a protected
session. Test lock failure, failed authentication, capture stop/revoke and
crash recovery in a disposable image. No shell extension receives arbitrary
root commands or unauthenticated private window-control access.

## Ordered validation and rollout

1. Record an architecture decision and dependency/provenance inventory. Build
   an isolated, reproducible image with a selectable KWin/Plasma session.
2. Verify real window behavior and core applications; then install the Forge
   visual package and launch integrations through supported extension points.
3. Run the existing M3 daily-service matrix, M4 application/fault/persistence
   matrix, eight-hour mixed use and 20 login/logout/reboot cycles on the new
   session. Capture evidence from the guest and independent QEMU output.
4. Measure PSS, idle CPU, frame and launcher latency at 2 vCPU, 4 GiB,
   1280x800 and software rendering. Report noVNC latency separately and repeat
   the same scripted interactions for R-OS and Smithay. Measure a hardware-GPU
   profile separately; it cannot substitute for the fixed VM gate.
5. After all gates pass, build the pinned artifact and complete image, document
   licenses and rollback, back up the current VM and only then switch the
   default session. Physical-disk boot qualification remains an independent
   gate and initially retains XFCE as the safe desktop.

The first implementation increment is the isolated selectable session and
verified package lock, not a default-session replacement. It must produce
repeatable boot evidence and a concise capability/performance gap report.

## Upstream references

- https://develop.kde.org/docs/plasma/
- https://develop.kde.org/docs/plasma/kwin/
- https://develop.kde.org/docs/plasma/kwin/api/
- https://develop.kde.org/docs/plasma/kwineffect/
- https://archlinux.org/groups/x86_64/plasma/
