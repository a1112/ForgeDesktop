# noVNC response measurement fixture

`tests/fixtures/novnc-measure.html` and `.js` run alongside the distribution's
original noVNC `core/` and `vendor/` modules in a separate test web root. No
upstream modules or the user's existing viewer are modified. The current lab
web root is `/srv/forge-desktop-build/novnc-test`, served on loopback 6084 over
the existing SSH tunnel to the marked disposable VM's Unix VNC socket.

The page records the browser pointer-down event timestamp and polls a selected
guest pixel rectangle with requestAnimationFrame. It reports the first poll
with at least 32 sufficiently changed sampled pixels (or all samples in a tiny
rectangle). The canvas resolution and ROI accompany each sample. Limits are
65,536 ROI pixels, 100 observations and a three-second timeout. Results remain
in a visible readonly textarea; there is no upload or telemetry endpoint.

## Instrument validation, not performance acceptance

The real 1280x800 M1 test guest was used to validate the instrument:

- Clicking the visible Qt title bar raised it above GTK. The selected region
  contained the previously visible GTK title bar and visibly became Qt content.
  The first changed-pixel observation was **33.6 ms**.
- Clicking an already focused blank Qt area left that region unchanged. The
  instrument correctly recorded **timeout at 3004.3 ms** instead of success.
- Exact exported observations: `novnc-timer-smoke.json`; screenshot:
  `novnc-timer-smoke.png`. JavaScript syntax check passed.

These two deliberately different instrument checks are not a performance
sample set, not a R-OS baseline and not a ForgeDesktop latency acceptance.

## Measurement procedure for the final comparison

Fix the approved VM resources/output and use identical browser/network conditions
for each desktop. Choose an ROI whose visible change represents the requested
launcher operation, away from the cursor, clock and unrelated asynchronous
content. Capture before/after screenshots to prove this. Warm the launcher,
record repeated open operations with a descriptive case name, and preserve
timeouts/disconnections/resizes rather than silently dropping them. Reset and
export separate named runs for baseline and native desktop.

This measures DOM input to **first visible ROI change**. At 60 Hz the polling
resolution is about 16.7 ms; background tab throttling invalidates a comparison.
Browser canvas readback adds overhead. It includes VNC encoding/transport/decode
and browser rendering delays, but cannot identify the guest's physical scanout
time, content-complete response, or isolate each component. Report this separate
from the compositor's render/submission and shell handler-to-submission records.
Do not infer a native frame-time gate from noVNC measurements.
