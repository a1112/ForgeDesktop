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
active. The [native QMP frame at 61%](kwin-v5-audio-61.png) shows the actual
Audio Volume panel with **Line Out** and **Line In**. Moving the output slider
from 40% to 61% changed `wpctl get-volume @DEFAULT_AUDIO_SINK@` to `0.61`;
the test output volume was then returned to 40%.

The first remote look-and-feel invocation failed because the SSH process did
not have a display environment. Supplying the active Wayland socket and Qt
platform allowed the command to apply `org.forge.desktop`; Plasma Shell then
restarted successfully. `--resetLayout` applied the full Forge top panel and
centered Dock to this disposable profile. The [native Forge frame](kwin-v5-forge-audio.png)
shows the audio panel anchored to the top bar. The layout survived a normal
guest reboot; no application or compositor implementation changed.

Three samples distinguish the session state. The [stock-layout sample](kwin-v5-idle.json)
averaged 352.43 MiB PSS and 0.083% CPU. Immediately after resetting the
layout within that same session, a [hot-layout sample](kwin-v5-forge-idle.json)
averaged 461.26 MiB PSS, **failing** the 400 MiB goal. KWin alone rose from
about 167 MiB to 268 MiB PSS. A normal guest reboot restored the Forge
layout; a restored terminal was closed before the final measurement.

The [fresh-login 60-second raw sample](kwin-v5-fresh-forge-idle.json) used
root only to read the PSS of UID 1000's exact `kwin_wayland` and `plasmashell`
processes. It had no open application windows or audio panel. Process
identities were stable and all PSS reads completed:

| Metric | Fifth image | Published target |
|---|---:|---:|
| Mean combined PSS | 323.10 MiB | ≤400 MiB |
| Maximum combined PSS | 349.57 MiB | diagnostic |
| Average CPU, one core | 0.083% | ≤5% |

The fourth image's fresh-login result was 332.40 MiB and 0.067%. Both fresh
Forge-layout images meet these two VM targets. The hot-layout failure shows
that changing layouts in a running session needs a separate memory-recovery
test; the fresh reboot is not evidence that the hot-session increase has been
fixed. Frame P95, launcher P95,
screen-sharing, authenticated lock, Windows-side audio listening, a matched
R-OS baseline, eight-hour use and 20 login cycles remain unverified.
