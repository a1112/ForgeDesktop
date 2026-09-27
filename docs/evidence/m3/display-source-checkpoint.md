# M3 display source checkpoint

The multi-output implementation has per-CRTC software buffers, damage tracking,
forced connector probes, hot-removal rescue, output-local rendering and pointer
coordinates. Absolute devices map to the primary output; relative devices can
traverse the desktop. QEMU's per-head VNC absolute events contain no head identity.

The private shell protocol accepts bounded typed output/confirm/revert commands.
Only confirmed layouts are atomically saved with mode 0600 under
`$XDG_CONFIG_HOME/forge-desktop/v1/outputs.conf` (or `$HOME/.config`). Unknown,
malformed or incompatible configurations retain the safe connected layout.
A topology change cancels a pending transaction, and reconnecting the matching
set of outputs restores the last saved confirmation. Hardware modes are currently
selected from DRM modes, preferring 1280x800. The UI changes position and scale.

The paired QML shell exposes Displays with 100/150/200%, Keep and Revert.
Normal fullscreen/maximize targets the window's output; explicit xdg fullscreen
honors its requested output. Fullscreen on head 1 does not hide head 0's shell.

Validation: 28 Rust tests, Clippy with warnings denied, Qt model ctest. Live DRM
candidate 1/2/3 failures, corrections and screenshots are recorded separately in
`display/README.md`; candidate3 was built from the saved source snapshot used
for this checkpoint. Its SHA is
`1b517cfa71038b54954f10192d5e0d9d78ba0e3e4dfb343ebd61d433ad6e8b66`.
The paired shell SHA is
`5c44058075542ea6fd5faff1ad3d9a29f8463fb4aa778d5e3e87e956940169ef`.
These are scoped debug artifacts; a clean committed-source rebuild remains a
separate gate. This checkpoint does not advertise fractional-scale or viewporter;
150% uses integer client buffers resampled by the compositor.

The same checkpoint fixes Qt menus opened from a released pointer click. Popup
permission is tied to a recently delivered serial and client, expires after two
seconds and is consumed once (press/release are one authorization group). Real
`popup_input.sh released` failed before the change and passes after it; bogus
serial remains rejected. A real Qt QPushButton::clicked QMenu with QLineEdit
shows exactly 800 persistent candidate pixels. It has no privileged test bypass.
