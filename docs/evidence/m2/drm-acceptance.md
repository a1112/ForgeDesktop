# M2 independent DRM acceptance

Tested 2026-09-28 in the marked disposable daily-test image, leaving the user's
daily instance unchanged. QEMU KVM, 2 vCPU, 4 GiB, 1280x800, virtio-vga,
Pixman/dumb buffers, Qt Quick software rendering. LightDM starts an ordinary
UID 1000 Wayland session. No XFCE shell runs in that session.

- Compositor `ff17b40`: SHA-256
  `c8d451a7f618712bf59e82073276181096e24439b4d8c58ea9285cb2ca2342eb`.
- Shell: SHA-256
  `520be9d6e8b1bf1b9bcc30129b18c56ffcef0d5c3bd9541c52a8d38f56e6015b`.
- Opened the application grid through noVNC and launched real Mousepad using
  its GIO desktop entry. Typed `forge` using actual viewer keyboard events.
- Sent SIGKILL to the shell as UID 1000. Shell PID changed 1139 to 1230;
  compositor PID 1117 and Mousepad PID 1152 remained. The native panel and Dock
  returned and Mousepad retained its unsaved `forge` text. See
  `drm-before.json`, `drm-after.json`, and `drm-shell-restart.png`.
- Separate specification and quality reviews passed `ff17b40`, including the
  nested real pixel/input policy regressions. Reviewers inspected retained
  evidence; they did not independently rerun the whole Linux suite.

## Early measurement, not final performance acceptance

After minimizing Mousepad, collected 60.0002 seconds of idle samples as the
ordinary desktop user. `drm-idle.json` selects only the exact compositor and
shell executable names, excluding their descendants and ordinary applications.
Process identities were stable and PSS coverage complete. Combined PSS mean
71.20 MiB, maximum 71.49 MiB; CPU 1.63% of one core. Optional bounded frame
instrumentation was enabled. This is an M2 observation; M3 adds services and
the final identical-workload comparison, interaction/frame measurements and
eight-hour acceptance remain outstanding.

Existing Mousepad logs report a missing optional gspell library and AT-SPI
registration warnings. Editing worked; complete session dependencies and
accessibility integration remain M3 work. This isolated session still uses
development autologin and is not the release/default session.
