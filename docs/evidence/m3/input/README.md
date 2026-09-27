# M3.1 native selection and input checkpoint

2026-09-28, pinned Arch 2026/08/01 builder, ordinary `forge-build` user,
1280x800 Xvfb host, ForgeDesktop nested **Wayland** output with Pixman. This is
protocol/toolkit evidence; it is not independent DRM, Electron, multi-output,
lock-screen or full M3 acceptance. The user's VM was not modified by these tests.

## Reproduction and observed results

Run from the source directory inside the prepared Arch builder:

```
cargo test --workspace --offline --locked
cargo clippy --workspace --all-targets --offline --locked -- -D warnings
dbus-run-session -- sh crates/forge-compositor/tests/selection_smoke.sh
dbus-run-session -- sh crates/forge-compositor/tests/ime_smoke.sh gtk
dbus-run-session -- sh crates/forge-compositor/tests/ime_smoke.sh qt
dbus-run-session -- sh shell/tests/window_policy.sh
```

- 25 existing Rust tests passed; Clippy passed with warnings denied.
- Two separate GTK clients transferred exact `Forge 中文剪贴板 😀` through both
  clipboard and primary selection. A negotiated drag transferred the exact
  `file:///tmp/Forge-%E4%B8%AD%E6%96%87.txt\r\n` URI without executing or opening it.
- A client-provided 20x20 green cursor with hotspot `(3,5)` was sampled at
  `(397,245)` for pointer `(400,250)`, then at `(397,295)` after motion alone.
- Ordinary client registry: `text-input=1,input-method=0,virtual-keyboard=0`.
- GTK and Qt, both using native `text-input-v3`, committed `你好`. Killing only
  the supervised Fcitx process produced a new PID; both clients then committed
  `你好你好` while staying alive.
- Candidate surface screenshots are real captures: [GTK](gtk-candidate.png),
  [Qt](qt-candidate.png). GTK candidate border at `(200,360)` was `(192,192,192)`;
  Qt first candidate interior at `(167,571)` was `(128,128,128)`. These checks
  verify placement below the fixture's actual caret, including GTK CSD offsets.
- M2 fullscreen edge rendering/input, deliberate launcher access, snap,
  minimize/restore and workspace visibility/input regressions passed.

## Red tests and corrections

Before primary selection support, the GTK primary result was `MISSING` (GTK also
overwrote its clipboard fallback). Before cursor support the expected green
pixel contained `(246,245,244)`; motion-only rendering reproduced the same failure
until pointer motion marked damage dirty. Before text-input registration the
ordinary registry probe returned `text-input=0`.

Fcitx requires both input-method-v2 and virtual-keyboard-v1 to start its Wayland
frontend. Both globals use the same exact supervised PID/UID filter. Credentials
are captured from the accepted socket's kernel `SO_PEERCRED`, before insertion;
querying DisplayHandle inside a global filter deadlocked under the backend lock.
The registry probe is bounded by a five-second timeout to catch this regression.

The first candidate placement used global coordinates for `parent_geometry`;
the `(200,360)` test then saw background `(246,245,244)`. Smithay PopupManager
requires the client surface-local geometry here. The corrected native candidates
are below the text caret. The test explicitly establishes host focus before
typing, so an artificial same-batch Xvfb focus/keypress does not race IME grabs.

## Dependency and security boundary

No new Rust crates. Existing Smithay 0.7.0 MIT implementations provide primary,
text-input-v3, input-method-v2 and virtual-keyboard-v1. Fcitx is a separate process,
ordinary user, foreground `fcitx5 -D --replace`, fixed executable path, null stdin,
Wayland-only connection; failed starts/restarts use bounded exponential backoff.
The shell's inherited private channel is not exposed to Fcitx. Application
clipboard content goes through standard Wayland FD transfers, not compositor
logging or an unconstrained shell command.

Signed Arch packages used (full closure and hashes in the adjacent M3 dependency
receipts): `fcitx5 5.1.21-1`, `fcitx5-chinese-addons 5.1.13-2`,
`fcitx5-gtk 5.1.7-1`, `fcitx5-qt 5.1.14-1`. Upstream:
[Fcitx](https://github.com/fcitx/fcitx5),
[Chinese addons](https://github.com/fcitx/fcitx5-chinese-addons),
[GTK](https://github.com/fcitx/fcitx5-gtk),
[Qt](https://github.com/fcitx/fcitx5-qt). Preserve the packages' GPL/LGPL license
files in the final image. No upstream source or visual assets were copied here.

Candidate compositor SHA-256 (debug, for isolated testing only):
`5058d5927a9f66a7b528cda32a46370b917d6e8ae14f4636eacbd0c7afe3f049`.
Artifact: `/srv/forge-desktop-build/arch-target/debug/forge-compositor`.
QML shell is unchanged. Multi-output/scaling, XWayland, Electron/CompatForge,
focus-change/edge-of-output IME cases and lock gating remain M3.1/M3.2 work.

## Review correction: live popup focus changes

The additional two-Qt/Fcitx focus test passed because Fcitx itself recreated its
popup. A protocol fixture that intentionally retains one live popup reproduced
the review finding: after moving the second window right and focusing it, the
old caret `(167,571)` still rendered green instead of the Qt background
`(239,239,239)`. `dismiss_popup` now explicitly removes the live surface from its
old root before Smithay reparents it. The same fixture now observes green only
at the new caret `(697,601)` and background at the old one.

`tests/persistent_ime.c` is compiled with `wayland-scanner` against the existing
locked `wayland-protocols-misc 0.3.12` input-method-v2 XML. Its executable is
mounted over `/usr/bin/fcitx5` **only in the disposable nspawn namespace** with
`--bind-ro=/srv/forge-desktop-build/work/persistent-ime:/usr/bin/fcitx5`, then run
with `dbus-run-session -- sh crates/forge-compositor/tests/persistent_ime.sh`.
No production bypass or process-name authorization was introduced.

## Live xdg-popup input regression (2026-09-28)

The `popup_input.c` native Wayland fixture creates a real xdg_popup using a legal
pointer serial, enables text-input-v3 on that popup, then explicitly disables and
reenables it three times without destroying either popup surface. The supervised
input-method fixture paints 40 x 20 premultiplied half-alpha green pixels on a
white popup. This distinguishes a duplicated render node from a single node.

- Red: rebuilding `ime.rs` from `4e57ad4` gives 800 multiply blended candidate
  pixels and zero single-blended pixels; `popup_input.sh` exits 1.
- Green: derive the actual toplevel root with `find_popup_root_surface` before
  dismissal. Exactly 800 single-blended pixels, zero duplicate pixels; exit 0.
- Negative: `popup_input.sh bogus` sends an unrelated serial, receives popup_done,
  and never enables text input; exit 0.
- Popup parent geometry is taken from its tracked popup geometry; normal
  toplevel candidate placement continues to use the local client geometry.

These tests run in isolated Xvfb hosting the Pixman nested compositor, with a
private nspawn bind of the deterministic input-method fixture over the supervised
fixed executable. They exercise native Wayland clients, not XWayland. The bind
and fixture environment are never installed into the production guest.
