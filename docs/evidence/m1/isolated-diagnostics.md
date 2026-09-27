# Isolated guest diagnostics

The disposable `forgedesktop-daily-test.raw` now includes signed Arch snapshot
packages `qemu-guest-agent 11.0.3-1` and `numactl 2.0.19-1`. Their archives and
detached signatures were checked by pacman against the existing pinned builder
keyring. This test-only addition is excluded from the release artifact/image.

Normal QMP ACPI shutdown preceded offline installation. After restart, actual
Guest Agent `guest-exec` returned the process list: qemu-ga PID 371 UID 0,
compositor PID 595 UID 1000, Qt probe PID 620 UID 1000, GTK probe PID 716 UID 1000.
This establishes that the diagnostics channel and existing desktop session both
run in the isolated VM. It is not a performance or M4 cycle acceptance result.

The service drop-in is `tests/fixtures/isolated-qemu-guest-agent.conf`. The
required marker is `/etc/forgedesktop-isolated-test` containing exactly
`forgedesktop-daily-test`. The channel uses QEMU virtio serial and a Unix socket
at `/srv/forge-desktop-build/daily-test-vm/qga.sock`, beneath an owner-only host
directory. No guest NIC, TCP listener or production-instance selection is added.

The trusted VM host can execute root diagnostics in its disposable guest using
`tests/fixtures/isolated_guest.py`. It synchronizes the QGA stream, bounds
responses, verifies the guest marker before the requested executable, and
passes an argument array without shell expansion. Commands that need desktop
permissions must explicitly use `runuser -u forge`; root execution does not
prove that an ordinary desktop user has permission. A command timeout does not
kill its guest process; inspect the guest before retrying a mutation.

QEMU launch additions:

```
-device virtio-serial-pci
-chardev socket,path=/srv/forge-desktop-build/daily-test-vm/qga.sock,server=on,wait=off,id=qga
-device virtserialport,chardev=qga,name=org.qemu.guest_agent.0
```

This fixture is never installed into the user's current daily VM, which remains
on its existing XFCE/R-OS base and overlay. Protocol reference:
https://www.qemu.org/docs/master/interop/qemu-ga-ref.html
