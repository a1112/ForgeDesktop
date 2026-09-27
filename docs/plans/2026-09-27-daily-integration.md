# M3 daily integration sequence

This refines the already approved complete-desktop scope. Execute after M2
specification and quality reviews pass. Keep changes in the native-desktop
branch; each implementation task needs real Linux evidence and two-stage review.
Do not interpret any subtask as full M3 acceptance.

## M3.1 Output, input and application interoperability

Extend the existing Smithay backend rather than introducing another compositor.
Connect policy outputs to actual DRM connectors/CRTCs and nested test outputs.
Test two outputs, hot removal, logical placement, 100/150/200 percent scale,
pointer coordinate mapping and window recovery when an output disappears.
Output apply/confirmation/revert must reach the real backend, not only the
existing pure policy model. Use a bounded timeout and revert unconfirmed modes;
save confirmed settings atomically into a versioned private user directory.

Complete real cursor surfaces, clipboard/primary selection and drag/drop,
including text, UTF-8 and file URI transfers. Add XWayland with real X11 windows,
selection/focus and crash recovery. Do not treat an X11-host nested backend as
XWayland application support. Run GTK, Qt, Electron and existing CompatForge
applications through their actual native/X11 paths and document limitations.

Add text input and input method protocols supported by Smithay, connecting
Fcitx 5 to actual focus/caret geometry and candidate surfaces. Restrict privileged
input-method roles to the desktop's authorized IME process; ordinary apps must
not become keyboard interceptors. Test Chinese composition and candidate
positioning in GTK/Qt/Electron, focus changes and IME restart. Use installed
toolkit Fcitx modules where necessary and record the chosen application path.

## M3.2 Lock boundary

Implement ext-session-lock-v1 with PAM-backed swaylock. Until all active outputs
are covered, blank them and withhold input from ordinary surfaces. A lock-client
crash keeps the session locked; only the protocol-authorized unlock completes
the state transition. Lock cannot be bypassed by a panel, popup, fullscreen app,
new output, workspace change, stale control message or shell restart.

Publish lock-state events only to inherited authorized desktop service channels.
Use that same compositor-owned state to stop clipboard host synchronization and
screen capture before any new pixels/selection content can be exported. Never
rely solely on a shell-visible boolean. Test failure, restart and output-change
cases in the disposable guest. Do not set or change the user's password; user
authentication and final autologin removal remain the explicit final gate.

## M3.3 Native session services and settings

Add the session notification service and StatusNotifier tray, including close,
actions, persistence bounds and untrusted plain-text app content. The shell
owns their visual surfaces; a shell restart must reconstruct current state.
Prevent competing notification daemons when entering the native session.

Implement controls using the real installed network provider, PipeWire and
WirePlumber, display/input configuration, theme/default applications and
logind power actions with existing Polkit mediation. Show actual provider
failures and denied operations. Reuse existing settings applications when they
provide a complete operation; do not display simulated toggles. Add the existing
Forge app launch broker path and preserve ordinary GIO desktop-entry launch.
GNOME Software/Flatpak and default file associations must work in this session.

## M3.4 Portals and host integration

Keep GTK's file chooser backend. Implement an independently restartable native
screenshot/ScreenCast backend using portal D-Bus contracts and PipeWire. Actual
whole-output and single-window capture need user choice, consent, deny/cancel,
stop and revoke. Validate backend callers against the portal broker's actual
bus identity; never grant access just because a caller supplies an app ID.
Private compositor capture access must remain inherited, typed and bounded.
Window capture must not reveal other overlapping windows. Lock terminates
active streams and refuses pending/new requests. Do not implement remote control
or global input injection.

Connect a Wayland text clipboard agent to the existing QEMU/vdagent host path,
with an explicit opt-in setting, bounded UTF-8 transfers, loop suppression and
compositor-owned lock gating. Verify Chinese text both ways with Windows.
Retain noVNC and establish a host-loopback SPICE channel protected by SSH for
audio. Verify PipeWire routing and actual Windows playback, recording what was
observed; a nonempty audio buffer alone is not listening acceptance.

## Evidence and delivery handoff

Pin all newly used third-party source and Arch package dependencies and retain
license provenance. Re-run the protocol/policy/Qt suites after integrations, then
the actual application and negative-permission/fault matrix. Only then start
the full eight-hour mixed workload and twenty normal session/reboot cycles.
Record elapsed time, process identities, errors, memory trend and saved files.
QEMU Guest Agent diagnostics are confined to the marked disposable test image;
they do not prove ordinary-user permissions and are excluded from the release.

M5 still requires measured performance against the R-OS baseline, a verified
external bundle and complete new image, ForgeOS's twelve checks, documentation,
normal shutdown/backup of the current instance, usable account authentication,
default-session switch and retained XFCE recovery plus visible real desktop.
