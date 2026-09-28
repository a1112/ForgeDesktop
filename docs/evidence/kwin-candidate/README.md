# KWin/Plasma isolated candidate: initial acceptance

Date: 2026-09-28 UTC. This records the first boot and window checks, not the
M3-M5 daily-use or default-session acceptance. The later Forge visual package,
verified image rebuild, and interactive checks are recorded in
[visual acceptance](visual-acceptance.md).
The follow-up pinned software-rendering image and its fresh-login measurements
are recorded in [software backend acceptance](software-backend-acceptance.md).

## Artifact and isolation

- ForgeDesktop source commit: `651e2e47943aa958335a02adfd9ae5e04a98b4b2`.
- ForgeDesktop bundle receipt SHA-256: `c30d9cf8d4d19908bf58e914c072b2adb1e94ed13c9a8f170fffd8dd60b7ad53`.
- ForgeOS source image SHA-256: `2cc90d85ad4d26e2c4181b241d9fe7acc9c82650755c979bf7b60fe75d5d6f1e`.
- Derivative image SHA-256: `10306e25d6b56e40714324f8229c31f0f13ed0f9bfeb3edc49310591f7a9542f`.
- The pinned Arch 2026/08/01 closure added 158 packages. Every archive and
  detached signature matched the ForgeOS lock and verified against the pinned
  Arch keyring before offline installation. Installed versions were checked
  against the lock. See [image receipt](image-receipt.json).
- The source raw image and the existing daily VM were not modified. QEMU used
  a new qcow2 overlay with a read-only base; see [started receipt](vm-started.json).
  The candidate image itself retains `user-session=xfce` and
  `autologin-session=xfce`. Only the disposable overlay changed
  `autologin-session` to `forgedesktop-kwin` to test unattended login.
- QMP reported KVM enabled and running with 2 vCPU, 4 GiB, virtio-vga, and a
  1280x800 guest output. noVNC connected through a separate localhost/SSH
  tunnel, leaving the existing daily VM viewer untouched.

## Observed behavior

1. LightDM launched the packaged Wayland entry as the ordinary `forge` user.
   The guest showed `kwin_wayland` with `--socket wayland-0` and XWayland
   support, plus `startplasma-wayland` and `plasmashell`. `loginctl` listed
   the `forge` user session on `seat0`.
2. KRunner opened with Alt+Space. Thunar (GTK) and System Settings (Qt)
   rendered as separate, focused windows. Alt+Tab returned focus to the
   terminal. KWin's Meta+PageUp maximized Thunar; Meta+Left tiled it on the
   left. [Independent QMP frame](kwin-systemsettings.png) shows the two
   application windows and the Plasma panel at native 1280x800.
3. Sending `SIGKILL` to `plasmashell` removed the panel while Thunar, System
   Settings, and the terminal stayed open. The panel returned automatically.
   `plasmashell` PID changed from 732 to 1572; KWin PID 618 remained.
   [Recovery frame](kwin-shell-recovered.png) shows the surviving windows and
   recovered panel.
4. Firefox opened its first-run page in a full-size window. The guest reported
   `systemctl is-active forge-permissiond` as `active` after the package-hook
   warning. This checks service liveness, not the full permission API.

## Limits and follow-up

- This *first* image contained the session entry and verified launcher, without
  the later Forge dark visual package. Its screenshot shows stock Plasma styling.
- The test overlay used automatic login because the disposable `forge` account
  has no interactive password. The greeter's manual session-selection and
  KWin-exit return path remain to be exercised in a separate overlay.
- Pointer drag/resize, overview, virtual desktops, Electron,
  CompatForge, Flatpak, XWayland focus, portals, Fcitx, clipboard, audio,
  output scaling, lock security, 8-hour use, 20 cycles, and performance goals
  remain pending. The test VM's noVNC channel did not enable clipboard or audio.
- Pacman's `systemd-tmpfiles` post-transaction hook emitted an unsafe path
  transition warning for the pre-existing Forge permission database. Pacman
  completed with exit 0 and the candidate booted. The service is active, but
  its database and permission operations still need a guest acceptance check.
- Windows-native ForgeOS Rust `cargo test` failed two existing
  `forge-config` tests on POSIX-style runtime paths, and `cargo clippy -D
  warnings` failed existing unused imports in Forge services. The new Python
  tests passed; these Rust gates must be resolved or verified in their Linux
  build environment before M5.

Keep XFCE as the default and retain the Smithay session until the remaining
gates pass and the current VM is backed up.
