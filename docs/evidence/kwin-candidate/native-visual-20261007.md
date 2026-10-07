# Native R-OS visual and application acceptance

2026-10-07. This is scoped functional evidence on an isolated P0-derived
candidate, not completion of M3-M5, the new Rust backend, or a default switch.

## Safe activation and runtime defects

Select the explicit **Apply Forge Native Style** action from the KDE launcher,
or run `/usr/libexec/forge-desktop/forge-native-style` in the ordinary user's
running Wayland session. It applies the Forge look-and-feel without resetting
panel layout, initializes only missing KWin button/maximize preferences, and
reloads KWin through its supported `/KWin reconfigure` method. Existing explicit
preferences, including empty strings and `false`, are preserved. This means an
existing custom window layout remains custom. The session wrapper itself does
not write home configuration or switch the default session.

Upstream `plasma-apply-lookandfeel` applied the Aurorae library/theme but ignored
the extra button and borderless-maximize entries in package defaults. The new
explicit action closes that activation gap. Regression tests first failed for
the absent helper, existing/empty preference preservation, idempotence, root
rejection, and explicit reload failure. They pass with the helper.

Runtime also reproduced two layout defects. Plasma now defaults new panels to
floating, adding an 8px inset; the new top panel explicitly sets `floating =
false`. Passing comma-joined launcher IDs to `writeConfig` serialized a single
escaped string instead of the required list. Passing the typed array produces
six usable launcher entries in the intended order, including GNOME Software
when installed. Both source fixes had failing regression checks first.

The helper and desktop action are two closed, independently hash-checked
payloads, installed with modes 755 and 644. Python was already in the reviewed
runtime dependency inventory. No new package or private KWin API was added.

## Environment and isolation

The existing Hyper-V Linux builder was reached through its configured pinned
SSH connection. The immutable input was
`forgeos-ros-p0.raw`, SHA-256
`a70655efcf1c91330388a4e32f231259bd70480af0102448b3bfb887cb130fda`.
Only a separate sparse raw copy under
`/srv/forge-apps-test/lab/native-visual-20261007/run-7SOe0R` was patched, then
booted with `snapshot=on`, 2 vCPU, 2 GiB RAM, KVM, virtio graphics and NAT.
The existing 4 GiB guest and its viewer remained running. The source image was
hash-checked before and after preparation. No base image, default VM, existing
home profile, recovery session, or root filesystem dependency was changed.

The installed initial theme was the 35-file candidate from `0e2b4fec`, validated
by the ForgeOS consumer before patching. The follow-up activation helper ran
from its identical copied source in the private ordinary-user profile. The two
layout changes were applied through the public Plasma scripting method in that
same profile. This is evidence for those source bytes and settings; it is not
a fresh boot of a fully rebuilt release image or the later Rust implementation.

Actual versions were KWin/Plasma 6.7.3, GTK 3.24.52, GTK 4.22.4, Thunar 4.20.9,
Mousepad 0.7.0, XFCE Terminal 1.2.0, and Firefox 153.0.1. UID 1000 ran KWin,
Plasma, and applications. Startup environment reported
`GTK_THEME=ForgeROS:dark`. Software rendering and cold image I/O made startup
and later browser operations slow; this 2 GiB run is not a performance gate.

## Observed behavior

- Mousepad's titlebar drag changed geometry from `(320,162,640,508)` to
  `(470.078,264.124,640,508)`, measured with a read-only KWin script.
- Its green control maximized to `(0,32,1280,768)` with `noBorder=true`.
  The Fusion topbar showed the active title and live controls; Dock dodged.
  Fusion's green control restored the previous dragged position. Yellow set
  `minimized=true`; a Dock click restored and activated the same window. The
  normal red control removed the window after saving.
- Native clipboard paste and Mousepad's normal save shortcut wrote Chinese
  UTF-8 text to disk. Thunar's rename dialog renamed the file, then its normal
  copy/paste action created a second file. Both files retained SHA-256
  `066587ba22a3b24a556ff74310b073a56067f212728145eaa08c25303b4006c1`.
- Typing a command into the actual XFCE Terminal shell ran the probe and
  displayed `native-shell-ok`; its output file records `/home/forge`.
- The corrected Dock launched Firefox and System Settings. Settings displayed
  the shared graphite surfaces, blue selection, and left traffic controls.
  Firefox displayed a real public search result and retained its CSD fallback.
  GNOME Software's desktop action eventually produced an actual dark GTK4
  window; it still displayed “refreshing data” at teardown.
- The normal upstream locker rejected a wrong password while `GetActive`
  remained `true`. A correct disposable password entered through the normal
  password field returned to the desktop and `GetActive=false`. No privileged
  unlock, authenticator replacement, or `Qt.quit` path was used.
- KScreen actually changed scale from 1 to 1.5 to 2, with logs and screenshots,
  then restored scale 1 and 1280x800. At 1920x1080, logical geometries were
  1280x720 at 150% and 960x540 at 200%. The 32px logical topbar scaled with them.

## Failures and remaining gates

The first fixture had a root-owned `.config` parent. It prevented normal-user
theme writes and produced the initial light panel and dconf warnings. That
private directory was preserved by rename and copied to a new user-owned
directory before activation. Earlier preparation also rejected the Windows
tar's executable modes; a receipt-mode tar fixed it. Temporary guest SSH host
key generation lacked offline chroot entropy, so a separate temporary key was
generated on the builder. None required changing production state.

The first output-mode commands omitted the refresh/ID required by this
KScreen version and failed. Commands using observed mode ID 13 succeeded.
Fast QMP text input under browser load produced a malformed search string;
the intended `example.com` navigation and later clipboard navigation were
not accepted. Public browsing was observed, but browser input/clipboard still
needs a dedicated paced acceptance run. The browser was terminated only in
the private guest to free memory for the store observation.

The virtual device exposed only one connected output despite a two-output
capacity, so no multi-output/hotplug acceptance is claimed. Chinese clipboard
editing was tested; new IME composition was not. The terminal viewport keeps
its application color preference while GTK chrome matches the shared palette.
Firefox and GTK4 CSD retain upstream controls. Store catalog/install, output
hotplug, repeated PAM cycles, persistence/reboots, fault/recovery, portals and
capture revocation, audio listening, latency, soak and delivery gates remain
open. Mousepad's optional spell plugin lacked `libgspell`; Thunar's optional
thumbnail service was absent. No theme CSS parse error was observed.

## Evidence and cleanup

Local evidence is under the native checkout's
`.cache/native-runtime-20261007/`: preparation/run proofs, QMP/guest scripts,
read-only window geometry snapshots, application journals, UTF-8 file hashes,
scale logs, and PNG screenshots including `fusion-maximized.png`,
`chinese-edit-saved.png`, `files-copy-renamed.png`,
`terminal-command-success.png`, `wrong-password-locked.png`, `pam-unlocked.png`,
`scale-150-final.png`, `scale-200-final.png`, `settings-runtime.png`, and
`last-screen.png`. The disposable password and private SSH key were not exported.

Own QEMU and websockify stopped through the owned QMP endpoint, exit 0 after
1596.75 seconds. The owned Windows tunnel was stopped. Their ports no longer
listen; existing guest/viewer PIDs 181253 and 73113 remained. This proves test
resource cleanup, not clean guest shutdown or crash recovery. Qualification
flags and the M3-M5 status remain unchanged.
