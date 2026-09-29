# R-OS native session validation

2026-09-29, isolated candidate tests. These results do not complete M3-M5 or
authorize a default desktop switch.

## Scope and isolation

The input candidate is `forgeos-ros-p0.raw`, SHA-256
`a70655efcf1c91330388a4e32f231259bd70480af0102448b3bfb887cb130fda`.
It contains ForgeDesktop `065ada8` and the first-stage R-OS Rust artifact.
Tests use a private raw copy on the L-drive-backed Linux volume, with a fresh
QEMU snapshot for each boot. The original candidate, existing VMs and user
profiles are unchanged. The guest has 2 vCPU, 2 GiB RAM, virtio-vga software
graphics and no network device. This is functional evidence, not a performance
measurement.

Only the private copy selects `forgedesktop-kwin` for LightDM autologin and has
a disposable `forge` password for real PAM testing. This is not the release
authentication configuration. The public Rust unit remains opt-in in the
candidate; a test probe starts it in the guest's UID 1000 systemd user manager.

The first runtime check observed UID 1000 `startplasma-wayland`,
`kwin_wayland` and `plasmashell`, plus an active `r-os-rust.service`. The real
HTTP capabilities response reports authentication/files/settings available and
Android/window bridge unavailable. The locker changed its `GetActive` result
from `true` to `false` after entering the disposable password through the
normal upstream password field. No privileged unlock or authenticator bypass
was used. The displayed desktop and serial state both confirm the unlock.

## Selecting the candidate lock screen

The first test harness incorrectly wrote `kscreenlockerrc` / `Greeter` /
`Theme`; that run tested the upstream stock locker. In pinned KScreenLocker
6.7.3, the shell package comes from `plasmashellrc` / `Shell` / `ShellPackage`.
See [upstream source](https://github.com/KDE/kscreenlocker/blob/v6.7.3/settings/shell_integration.cpp).

For a disposable profile in an already running user Wayland session:

```sh
plasma-apply-lookandfeel -a org.forge.desktop
kwriteconfig6 --file plasmashellrc --group Shell --key ShellPackage org.forge.ros
kreadconfig6 --file plasmashellrc --group Shell --key ShellPackage
qdbus6 org.freedesktop.ScreenSaver /ScreenSaver Lock
```

These commands select the shell for that profile, not merely a cosmetic
Greeter setting. Preserve an existing user's configuration before any future
onboarding; this test does not install a system-wide default. A process
launched outside the user session also needs its actual Wayland display and
session bus environment. The first probe's visual-theme command lacked
`WAYLAND_DISPLAY`; the same command succeeded in the ordinary user terminal.
That failure was in the test harness, not missing Qt libraries.

Restore the upstream shell in this disposable profile with:

```sh
kwriteconfig6 --file plasmashellrc --group Shell --key ShellPackage org.kde.plasma.desktop
```

For a real existing profile, restore its recorded previous value instead.

## QML import defect and fix

The second run selected `org.forge.ros` correctly and reproduced a real theme
load failure: Qt rejected the bare absolute directory import on line 6 as an
invalid import URL. KScreenLocker stayed locked and displayed its emergency
password dialog; it still required the disposable account's correct PAM
password to return to the desktop.

The fix adds the explicit `file:` scheme to the installed, fixed upstream
directory. No authentication behavior changes. The bundle producer now
requires the valid import URL, and a regression test rejects the old form.
The new test failed before the fix; all 27 theme/bundle tests passed after it.

The exact fixed QML SHA-256 is
`b6d138615f515fa552c7d848d9a212e98809fa7cfdd4ab6f0b3b4f7024ca3c94`.
Only that QML payload was patched in the stopped private test image for the
next fresh snapshot. This is P0 plus the QML fix, not a rebuilt release image
and not the later P1 Rust service. The immutable P0 candidate still contains
the broken opt-in custom locker.

The fresh patched snapshot displayed the blue `R-OS` label over the full
upstream Chinese lock screen. A wrong password left the session locked; the
correct disposable password restored the native dark desktop. This is one
observed authentication cycle on the patched image. It does not qualify the
unpatched P0 image, multi-output behavior or crash recovery.

## Evidence and remaining gates

The workspace evidence lives under `artifacts/ros-p1/native/`:
`preparation.json`, `run-proof.json`, `serial-first.log`,
`upstream-unlocked.png`, `native-theme-first.png`, and the preparation/run
scripts. The first run stopped its own QEMU through QMP after its ten-minute
bound, exit 0. This was supervisor cleanup, not guest poweroff acceptance.

The failed-candidate journal is `serial-qml-failure.log`. Patched screenshots
are `ros-lock-branded.png`, `ros-lock-wrong-password.png` (still locked after
the rejected attempt), and `ros-unlocked.png`. The exact QML hash is also
printed by the patched guest before starting the service and locking.

`serial-patched.log` records KWin 6.7.3 / Qt 6.11.1, the expected QML hash,
PAM `unix_chkpwd` audit results `res=failed` followed by `res=success`, and
`GetActive` results changing from `true` to `false`. There is no QML import
load error in this patched run. `native-acceptance-proof.json` records these
checks and SHA-256 hashes of the log and screenshots; reproduce its assertions
with `summarize_native.py` next to the artifacts.

The patched run stopped its own QEMU through QMP after 508.56 seconds, exit 0.
The associated websockify process, loopback SSH tunnel and temporary browser
tab are also closed. No unrelated guest was stopped. As above, this proves
test-resource cleanup, not clean guest poweroff.

Candidate-specific R-OS locker evidence is recorded separately from the stock
locker result. Multi-output, suspend/resume, crash recovery, input/capture
revocation, repeated authentication cycles and security review remain open.
`X-Forge-RuntimeQualified` and window bridge runtime/capture/input flags remain
false until the associated gates pass.
