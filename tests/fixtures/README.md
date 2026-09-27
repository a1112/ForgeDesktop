# Isolated runtime fixtures

`m1-drm.service` is a temporary acceptance session for a disposable copy of the
ForgeOS graphics image. It retains the established ordinary-user PAM/logind
device path and replaces only the test copy's Weston activation. It is not the
final LightDM session, not a login/authentication implementation, and must never
be installed as the current daily VM's default. Its failure path requests the
existing tty1 getty; graphical login-manager recovery is a separate required gate.

Mask the old graphics ready/probe services in that test copy before enabling this
fixture. Leave the production Forge service readiness, permission and sandbox
units intact. Boot only after unmounting and detaching the image from the builder.

Initial snapshot-mode diagnostics did not reach `forge-ready.service` completion.
A subsequent persistent disposable-image boot passed the gate and shut down
normally. The fixture retains its dependency on that gate. A Wine helper's
seccomp core dump alone is not evidence of gate failure: inspect the final
`FORGEOS_READY` record. Graphical-login recovery is still a separate acceptance
item. The working directory is `/`; this test does not rely on Weston's state
directory having been created by a masked service.

This OVMF/virtio-vga test boot assigns simpledrm minor 0, then virtio_gpu minor 1;
the fixed test unit targets `/dev/dri/card1`. Verify the boot's kernel/udev records
before reusing the fixture. Production sessions must discover their seat's GPU.
The explicit `env XDG_RUNTIME_DIR=...` in ExecStart restores the writable managed
runtime directory after PAM, as in the existing ForgeOS Weston service.

`m1-session.sh` and `forgedesktop-m1.desktop` exercise a real LightDM Wayland
session in a separate copy of the known-hash daily v3 base, leaving XFCE present.
`m1-fault.sh`/`.service` intentionally SIGKILL only the matching UID 1000
compositor after 60 seconds. They require an explicit isolated-image marker
(`/etc/forgedesktop-isolated-test` containing `forgedesktop-daily-test`), must
never be packaged for production, and are removed after fault acceptance.
