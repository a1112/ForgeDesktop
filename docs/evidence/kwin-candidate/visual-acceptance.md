# KWin/Plasma Forge visual candidate: isolated VM evidence

Date: 2026-09-28. This is an observed candidate, not M3-M5 acceptance or a
change to the user's default session.

## Reproducible artifact

- ForgeDesktop source commit: `36bbdc38445e6853bc6ffbb66215ffa13a9903c9`.
- Deterministic bundle receipt SHA-256:
  `4e2757ef56f42add59c831bb50312e072b6f26da31ea61aa14796e2cecd0e50f`.
- ForgeOS source image SHA-256:
  `2cc90d85ad4d26e2c4181b241d9fe7acc9c82650755c979bf7b60fe75d5d6f1e`.
- Derivative raw image SHA-256:
  `e9d6a65d5a92b7d9883ae83ec49ad8dacea780a5527ff0c011df1131a3bf6726`.
  See [image receipt](kwin-v3-image-receipt.json).
- The pinned Arch 2026/08/01 closure installed 158 signed packages. The image
  builder checked archive and detached-signature digests, signature trust,
  installed versions, source image identity, and the independently pinned
  ForgeDesktop bundle before emitting the derivative.
- The derivative lives at
  `/srv/forge-desktop-build/kwin-root-output/forgeos-kwin-v3.raw` on the Linux
  builder. It is read-only and retains XFCE as default. The source raw and
  existing daily VM were not modified. Only a disposable qcow2 test overlay
  selected KWin for automatic login and enabled temporary loopback SSH control.

## Interactive visual and window checks

The isolated VM used 2 vCPU, 4 GiB, virtio-vga, a native 1280x800 guest output,
and software rendering. LightDM launched KWin Wayland and Plasma as ordinary
user `forge`. The installed Forge theme applied through `plasma-apply-lookandfeel`:
Breeze Dark, a static original wallpaper, a 34-pixel top panel, and a centered
560-pixel Dock. The Dock pins installed launchers for Thunar, XFCE Terminal,
Mousepad, Firefox, and System Settings. The Forge visual package is present in
the raw image; applying it to a new user profile remains a separate onboarding
step.

- [Clean desktop frame](kwin-v3-forge-desktop.png) is a native QMP 1280x800
  capture after applying the image's Forge visual package.
- Clicking the packaged Dock entries opened real Thunar and XFCE Terminal
  windows. KWin's Meta+Left and Meta+Right arranged them in two halves;
  [tiled window frame](kwin-v3-windows-tiled.png) is a native QMP capture.
- Firefox, System Settings, KRunner, maximize, Alt+Tab, and Plasma shell
  crash/recovery were exercised in the preceding isolated image (see
  [first-boot acceptance](README.md)). That evidence is not a substitute for
  a complete application matrix on this final raw image.
- noVNC served this disposable VM through a separate local SSH tunnel. Its
  viewer is for visual inspection and is not an audio or clipboard acceptance.

## Shutdown and performance observations

The first disposable overlay did not power off after QMP ACPI powerdown: KDE
showed a lock screen, and the locked test account had no usable password.
After the timeout, only that disposable overlay was stopped through QMP
`stop`/`quit`; this was **not** a clean guest shutdown. The second disposable
overlay was stopped normally from the guest with `systemctl poweroff`; QEMU
exited with code 0 and `qemu-img check` found no errors. The third, final-image
test VM is running for interactive inspection. ACPI power-button behavior
remains a separate recovery test. During later measurement the third overlay
also locked automatically after idling. Its root-only test control used
`loginctl unlock-session` to restore the viewer. This proves no authentication
behavior: automatic login and privileged test control must be removed before
any lock-security or default-session acceptance.

A preliminary 60-second sample with Thunar and XFCE Terminal open measured
`kwin_wayland` plus `plasmashell` at 540.36 MiB combined PSS and 0.5% of one
CPU core. Open application buffers can affect the compositor process, so this
sample does not decide the no-app idle target.

After closing both windows and waiting for the desktop to settle, an exact
process-group sample for UID 1000 ran for 60.00028 seconds at 5-second
intervals. The [raw counters](kwin-v3-idle-root.json) record stable KWin and
Plasma Shell process identities and complete PSS reads. Mean combined PSS was
**553.49 MiB**, maximum **569.56 MiB**, and CPU was **0.05% of one core**.
KWin stayed at about 179.4 MiB PSS, while Plasma Shell rose from 364.1 to
390.2 MiB during the minute. A prior ordinary-user read was invalid for PSS
because KWin denied access to `smaps_rollup`; this corrected read used root
solely to inspect the two ordinary-user processes. The published **400 MiB PSS
goal is not met**. The short rise calls for longer steady-state diagnosis; it
is not yet proof of a persistent leak. Neither sample establishes frame P95,
launcher response, noVNC latency, or a matched R-OS comparison.

In the same disposable overlay, a separate experiment set
`QT_QUICK_BACKEND=software` in the `plasmashell` user service environment and
restarted that service. The desktop, panel, wallpaper, and Dock remained
visible. A subsequent [60-second raw sample](kwin-v3-software-idle.json)
recorded stable process identities, complete PSS, **444.76 MiB** mean/maximum
combined PSS and **0.067%** of one core. Plasma Shell was about 171.7 MiB;
KWin was about 273.1 MiB, so the net improvement over the preceding run was
about 108.7 MiB. The samples are sequential, not matched fresh-login trials.
The new software backend is being added to the ForgeDesktop candidate wrapper
for a fresh-login image test. This result still **fails the 400 MiB gate**.

## Remaining gates

- M3: Chinese input, clipboard and drag/drop, notification tray, audio,
  output scaling, portal consent/revoke, and lock security in this session.
- M4: GTK/Qt/Electron/Flatpak/XWayland/CompatForge matrix, persistence,
  8-hour mixed use, and 20 login/exit/reboot cycles.
- M5: accepted PSS/CPU/frame/launcher measurements, full image and recovery
  release checks, and only then any default-session decision. The published
  compositor-plus-shell PSS goal remains 400 MiB.
- The pre-existing Forge permission database produced a `systemd-tmpfiles`
  post-transaction warning during build. Pacman exited 0; permission API
  behavior still needs a guest acceptance test.
