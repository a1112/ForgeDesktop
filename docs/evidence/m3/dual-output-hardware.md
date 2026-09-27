# Disposable dual-output hardware preparation

Host QEMU 10.2.1, guest Linux 6.18.41-lts. The marked daily-test VM uses
`virtio-vga,id=gpu,max_outputs=2`. Two owner-protected Unix VNC listeners select
`display=gpu,head=0` and `head=1`. Loopback websockify 6084/6085 is reached
through SSH; no host-wide listener was introduced. Guest remains 2 vCPU/4 GiB.

`tests/fixtures/isolated_output.py` restricts itself to that VM's head-1 socket,
checks the owner-only directory, guest marker and RFB server identity, then
sends a bounded RFB SetDesktopSize request. It sends no keyboard/pointer input.
Use `0 0` for removal or `1280 800` for reconnect. Viewers must use `resize=scale`
so automatic browser resizing cannot compete with the requested hardware state.

Observed both Virtual-1 and Virtual-2 connected after head-1 activation. QEMU
tracing confirms 0x0 requests and subsequent guest GET_EDID/GET_DISPLAY_INFO.
M2 does not yet reprobe connectors: sysfs status and a non-master modetest can
still show cached `connected`. A diagnostic `detect` write to Virtual-2's sysfs
status refreshed it to `disconnected`, proving the virtual device transition.
This privileged diagnostic is NOT compositor hotplug acceptance. M3 must react
to the event and force-probe connectors itself; its tests must not rely on that
diagnostic write. The fixture intentionally reports cached guest state without
forcing it. Rendering two outputs, scaling, recovery and mode rollback remain
unverified at this preparation stage.

Implementation references: [QEMU 10.2.1 VNC request handling](https://github.com/qemu/qemu/blob/v10.2.1/ui/vnc.c),
[virtio GPU output state](https://github.com/qemu/qemu/blob/v10.2.1/hw/display/virtio-gpu-base.c).
