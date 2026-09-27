# Dual DRM display and configuration candidates

2026-09-28, marked disposable `forgedesktop-daily-test` VM only. All three
candidate binaries were built from uncommitted multi-output changes. This is
runtime debugging evidence; the final committed revision needs a fresh build,
review and acceptance run before M3.1 can be marked complete.

## Isolated setup

QEMU/KVM: 2 vCPU, 4 GiB, `virtio-vga,max_outputs=2`, 1280 x 800 per head,
Pixman and DRM dumb buffers. The VM's marker was checked before every guest
operation. For each binary replacement, QMP requested normal shutdown, the
host checked that no process held its image, mounted its own offline root,
verified the marker, saved the previous executable, verified the candidate
SHA-256, replaced the file and unmounted/disconnected NBD before boot. The
daily user VM and its overlay were untouched.

Paired Qt shell SHA-256:
`5c44058075542ea6fd5faff1ad3d9a29f8463fb4aa778d5e3e87e956940169ef`.
Compositor candidate SHA-256 values:

| Candidate | SHA-256 | Scoped result |
| --- | --- | --- |
| 1 | `4e0e83d8fd511605d081a146999714daed9dcdb70604300936514cef0619cb5a` | Two real outputs and head-1 client pixels; fullscreen on head 1 incorrectly hid head-0 shell. |
| 2 | `e9c268b8652bf006f746bbc51d419498b876e9cc3da326ab91eb6b701d8e5269` | Head-0 shell remained visible with head-1 fullscreen; saved head-1 scale was not restored after reboot and hot-connect. |
| 3 | `1b517cfa71038b54954f10192d5e0d9d78ba0e3e4dfb343ebd61d433ad6e8b66` | Saved 200% restored after reboot/hot-connect and later unplug/replug; pending edit canceled on unplug. |

## Observations

- In the ordinary `forge` Wayland session, `fullscreen-output 1` produced a
  real xdg-toplevel fullscreen on head 1. The separate noVNC head-1 view
  showed solid purple [candidate 2](head1-fullscreen-candidate2.jpg); screenshot
  center JPEG pixel was RGB (170, 51, 203), matching expected (170, 51, 204)
  after JPEG encoding. `fullscreen-ready` and `keyboard-enter` appeared in the
  fixture log. The compositor survived.
- On candidate 2, the head-0 [top bar and Dock](head0-while-head1-fullscreen-candidate2.jpg)
  remained visible while head 1 displayed the fullscreen client. Unplugging
  head 1 with that same client still alive migrated its purple window to head 0
  [without losing the process](head1-unplug-window-on-head0-candidate2.jpg).
  The compositor PID remained live and logged output removal.
- With both connectors active and the fullscreen fixture closed, a noVNC
  head-0 click at the Mousepad Dock icon launched real Mousepad PID 784 and
  showed its unsaved-session recovery dialog. This retested the earlier
  two-head absolute-pointer offset defect.
- Candidate 1's Displays UI offered 100%, 150%, 200% and a 15-second
  confirmation. A 150% preview displayed
  [Keep/Revert controls](display-150-pending-candidate.jpg), then automatically
  returned to 100%. A 200% preview followed by Keep wrote
  `/home/forge/.config/forge-desktop/v1/outputs.conf`, owned by `forge`, mode
  0600. It recorded head 1 as `(1280,0)` logical 640 x 400 with scale 2000.
- Candidate 3 rebooted initially with only head 0; on head-1 hot-connect, the
  [Displays panel reported 200%](restarted-head1-restored-200-candidate3.jpg).
  A second unplug/replug retained 200%. An unconfirmed 150% preview was then
  interrupted by unplug: Keep/Revert disappeared, the saved file stayed at
  2000, and reconnect again reported 200%.
- An ordinary user Wayland `output-probe` on candidate 3 returned two outputs:
  `Forge-DRM-1:0,0:1280x800:scale=1` and
  `Forge-DRM-45:1280,0:1280x800:scale=2` after restoring 200%.

## Outstanding gates

The candidate 1 failure and candidate 2 persistence failure were fixed in
later candidates, but no final committed/rebuilt artifact has passed this
sequence. At 150%, client-facing fractional-scale protocol support and
application appearance still need inspection. Multi-output candidate input
positioning, shell crash recovery, XWayland and the broader M3/M4 matrix remain
open. This record does not count as the 20-cycle or 8-hour acceptance run.
