# ForgeDesktop compositor

This is the M1 implementation in progress, **not an accepted daily desktop**.
`forge-compositor --nested` opens an X11 output window and serves native Wayland
clients on `forge-wayland-0` inside the current user's `XDG_RUNTIME_DIR`.
It refuses root. Closing the host window exits the compositor; the listening
socket is managed by Wayland's RAII socket guard. Existing desktop sessions are
unmodified.

Rendering uses Smithay Pixman and its output damage tracker. No GL renderer is
compiled in. The nested transport uploads damaged rectangles only; it splits scanline uploads to the X server's maximum request size. This
transport must be benchmarked before any frame-time or CPU claim.
`--drm /dev/dri/cardN` selects libseat session access, libinput, two DRM dumb
buffers and vblank-driven page flips. This backend requires an active login
seat; root is refused in both modes. The initial backend supports one connected
output; multimonitor/scaling/hotplug remain later acceptance work.

Current adapter: wl_compositor/subsurfaces, wl_shm, xdg-shell, output/xdg-output,
seat keyboard/pointer, data device, real toplevels/popups, client-requested
interactive move/resize, click focus. Only implemented xdg window-management
capabilities are advertised (currently none of maximize/fullscreen/menu).
There is no private control socket.
M3 lock, capture, portal, IME and shell interfaces are not advertised.

## Dependency provenance

- `smithay = 0.7.0`, MIT, https://github.com/Smithay/smithay
- crates.io source SHA-256:
  `740cea6927892bc182d5bf70c8f79806c8bc9f68f2fb96e55a30be171b63af98`
- `Cargo.lock` fixes the dependency graph and each registry source checksum.
- Protocol handler structure follows Smithay's MIT-licensed `examples/minimal.rs`;
  software rendering and window management are ForgeDesktop code.
- X11 transport uses Smithay's re-export of x11rb (MIT/Apache-2.0), avoiding an
  application FFI boundary. Pixman/libinput/DRM/libseat system packages belong to
  the ForgeOS package lock. Record their installed versions in build evidence.

## Development checks

Run `cargo test --workspace --locked`, `cargo fmt --check`, and Linux
`cargo clippy --workspace --all-targets --locked -- -D warnings`.
Windows policy tests do not compile or validate the Linux compositor adapter.

The isolated runtime harness is `tests/nested_smoke.sh`, with real GTK/Qt test
clients and a scoped Xvfb input driver. Recorded nested evidence is in
`docs/evidence/m1/nested-validation.md` at the repository root. Full M1 remains
pending the independent DRM and display-manager recovery checks.
