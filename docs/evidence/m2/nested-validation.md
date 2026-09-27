# M2 native shell: nested validation

2026-09-27, isolated signed Arch 2026/08/01 build container, ordinary
`forge-build` UID 1000. Xvfb :92 1280x800, Pixman compositor and Qt Quick software.
This container shares the 8GiB Hyper-V host; it is **not** the fixed 4GiB target
VM, so no performance budget is accepted from these observations.

Commands: `cargo test --offline --locked`, `cargo clippy --offline --locked
--all-targets -- -D warnings`, `cargo fmt --all --check`, CMake/Ninja shell
build, `model-test`, then `sh shell/tests/smoke.sh` inside the builder.

- 25 Rust tests pass (8 library, 3 Linux axis, 14 policy), including partial
  frames, oversized/unknown/wrong-version messages, queue cap, stale IDs and
  exact PID+UID role authentication. Initial protocol tests were observed red.
- Qt tests pass: complete snapshot reconciliation/removal, malformed snapshot
  rejection, Hidden/NoDisplay/OnlyShowIn filtering, missing application failure.
  Initial reconciliation/filter/failure tests were observed red before code.
- Actual GTK3 and Qt6 Wayland fixtures both accept `forge`; shell SIGKILL causes
  restart with new PID while both original application PIDs and text survive;
  each accepts another `forge`, yielding `forgeforge`.
- Dock operations produce Qt content sizes 1274x645 maximized (1280x678 outer
  work area including client decorations), 1280x800 fullscreen, 634x447 restored,
  and 634x645 half-width snap. Minimize/restore, both snaps, workspace transfer
  and switch are exercised through actual QML pointer controls. Typed close
  terminates the targeted Qt fixture normally while other clients survive.
- GIO app grid lists genuine installed desktop entries, and clicking CMake
  launches real `/usr/bin/cmake-gui`, with a corresponding task. Its stdin was
  inspected as `/dev/null`, not the shell control socket. The shell-only Qt
  decoration suppression is removed from app launch context.
  A second shell SIGKILL also preserves the GIO-launched CMake PID.
- A separate Qt client with title `forge.panel` and shell-like desktop ID stays
  an ordinary 634x447 client, never receiving the privileged 1280x38 panel role.
- Original QML shapes and colorful Dock icons were visually inspected. App
  titles use PlainText. CPU/RAM/disk/network values come from real /proc and
  QStorageInfo with 2-second sampling, clock from system time.

Runtime logs/screenshots on builder: `/srv/forge-desktop-build/work/m2-smoke`.
Raw screenshots are XWD; selected PNGs are retained in this evidence directory.
`shell/tests/nested.sh` is a bounded manual diagnostic harness; `smoke.sh` is the
repeatable automated acceptance sequence. The Xvfb input helper has no production
injection endpoint and explicitly requires DISPLAY=:92 and --isolated-xvfb.

M2 independent DRM/daily-image installation is owned by the parent integration
task and must be checked separately. M3 IME/notifications/tray/controls/lock/
capture/clipboard/XWayland and Forge broker integration remain pending, as do
M4/M5 stability/performance/release gates. This is not a complete daily desktop.

Validated debug compositor SHA-256:
`c8d451a7f618712bf59e82073276181096e24439b4d8c58ea9285cb2ca2342eb`.
Shell SHA-256:
`520be9d6e8b1bf1b9bcc30129b18c56ffcef0d5c3bd9541c52a8d38f56e6015b`.
Paths: `/srv/forge-desktop-build/arch-target/debug/forge-compositor` and
`/srv/forge-desktop-build/work/m2-shell-build/forge-shell`.

## Specification review corrections (2026-09-28)

The first implementation kept persistent panels above fullscreen and its smoke
test did not assert several resulting window states. The new independent real
Qt fixture `shell/tests/window_probe.cpp` paints exact, distinct colors and logs
all keyboard/mouse events; `window_policy.sh` checks the compositor framebuffer
through the isolated X11 output, not control-command logs.

Before the fix, the fullscreen top pixel failed: expected client RGB
`[32,180,100]`, observed panel RGB `[130,148,193]` (`policy-red.txt`). After the
fix, both former chrome regions (100,15 and 640,765) show client pixels and the
client receives clicks at those exact coordinates. `fullscreen-policy.png`
confirms the full client covers the output. Super deliberately opens controls.

`policy-green.txt` records exact left/right snap pixel checks, minimize removal,
restore reappearance, workspace transfer/removal and workspace reappearance.
The script also asserts per-client keyboard **and pointer** counts do not change
while minimized/on another workspace, and verifies restored/switched clients
receive subsequent input. These checks exercise actual scene visibility and
focus, rather than just command receipt or configured dimensions. Existing
GTK/Qt/CMake restart/launcher/close smoke coverage remains in place.
