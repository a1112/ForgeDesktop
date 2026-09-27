# Dual DRM output candidate: isolated VM observation

2026-09-28. This is an M3.1 **candidate check**, not full output acceptance.
The debug compositor was built from uncommitted multi-output changes and must be
rebuilt, reviewed and retested after the work is committed. The user's daily VM
and its overlay were not modified.

## Fixed test conditions and installation

- Marked disposable image: `forgedesktop-daily-test.raw`; guest marker
  `/etc/forgedesktop-isolated-test=forgedesktop-daily-test` checked before access.
- QEMU/KVM, 2 vCPU, 4 GiB, `virtio-vga,max_outputs=2`, 1280x800 per head;
  ordinary UID 1000 LightDM compositor, Pixman and DRM dumb buffers.
- The guest shut down normally by QMP `system_powerdown`. The host verified no
  process held the image before attaching `/dev/nbd0`; the exact M2 binary SHA
  `c8d451a7f618712bf59e82073276181096e24439b4d8c58ea9285cb2ca2342eb`
  was saved for rollback. The candidate SHA
  `6d32efdd4837b5b99acb2f80aa24215eee0be3ed99d9a56b82845a41ea4c2cda`
  was installed offline and verified in the guest after boot.
- Both NBD and the root mount were released before the VM restarted. Its network
  remained disabled; no test package or lab guest-agent tool is part of a release
  bundle.

## Real hardware and Wayland sequence

The same compiled ordinary Wayland `output-probe` asks for the exact output count
and prints each `wl_output` name, logical origin, mode and integer scale. On the
old M2 compositor, with the virtual second connector connected (diagnostic
kernel detect used only to refresh the old driver state), `output-probe 2`
failed with `outputs:1`.

The candidate was then booted and tested **without a diagnostic sysfs detect**:

| Hardware request | Guest connector state | Ordinary client result | Compositor |
|---|---|---|---|
| head 1, 1280x800 | both connected | 2 outputs: `Forge-DRM-1` at `(0,0)`, `Forge-DRM-45` at `(1280,0)`; both 1280x800, scale 1 | PID 539 alive |
| head 1, 0x0 | second disconnected | 1 output, `Forge-DRM-1` | PID 539 alive |
| head 1, 1280x800 again | both connected | same 2 outputs restored | PID 539 alive |

The guest session log records `output added`, `output removed`, then `output
added` for connector 45. The noVNC head-0 screenshot shows the live ForgeDesktop
shell; head 1 connected and showed only the dark background: [head 0](dual-output-head0.jpg),
[head 1](dual-output-head1.jpg). A client window rendered on head 1 has **not**
yet been proven, so this does not establish full dual-screen rendering, pointer
mapping or window recovery.

## Remaining acceptance

Rebuild from a committed/reviewed source revision; show an actual application on
the second head, remove that output with an application on it, and verify recovery
on head 0. Test 100%, 150%, 200% scale, pointer/candidate placement, actual
settings apply/confirm/revert and persistent config. Capture the two viewer
screens and compositor log at each step. Then run the broader M3.1 app matrix.
