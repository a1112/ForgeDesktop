# noVNC fragmented-frame investigation (2026-09-28)

The user's noVNC page showed fragmented, retained Thunar/Firefox pixels.
QMP `screendump` of the same QEMU output showed a complete and current frame.
Reloading the affected page forced a complete RFB frame and immediately
restored the correct image (`after-reconnect.png`). This rules out corrupted
files and a permanently damaged guest scanout. The mismatch lies somewhere
between QEMU's VNC updates, noVNC's canvas, and the browser's tab rendering.

The test VM is marked `forgedesktop-daily-test`, served through loopback
websockify on port 6084. The daily VM on port 6083 was not changed. A second,
agent-created noVNC tab sometimes displayed only small parts of an updated
window (`two-clients-before.png`) while the first tab and QMP showed the full
frame. That tab was hidden, so browser background throttling is a plausible
confounder. Two VNC clients were confirmed with QMP `query-vnc`, but this
observation alone does not prove a QEMU multi-client defect.

## Interventions

- Omitting DRM `FB_DAMAGE_CLIPS` in the isolated guest did not remove the
  missing-window symptom. The compositor source and test-guest binary were
  restored to the original build (SHA-256
  `99593a653c65bd35c23ed87018ae122860d05e67c2efbace7643d5da32c975f9`).
- Forcing full Pixman repaint on each changed frame also failed to make the
  hidden second viewer reliable. This candidate was reverted.
- Disabling noVNC ContinuousUpdates or CopyRect in temporary copies did not
  yield a convincing fix. The stock noVNC JavaScript was restored.
- With the extra VNC tab closed, the primary viewer showed a clean Thunar
  window and QMP reported one VNC client. Backgrounding the primary tab,
  launching Thunar, and returning did not reproduce the corruption in that
  single trial.

## Current disposition

The observed screen can be repaired immediately by reloading the affected
noVNC page. This is a display-client reset, not a VM reboot, and leaves guest
files and applications intact. The underlying intermittent update loss is not
yet fixed. A reliable fix requires a repeatable visible-client reproducer
and comparison of the RFB rectangle stream, browser canvas, and QMP frame.
