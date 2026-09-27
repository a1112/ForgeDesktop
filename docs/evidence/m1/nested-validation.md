# M1 nested compositor evidence — 2026-09-27

**Nested subset passed. Full M1 remains pending DRM runtime and display-manager
failure recovery. No M2–M5 or performance acceptance is implied.**

## Tested build

- Ordinary build/test user: UID 1000 (`forge-build`) in a disposable Arch
  systemd-nspawn container. The user's daily desktop was not operated by these tests.
- Rust 1.98.1 toolchain, Arch GCC 16.1.1+r595+g171d15ac6959-1,
  glibc 2.44+r5+g7cba77790f32-1. Cargo dependencies fixed by `Cargo.lock`.
- Smithay 0.7.0; pixman 0.46.4-1; libinput 1.31.3-1; libdrm 2.4.134-1;
  libxkbcommon 1.13.2-1; Wayland 1.25.0-1; seatd 0.9.3-1.
- GTK 3.24.52-1; Qt base/Wayland 6.11.1-1. Package signatures checked by
  pacman against the prepared Arch keyring. The container is not a boot acceptance test.
- `forge-compositor` SHA-256:
  `b3cde161d0d9adaf40c1d7c181283f9a163f4e535310b358fb50a3eed93852bc`.
- Both nested and DRM Rust code compile. Arch `cargo test --workspace --locked
  --offline`: 17 unit tests passed. Linux Clippy all targets with `-D warnings`
  passed; `cargo fmt --check` and `git diff --check` passed.

## Runtime checks

| Check | Evidence/result |
|---|---|
| Real GTK Wayland rendering | `nested-gtk.png`, manually inspected |
| Real Qt Wayland rendering | `nested-qt.png`, manually inspected |
| Keyboard delivery to real clients | Five X11 host key events became `forge` through the compositor's Wayland seat in both toolkits |
| Native Qt titlebar move | Pixel assertion: vacated area became background and target area became window; screenshot shows +200,+100 move |
| Native Qt resize | Qt content width 634 → 734; +100 pixels independently logged by the client |
| Click focus and stacking | A second Qt process received `forge`; clicking the exposed first entry produced `forgeforge` only in the first process and raised it |
| Live socket ownership | Duplicate compositor exited 1 and did not change the live socket inode |
| Compositor crash | SIGKILL in the isolated container; a fresh compositor successfully rebound the same socket |
| Root refusal | Exit 1: `compositor must run as an ordinary user` |
| Unsafe runtime directory refusal | UID 1000 with `XDG_RUNTIME_DIR=/tmp` exited 1 before opening a display |

Screenshots show Chinese glyph rendering, **not Chinese IME acceptance**.
Client logs end with connection-loss diagnostics where the harness deliberately
killed the compositor. This is expected and is distinct from shell-process recovery.

## Reproduce

Build `forge-compositor` and `--examples` with Cargo locked/offline. Bind source
to `/work/forge-desktop` and Cargo target to `/target` in the test container, with
GTK 3 development files, Qt 6 Widgets/Wayland, GCC, pkgconf, Xvfb and D-Bus installed.
Run as the ordinary build user:

```sh
dbus-run-session -- sh /work/forge-desktop/crates/forge-compositor/tests/nested_smoke.sh qt
dbus-run-session -- sh /work/forge-desktop/crates/forge-compositor/tests/nested_smoke.sh gtk
```

The harness uses an isolated Xvfb `:92`, not an existing user display. It refuses
to pass input through its test helper unless this display and the explicit
`--isolated-xvfb` flag are selected. Captures/logs are in `/work/m1-nested-{qt,gtk}`.
`tests/xwd_to_png.py` converts the captured framebuffer with Python's standard library.

## Remaining adapter limits

- DRM requires an active libseat/logind login seat, a private runtime directory,
  and dumb-buffer allocation, PRIME export and CPU dmabuf mapping. It selects one
  connected output, preferring 1280×800, and uses two software buffers/page flips.
- Hardware cursor shapes, keyboard-origin popup grabs, client min/max size
  constraints and M2 window-management controls need further work.
- Fullscreen/maximize/minimize/window-menu capabilities are not advertised.
  Lock, capture, portal, virtual input and private shell control protocols are
  not registered. No XWayland acceptance has been performed.
- No latency/PSS/idle-CPU/frame-time goal has been measured or accepted here.

## Follow-up: axis forwarding and DRM scanout format

The review found missing DRM scroll dispatch. Both backends now use one axis
translator. Three regression tests first failed and then passed, covering both
axes, high-resolution v120 steps, continuous motion, natural direction, and
explicit finger stops (an absent axis is not a stop). Real Qt Wayland acceptance
was rerun after the change: `nested-wheel-client.log` records vertical
`qt-wheel:0,120` and horizontal `qt-wheel:-120,0`. Move, resize, two-client focus,
socket collision and crash/rebind checks also passed again. Arch locked/offline
workspace tests now total **20 passing**; all-target Clippy with `-D warnings`
passed. Earlier GTK screenshot/log evidence above retains its original build hash.

This follow-up binary SHA-256 is
`df0d0a95abb0cae9e38f4567e525921b62e2ef8054327bbb759750362c6e57f1`.

A separate isolated DRM test reached initialization but the kernel rejected AR24
on the primary plane. Smithay's opaque framebuffer helper can fall back to legacy
framebuffer creation using the original allocation format. The compositor now
queries primary-plane XRGB8888 support and allocates that format directly, so
both modern and legacy framebuffer creation use XRGB8888. Initial atomic state
testing preserves kernel error context. Actual DRM acceptance is recorded by the
separate VM test; compilation alone does not establish that acceptance.