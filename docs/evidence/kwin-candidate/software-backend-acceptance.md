# KWin/Plasma software backend: fresh-image acceptance slice

Date: 2026-09-28. This is the fourth isolated image, following the
[Forge visual image](visual-acceptance.md). It verifies the candidate's
software-rendered VM session and two performance gates only; M3-M5 remain open.

## Artifact and isolation

- ForgeDesktop bundle source commit:
  `fce6e183262266fcf67116322c9267b13706f2b8`; bundle version `0.2.2`.
- ForgeDesktop bundle receipt SHA-256:
  `ef1aab7a5c5a1e3e803b0e16d369a55556a7a587113660a2f8f411499ea80fc7`.
- ForgeOS derivative image SHA-256:
  `77097121033c0f300c04d7d031076e6fa468f76ec7948009afa333984dbbfea9`.
  See the [image receipt](kwin-v4-image-receipt.json). Source raw SHA-256
  remains `2cc90d85ad4d26e2c4181b241d9fe7acc9c82650755c979bf7b60fe75d5d6f1e`.
- The image builder independently validated the bundle's exact login-script
  bytes, 158 pinned Arch package archives and signatures, installed versions,
  source identity, and XFCE default. The 20 GiB derivative is read-only at
  `/srv/forge-desktop-build/kwin-root-output/forgeos-kwin-v4.raw` on the
  Linux builder. Its source and the daily VM were not modified.
- A new qcow2 overlay selected KWin automatically for testing, enabled a
  host-loopback-only SSH control key, and disabled idle auto-lock so the viewer
  remains usable. These test-only settings are absent from the raw image.
  The raw image still defaults to XFCE; Forge theme selection was performed
  in the test user profile after login.

## Observed desktop and performance

The VM used KVM, 2 vCPU, 4 GiB, virtio-vga, a 1280x800 output, and no hardware
GPU. LightDM started KWin Wayland and Plasma Shell as ordinary user `forge`.
`/proc/751/environ` in the guest contained `QT_QUICK_BACKEND=software`,
inherited from the pinned ForgeDesktop session wrapper. The Forge wallpaper,
dark panel and centered Dock rendered normally in the
[native 1280x800 QMP frame](kwin-v4-forge-desktop.png). The installed Dock
launched Thunar and XFCE Terminal; KWin tiled both to screen halves with
Meta+Left and Meta+Right. The [native tiled-window frame](kwin-v4-windows-tiled.png)
shows both real application surfaces. No application window was open during
the following idle sample.

The [raw process counters](kwin-v4-idle.json) cover exactly `kwin_wayland` and
`plasmashell` for UID 1000, excluding launched applications and descendants.
Root read `smaps_rollup` only for the measurements. Over 60.00028 seconds at
five-second intervals, identities stayed stable and every PSS read succeeded:

| Metric | Observed | Published target |
|---|---:|---:|
| Mean combined PSS | 332.40 MiB | ≤400 MiB |
| Maximum combined PSS | 335.09 MiB | diagnostic |
| Average CPU, one core | 0.067% | ≤5% |

This run meets the **PSS and idle-CPU goals under the fixed VM conditions**.
It is one 60-second warm session after theme application. It does not measure
window frame P95, launcher P95, noVNC end-to-end delay, long-term memory
growth, or a matched R-OS workload. The older hot-restart experiment was
444.76 MiB; the fresh-image measurement is the valid candidate result, but
their different process histories prevent attributing the whole change to one
factor. [Software Qt Quick](https://doc.qt.io/qt-6/qtquick-visualcanvas-adaptations-software.html)
omits some shader effects, so application visuals
and 150% fractional scaling still require checks.

## Remaining release conditions

- M3 services and permissions: Fcitx, clipboard/drag-drop, notifications,
  audio, portal consent/revoke, output scaling, and a real authenticated lock.
- M4 app matrix, save/reboot persistence, 8-hour mixed use and 20 clean cycles.
- M5 frame and launcher latency, matched R-OS comparison, dependency/license
  evidence and recovery flow. The image builder volume has about 27 GiB free
  after this build, below the 30 GiB preparation target for another rebuild.
- The test overlay's automatic login and privileged control cannot count as
  lock-security acceptance. A default switch requires a user-set account
  password and removal of development automatic login.

XFCE remains the default recovery session, and the Smithay entry remains
available. No production default or physical-disk installation changed.
