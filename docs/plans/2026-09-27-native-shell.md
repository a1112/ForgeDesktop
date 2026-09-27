# Native shell implementation plan

> Execute using the existing subagent-driven-development workflow: one
> implementation task, specification review, then quality review.

**Goal:** Complete approved M2 with a real, independently restartable QML shell.

**Architecture:** The compositor owns window policy and scene placement. Its
fixed shell executable receives one end of a private socket pair as stdin;
there is no filesystem control socket. The C++/Qt shell displays native QML
windows, receives bounded state/events and requests typed window operations.
Standard desktop applications launch through GIO desktop-entry APIs.

**Stack:** Existing pinned Smithay/Pixman and Qt 6.11.1 packages, Rust, C++20,
Qt Quick software rendering, GIO; no browser engine in the shell.

## Task 1: Private shell control and real window policy

Files: `crates/forge-compositor/src/linux/shell.rs`, protocol module/tests,
`src/linux.rs`, `src/linux/drm_backend.rs`, Cargo manifests/lock if necessary.

1. Add failing tests for framed partial reads, oversized/malformed messages,
   wrong protocol version, unknown window/workspace IDs and output queue bounds.
2. Implement a version-1 typed protocol over an inherited Unix socket pair.
   Bound frame and queue sizes, strings, commands per dispatch and retry rate.
   IDs are opaque strings, never pointers or process IDs. No arbitrary exec verb.
3. Spawn a fixed installed shell path; clear exec inheritance of the shell
   endpoint before it launches other programs. Authenticate special shell
   surface roles against the spawned shell's actual Wayland client credentials.
   An ordinary app with a matching title/app-id must not become a desktop panel.
4. Expose current windows, activation, close, minimize/restore, maximize,
   fullscreen, snapping and workspaces through the existing policy model.
   Synchronize protocol configure/ack, scene stacking and actual keyboard/pointer
   focus. Advertise only behavior that is now implemented.
5. Keep background below apps and panels above ordinary apps; reserve work area
   for top bar/dock. Shell popovers receive focus only when intentionally opened.
6. Restart failed shell with bounded backoff; other app processes and Wayland
   connections survive. Re-send authoritative state after reconnect.
7. Run Linux unit tests, Clippy/fmt and real nested tests for every state change,
   spoofed-role denial and shell-kill recovery before DCO commit/review.

## Task 2: QML interface and desktop-entry launch

Files: `shell/CMakeLists.txt`, `shell/src/*`, `shell/qml/*`, `shell/tests/*`,
`docs/design/visual-provenance.md`, `docs/evidence/m2/*`.

1. Write Qt tests for protocol decoding, window model reconciliation, desktop
   entry filtering/search and application launch failure reporting.
2. Build the shell with CMake/Ninja against the pinned Arch Qt/GIO packages.
   Use software rendering by default and ordinary session privileges.
3. Implement top bar, colorful bottom Dock, application grid/search, real task
   switching and workspace controls. Use plain text for untrusted app titles.
   Clock and actual CPU/memory/disk/network metrics update at bounded intervals.
4. Reference local R-OS `components/os/TopBar.tsx` and `Dock.tsx` for proportions
   and dark translucent/rounded styling. Recreate shapes in QML and use installed
   application icons. Do not copy unlicensed assets. Record exact sources and
   license status of any copied asset. Static background; transitions <=150ms;
   no blur, continuous animation or fake system data.
5. Use GIO desktop-entry parsing/launch, including visibility rules and errors.
   Do not construct shell commands from desktop files or expose exec over IPC.
   The existing Forge-registered-app broker integration remains required in M3.
6. Test shell SIGKILL/restart with GTK/Qt apps remaining open and editable;
   verify launcher launches actual installed apps and Dock reflects real state.
7. Install only into the isolated daily test image and inspect real screenshot.
   Record measurements as observations, not performance acceptance. DCO commit
   then specification and quality review.

## Unchanged delivery gates

M3 still must implement actual controls, notifications/tray, IME, clipboard,
lock/capture/portal/audio and output rollback. The complete M4 application,
fault, 8-hour soak and 20-cycle gates and M5 artifact/image/license/performance
delivery remain mandatory. Keep the user's XFCE/R-OS sessions intact until all
gates pass. Shell prototype success is not complete daily-desktop acceptance.
