# Native XWayland and ForgeOS GUI broker, isolated VM

This is an interim M3 application sample, not the M4 stability gate. The guest
is the marked `forgedesktop-daily-test` copy, 2 vCPU / 4 GiB, QEMU virtio-vga
with two 1280×800 heads, no NIC. The user's daily VM and XFCE session were not
modified. The first compositor candidate had SHA-256
`e6ad481a7edcadcd579559cf65c1f5f62d95f760cbfe9aa32a4d41a768a20135`.
The final retest used SHA-256
`a19a6ae86883d829b7a777bedaccf3b89cd18272eb5ed388be3688e23b38e3cc`,
independently rebuilt from committed source `e280e40`.

On a normal boot, the native compositor started rootless XWayland as `:0` and
created `/tmp/.X11-unix/X0` owned by `forge`. The X server reported access
control enabled and `SI:localuser:forge`. For this isolated broker test, the
existing ForgeOS model was applied to the new socket: grant only `forge-appd`
socket read/write ACL and `xhost +si:localuser:forge-appd` from the forge
session. These grants currently need integration with XWayland restarts; they
are not yet a released setup path.

The real `/usr/libexec/forge/forge-sandboxd --gui-test` path launched two
registered Wine 11 / CompatForge applications under `forge-appd`. The UI was
observed in noVNC, then closed with Alt+F4. The broker returned exit 0 with
the following expected digest and lifecycle markers:

| App | Registered PE SHA-256 | Observed |
| --- | --- | --- |
| `dev.forge.wine-notepad` | `d0d8639b415c1973ead33f1709c041be88bffe5ca28e28b2efe9f16bc3dced22` | `FORGEOS_GUI_LAUNCHING`, `FORGEOS_GUI_READY`, `FORGEOS_GUI_ADMITTED` |
| `dev.forge.wine-winemine` | `e7b53033db0c26dff1c53f7e15c65fea1c6c999b9f4bbaca743c44fe544b1553` | Same three markers; [visible VM screenshot](winemine-broker.png) |

On the final retest, [Notepad](notepad-final.png) rendered a real editable X11
window and [WineMine](winemine-final.png) rendered its compact game window,
without the earlier oversized black region. Both final broker runs exited 0
with all three lifecycle markers and the registered PE digests above.

The ordinary-user real Wayland `scale-output 1` probe (SHA-256
`63494b282725fd79d4492b76c914cbf37d022e47672e876af670aac1b4ab9278`)
showed its purple viewport on head 1. At saved 200% it reported
`preferred-scale:240` and `logical-size:640x400`. During a temporary 150%
change on the same head it reported `preferred-scale:180`; after the 15-second
unconfirmed setting reverted, it reported `preferred-scale:240`. The shell
display-settings text bound the changed scale to the wrong row in this
candidate. The rebuilt shell changed the second output row from 200% to 150%
while the first stayed at 100% ([screenshot](display-head1-150.png)); the same
real Wayland probe logged `preferred-scale:180`, followed by `240` when the
unconfirmed setting reverted. The incorrect-row UI issue is resolved for this
two-output case. XWayland broker ACL/xhost grants were applied manually after
boot and still require a release integration that survives XWayland restarts.
