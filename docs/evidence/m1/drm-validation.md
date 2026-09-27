# M1 independent DRM runtime — 2026-09-27

The independent compositor/input subset passed in a disposable VM. Full M1
also passed graphical login recovery below. Specification and quality reviews
passed after input lifecycle fixes. M1 is accepted at its scoped milestone;
M2–M5 and the remaining M0 performance baselines are not completed by this test.

## Environment and build

- QEMU/KVM q35, 2 vCPU, 4 GiB, virtio-vga, USB tablet, OVMF, no network.
- Arch snapshot 2026/08/01; Linux 6.18.41-1-lts. Real Qt 6.11.1 and GTK
  3.24.52 packages installed with Arch signature verification.
- Ordinary `forge-graphics` UID 964, PAM/logind seat, private runtime directory.
- Smithay 0.7.0, Pixman, double DRM dumb buffers, XRGB8888 scanout, 1280×800.
- Installed binary SHA-256:
  `df0d0a95abb0cae9e38f4567e525921b62e2ef8054327bbb759750362c6e57f1`.
- Disposable image: `/srv/forge-desktop-build/forgedesktop-m1.raw`, copied from
  the prior package test image. The live daily overlay and base were untouched.
- Temporary unit/client fixtures are in `tests/fixtures`. They are not a
  production login session or a replacement for the final ForgeOS installer.

## Observed results

| Check | Observation |
|---|---|
| Core readiness | `FORGEOS_READY` before compositor startup |
| Independent output | DRM readiness at 1280×800; actual GTK and Qt simultaneously visible |
| Keyboard routing | QEMU key input became `forge` in GTK, then Qt after pointer focus |
| Move | Dragging GTK's client titlebar visibly moved its real surface |
| Resize | Qt right-edge drag increased logged content width 634 → 734 |
| Wheel | QEMU wheel event traversed libinput and Wayland: Qt logged `qt-wheel:0,120` |
| Normal shutdown | QMP ACPI powerdown reached system power-off and QEMU exited |

See `drm-resized.png` (manually inspected), `drm-client.log` and the filtered
guest `drm-journal.log`. QMP input targeted only the isolated VM's private socket.
The glyphs demonstrate text rendering, not Fcitx candidate or Chinese input tests.
No performance thresholds were measured here; kernel DRM debug was enabled to
diagnose initial modesetting and must be disabled for performance acceptance.

## Failures found and corrected

1. The masked Weston unit had not created its working directory. The temporary
   M1 unit now uses `/` rather than relying on that unrelated state directory.
2. PAM changed XDG_RUNTIME_DIR; the service now explicitly restores its managed
   writable runtime directory in ExecStart, matching ForgeOS's established pattern.
3. Firmware simpledrm occupied minor 0 before virtio_gpu registered minor 1.
   The fixed fixture selects the observed `card1`; production needs GPU discovery.
4. The DRM atomic test rejected AR24 on the primary plane. The compositor now
   checks XRGB8888 support and allocates that format directly. The next boot
   rendered both clients; no root or hardware rendering workaround was used.
5. Review found missing DRM axis forwarding. Both-axis/source/v120/finger-stop
   regression tests and actual Qt wheel delivery now cover that path.

Early snapshot-mode boots did not show core-readiness completion before they
were stopped. Persistent isolated-image boots passed it. A Wine helper's
seccomp core dump also occurs in a passing readiness run; it is not by itself
evidence that the readiness gate failed. The earliest snapshot boots are not
counted as successful shutdown or stability cycles.

## Real LightDM session and compositor failure

A separate `forgedesktop-daily-test.raw` was copied from immutable daily v3 base
SHA-256 `b1fe2525c2404e668d0212b9f91bbc61467cffad63b1205e5ebec33dcd75670f`.
Qt packages were signature-verified, the M1 Wayland session/probes installed,
and only this disposable copy's development autologin selected that session.
The current daily VM's base and overlay were unchanged; XFCE remained installed.

LightDM launched ForgeDesktop as `forge`, UID 1000, and both real GTK/Qt windows
were visibly present. An explicitly marked test fixture then SIGKILLed that
exact compositor process. LightDM stayed running and created a fresh greeter
session. `lightdm-after-crash.png` shows the actual graphical login form;
`lightdm-fault.log` records the killed UID/PID and subsequent greeter session.
The test VM then shut down normally through ACPI and the fault unit was disabled.

No password was entered or changed, and no authentication/lock-screen acceptance
is implied by this recovery test. The ordinary applications lose their display
when the compositor dies; preserving apps during a *shell* crash is M2's distinct
requirement. This injected crash is not counted as a normal M4 stability cycle.

## Reviewed build recheck

After `362fef5`, binary SHA-256
`171b35ef88413ce69fbb5faaf1dd6bdd1dbf209cd26b7218a3bac4ac6d90fb55`
was installed offline into the stopped LightDM test copy and booted again.
The real noVNC session showed both clients; typing `forge` in GTK, moving its
titlebar, focusing/typing `forge` in Qt and resizing Qt were visually rechecked.
See `lightdm-latest-input.png`. The focused quality re-review passed all three
findings (buffer mapping, stationary pointer targeting, host modifier focus),
supported by the committed native Wayland lifecycle regression fixture/logs.
