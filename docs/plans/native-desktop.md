# Approved native ForgeDesktop implementation plan

User approved 2026-09-27: Rust/Smithay compositor, Qt 6/QML native shell,
complete daily desktop in current x86_64 VM, reusing mature Linux applications.
Visual target is R-OS dark colors, colorful icons, rounded shapes, top bar and
bottom dock. Current target is 2 vCPU, 4 GiB, 1280x800 software-rendered KVM.

## Ownership and rendering

This independent repository owns compositor, shell and desktop services.
ForgeOS installs a pinned artifact and session; CompatForge retains runtime
ownership. Ordinary-user DRM/KMS/libinput/logind compositor; Pixman+dumb buffers
and damage tracking in the current VM, Qt Quick software rendering. Implement
nested backend first, then independent login. Hardware GPU is later scope.

## Required capabilities

- Real Wayland and XWayland windows: focus, move, resize, maximize/minimize,
  fullscreen, snapping, virtual desktops, multiple outputs/scales.
- Independent QML shell: bar, dock, grid/search, clock, notification center,
  quick controls and real system metrics. No realtime blur or dynamic wallpaper;
  animations <=150ms. Shell restart preserves client windows.
- Reuse Thunar, terminal, Mousepad, Firefox and GNOME Software/Flatpak. Desktop
  entry compliant launch; Forge-registered apps use the existing launch broker.
- Network provider, PipeWire/WirePlumber, display/input/theme/default app/power
  settings through D-Bus and existing policy. Fcitx 5 composition, clipboard,
  drag/drop, notifications and StatusNotifier tray.
- Standard xdg-shell, output/scaling, data-transfer/text-input/session-lock
  protocols; only advertise implemented capabilities.
- Shell control is inherited private Unix IPC, versioned and bounded. Opaque
  window IDs, state/events, activate/close/minimize, workspaces/output changes.
  No arbitrary command execution and no public control endpoint.
- ext-session-lock-v1 with upstream PAM swaylock; fail locked on locker failure.
  User enters new credentials manually; disable development autologin only at
  final accepted default-session switch after usable authentication is verified.
- Reuse GTK file portals; own screenshot and PipeWire ScreenCast backend with
  whole-output/window selection, consent, cancellation/revocation and lock stop.
  Remote control/global input injection is excluded.
- Wayland clipboard agent connects existing QEMU vdagent channel, opt-in text
  in both directions including Chinese; disabled while locked. Keep noVNC and
  add SSH-protected SPICE audio for actual host listening acceptance.
- Versioned private user config, atomic save, safe malformed-config fallback;
  timed confirmation/revert for output changes.

## Ordered milestones

M0: capture R-OS/XFCE startup/PSS/CPU/interaction/rendering baseline under fixed
conditions; provision >=30 GiB build space preserving existing disks and state.
M1: nested and DRM output, real GTK/Qt clients, input/focus/move/resize; recover
to login on compositor failure. M2: native shell/visuals/tasks/workspaces and
shell crash recovery. M3: all daily integrations above. M4: GTK/Qt/Electron,
Flatpak/XWayland/CompatForge samples, data persistence, rejection/fault tests,
8-hour mixed workload and 20 normal login/logout/reboot cycles. M5: performance,
licenses/provenance, verified installable artifact, complete new image,
recovery guide, default-session switch and visible final desktop.

## Measurable gates

- Compositor+shell PSS <=400MiB, excluding regular applications.
- Idle 60-second CPU <=5% of one core, no continuous unnecessary redraw.
- Drag/animation compositor frame P95 <=33ms; warm launcher P95 <=100ms.
- Report noVNC end-to-end latency separately; repeat matching R-OS baseline.
- Two virtual outputs, 100/150/200% scale, removal and failed-mode rollback.
- Lock rejects overlays/input/capture; failed auth never unlocks. Test separate
  compositor/shell/XWayland/portal crashes and recovery.
- Chinese candidate positioning, cross-app clipboard/drop, UTF-8 files/reboot.
- Capture consent/deny/cancel/revoke and unauthorized private IPC rejection.
- ForgeDesktop tests/integration gates and existing 12 ForgeOS checks pass.

## Rollout boundaries

Keep XFCE recovery and R-OS entry. Destructive fault tests run in an isolated
instance. Stop/backup current VM before install; never swap its immutable base.
Per-toolkit application interiors need not exactly match R-OS. HDR/VRR/touch,
hardware GPU and other architectures are excluded. Final deliverables include
source commits, artifact/image, reports/screenshots and recovery instructions.

References: https://smithay.github.io/smithay/smithay/index.html;
https://doc.qt.io/qt-6/qtquick-visualcanvas-adaptations-software.html;
https://flatpak.github.io/xdg-desktop-portal/docs/writing-a-new-backend.html;
https://github.com/swaywm/swaylock.
