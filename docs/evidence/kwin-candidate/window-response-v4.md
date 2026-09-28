# KWin window response: first VM tuning slice

Date: 2026-09-28. This record concerns the isolated v4 candidate visible at
the loopback-only noVNC port 6087. It is a scoped behavior check, not the M5
frame-time or end-to-end latency acceptance.

## Diagnosis and recovery

The 7.7 GiB Linux builder had no swap and ran two 4 GiB KWin test VMs. At
07:57:45 UTC its OOM killer terminated the v4 QEMU process (`-9`); the v4
systemd unit reported `oom-kill` and a 6.4 GiB memory peak. This was a host
capacity failure. The v4 noVNC web service and Windows SSH tunnel remained
up, so the browser showed a disconnected viewer. The v5 guest was shut down
normally, `qemu-img check` found no error in the v4 test overlay, and v4 was
restarted as `forge-kwin-v4-test-vm-r3`. Its QMP user-network SSH forwarding
was restored. The existing 6087 browser tab reconnected and displayed the
Forge wallpaper, top panel and Dock again. The v5 overlay and both immutable
raw images were retained. On this builder, run only one 4 GiB candidate VM at
a time until its memory allocation is raised.

The [native QMP frame after recovery](window-response-v4.png) is 1280x800 and
shows the clean desktop from QEMU rather than a noVNC canvas capture.

## Observed rendering and change

KWin 6.7.3 `supportInformation` identified the DRM output and **OpenGL on
Mesa llvmpipe**. Its window-view and overview effects reported a 300 ms base
animation duration. The user profile had no `AnimationDurationFactor` value.
The Forge look-and-feel now sets `[kdeglobals][KDE]
AnimationDurationFactor=0.5` for users who select the theme. KDE's animation
factor scales effect duration; for effects that use it, a 300 ms base becomes
150 ms. This is intended to reduce perceived wait during switching and
overview while retaining visible motion. It does not accelerate llvmpipe's
individual render frames.

For a reversible runtime check, `kwriteconfig6` set the same value in the v4
test user's `kdeglobals`, KWin was reconfigured over the user's D-Bus, and
`kreadconfig6` returned `0.5`. Through the live noVNC canvas, the pinned Dock
opened XFCE Terminal; the window moved after a title-bar drag and closed from
its title-bar control. The browser returned to the clean Forge desktop. These
observations confirm window operations survived the setting change. The v4
raw image remains unchanged; the profile adjustment lives only in its qcow2
test overlay.

The exact user-visible animation duration, dirty-frame P95, warm launcher P95,
and noVNC end-to-end latency were **not measured** in this slice. The current
browser interaction confirms behavior, not a latency target. A matched
before/after scripted window workload, with the same foreground viewer and
one guest at a time, remains required before a fluidity claim or default
session switch.

## References

- KDE's [General Behavior](https://docs.kde.org/stable_kf6/en/plasma-desktop/kcontrol/workspaceoptions/index.html)
  describes the workspace animation-speed setting.
- KDE's [KWin API](https://develop.kde.org/docs/plasma/kwin/api/)
  documents the effect animation-time factor.
- KDE's [portal settings source](https://github.com/KDE/xdg-desktop-portal-kde/blob/master/src/settings.cpp)
  reads `AnimationDurationFactor` from `kdeglobals`.
