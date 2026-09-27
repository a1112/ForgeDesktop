# M3.1 interoperability source checkpoint — 2026-09-28

This checkpoint extends the display checkpoint `e2a5f3b`. It does not complete
M3, the application matrix, stability/performance gates, or image delivery.

## Runtime changes

- Rootless XWayland is a compositor child with a separate XWM event loop.
  Native and X11 surfaces participate in the same window policy, rendering,
  focus, move/resize, task list, workspace and output membership. Override
  redirect surfaces do not steal keyboard focus or become normal tasks.
- Clipboard and primary selection bridge between native clients and real
  XWayland clients. Reading native selection from X11 requires X11 keyboard
  focus. The privileged xwayland-shell global is not visible to ordinary clients.
- XWayland failure removes its windows, releases its event source/display lock,
  clears only its server-owned selections and restarts with bounded backoff.
  Native applications remain alive. Its shell protocol state is recreated for
  each generation because Smithay 0.7 caches surface serials and XWayland resets
  its counter after restart. Reusing that cache intermittently associated new
  windows with an old surface; three consecutive restart tests passed after
  the correction, followed by another pass with diagnostic tracing removed.
- Shell and Fcitx receive the actual XWayland DISPLAY. The existing Ready log
  announces each server generation. Cross-user ForgeOS broker authorization
  remains ForgeOS policy; the compositor does not grant xhost or socket ACLs.
- `wp_fractional_scale_v1` and `wp_viewporter` are now implemented through
  Smithay. Preferred scale follows the highest overlapping output scale,
  including subsurfaces and tracked popups. Integer-only clients may still use
  integer buffers resampled at 150 percent.
- `--nested-multi` publishes two real output regions and renders them into one
  host window. The private render canvas is not exposed as a third output.
- Display files are bounded, regular files opened without following symlinks;
  configuration directories use 0700 and atomically replaced files use 0600.
- Popup authorization consumes a click sequence once even if its release
  arrives after the press serial has already been used.

## Red/green findings

1. A native fractional-scale/viewport probe failed on the earlier display
   candidate because the globals were absent. The new probe receives scale
   120 and a 1280x800 configure, and renders RGB (170,51,204) at the expected
   location. The DRM candidate separately produced scale 240 and 640x400 on
   the second output at 200 percent. Final DRM 150-percent UI validation is
   recorded separately by the VM acceptance owner.
2. The old candidate rejected `--nested-multi`. The new test sees exactly two
   outputs at (0,0) and (1280,0), purple client pixels at (2000,400), and the
   clicked client receives key 30.
3. A real X11 client created at 640x480 and resized to 128x160 before mapping
   remained 640x480 before the fix. Its ConfigureRequest is now honored:
   128x160 on map and 192x224 after a subsequent resize. This addresses a
   plausible cause of the WineMine black area observed by the VM owner, but
   the WineMine sample itself requires a new DRM run before claiming it fixed.

## Final Linux checks

All commands used the pinned Arch build root, Rust 1.98.1, Smithay 0.7.0,
offline locked Cargo dependencies and ordinary UID 1000. Xvfb is only the
host for nested tests: X11 application DISPLAY is the child XWayland display,
explicitly checked to differ from host DISPLAY `:92`.

| Check | Observed result |
|---|---|
| `cargo test --offline --locked --workspace` | 28 tests passed |
| `cargo clippy --offline --locked --workspace --all-targets -- -D warnings` | Passed |
| `build_protocol_probes.sh` | Rebuilt output, fullscreen, fractional and persistent-IME probes |
| `selection_smoke.sh` | Exact UTF-8 clipboard/primary, client cursor/hotspot, file URI drag/drop; ordinary registry denies IME, virtual keyboard and xwayland-shell |
| `xwayland_smoke.sh` | Real X11 pre-map/mapped sizing; exact Chinese/emoji clipboard and primary both directions; SIGKILL restart with new XWayland PID and retained native PID; new X11 client reads native selection |
| `ime_smoke.sh gtk` and `qt` | Native text-input-v3 composition, candidate pixels, Chinese `你好`, IME restart, same application reaches `你好你好` |
| `popup_input.sh`, `released`, `bogus` | Three disable/enable cycles have one candidate layer; press/release paths accepted, unrelated serial denied |
| `persistent_ime.sh popup` | Real Qt clicked QMenu input; exactly 800 candidate pixels |
| `scale_smoke.sh` | Fractional feedback/viewport destination and exact purple pixel |
| `nested_multi_smoke.sh` | Two outputs, second-output client pixels, pointer and keyboard |
| `shell/tests/window_policy.sh` | Fullscreen edges render and receive input; snap, minimize/restore and workspaces retain expected visibility/input |

The fake persistent IME tests use a read-only container bind mount over
`/usr/bin/fcitx5`; there is no production authorization bypass. Real Fcitx
tests run without that mount. Runtime logs and framebuffers remain under
`/srv/forge-desktop-build/work/m3-*`; committed real-VM evidence is separate.

## Artifact and remaining gates

Compositor candidate: `/srv/forge-desktop-build/work/m3-interop-final-candidate`

SHA256: `a19a6ae86883d829b7a777bedaccf3b89cd18272eb5ed388be3688e23b38e3cc`

Fractional probe: `/srv/forge-desktop-build/work/scale-output`

SHA256: `63494b282725fd79d4492b76c914cbf37d022e47672e876af670aac1b4ab9278`

These are debug candidates. Independent review and deployment of the committed
source build into the disposable DRM guest remain required. Parent-owned
Electron, CompatForge, multihead screenshots and shell display controls have
separate records. Absolute tablet mapping currently targets the primary output;
relative pointer input spans outputs. Hardware modes are chosen from DRM modes,
while the current display UI controls layout and 100/150/200-percent scale.
X11 uses its established integer coordinate model; this checkpoint does not
claim per-monitor X11 HiDPI or every legacy popup/drag interaction. Locking,
portal capture, host clipboard synchronization, audio and soak testing are
subsequent gates. XFCE and the user's VM remain recoverable.
