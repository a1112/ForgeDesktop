# KWin/Plasma M3 audio control slice

Date: 2026-09-28. This is an isolated fifth derivative image, built from the
same read-only daily source as the [software-rendered fourth image](software-backend-acceptance.md).
It tests the missing Plasma volume component and rechecks the VM's two idle
performance gates. It does not complete M3 audio playback to Windows.

## Artifact and isolation

- Source raw SHA-256: `2cc90d85ad4d26e2c4181b241d9fe7acc9c82650755c979bf7b60fe75d5d6f1e`.
- ForgeDesktop bundle SHA-256: `ef1aab7a5c5a1e3e803b0e16d369a55556a7a587113660a2f8f411499ea80fc7`.
- Fifth image SHA-256: `ced7c8e319a914d9830dc4d3c63871c73340655d6ae4bac615e8dd2d32ae4c97`,
  verified independently with `sha256sum` after the build. The
  [image receipt](kwin-v5-image-receipt.json) records 160 signed Arch packages,
  XFCE as the image default, and `systemAB=false`.
- The 2026/08/01 package lock gained `plasma-pa 6.7.3-1` and
  `pulseaudio-qt 1.8.1-1`. Both archive hashes and detached signatures were
  verified against the source image's pinned Arch keyring before installation.
  Offline `pacman -U --print` resolved both against the fourth image's installed
  dependency set. The fifth image builder checked all 160 packages and their
  installed versions.
- The builder had 30.18 GiB free before the image build after removing only
  reproducible Cargo target directories. The previous images and overlays were
  retained. The fifth image is read-only at
  `/srv/forge-desktop-build/kwin-root-output/forgeos-kwin-v5.raw`.
- A fresh qcow2 overlay selected ForgeDesktop KWin for unattended test login,
  disabled auto-lock, and enabled a restricted root SSH key reachable only via
  QEMU's loopback host forwarding. These settings and manual Forge theme
  selection are not part of the raw image. The fourth viewer and daily VM were
  not changed.

## Observed behavior

The fifth VM booted KWin Wayland as ordinary user `forge` with 2 vCPU, 4 GiB,
virtio-vga, 1280x800 and `QT_QUICK_BACKEND=software`. A normal QMP power request
opened KDE's confirmation screen; selecting **Shut Down** completed with QEMU
exit code 0 and `qemu-img check` reported no errors. After enabling the
test-only SSH service in the stopped overlay, it booted again. The guest's
ED25519 host fingerprint was verified in its terminal before using the key.

`plasma-pa`, `pulseaudio-qt` and `pipewire-pulse` were installed at the locked
versions. Plasma Shell, PipeWire, PipeWire PulseAudio and WirePlumber were
active. The [native QMP frame](kwin-v5-audio-61.png) shows the actual Audio
Volume panel with **Line Out** and **Line In**. Moving the output slider from
40% to 61% changed `wpctl get-volume @DEFAULT_AUDIO_SINK@` to `0.61`; the
test output volume was then returned to 40%.

The first remote look-and-feel invocation failed because the SSH process did
not have a display environment. Supplying the active Wayland socket and Qt
platform allowed the command to apply `org.forge.desktop`; Plasma Shell then
restarted successfully. No application or compositor restart was required.

The [60-second raw sample](kwin-v5-idle.json) used root only to read the PSS of
UID 1000's exact `kwin_wayland` and `plasmashell` processes. It followed the
theme application and shell restart, with all application windows and the
audio panel closed. The process identities were stable and all PSS reads
completed:

| Metric | Fifth image | Published target |
|---|---:|---:|
| Mean combined PSS | 352.43 MiB | ≤400 MiB |
| Maximum combined PSS | 353.26 MiB | diagnostic |
| Average CPU, one core | 0.083% | ≤5% |

The fourth image's comparable result was 332.40 MiB and 0.067%. The different
session histories prevent attributing the entire PSS change to the audio
packages. Both images meet these two VM targets. Frame P95, launcher P95,
screen-sharing, authenticated lock, Windows-side audio listening, a matched
R-OS baseline, eight-hour use and 20 login cycles remain unverified.
