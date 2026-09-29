# ADR 0004: R-OS per-window bridge

Status: accepted architecture; implementation partial, runtime admission CLOSED.
Date: 2026-09-29. Authority: user approved separate web windows for Linux/Android
applications, the existing R-OS visual design, one shared OS user/session, Rust
services, and a restricted, pinned KWin extension.

This is a narrowly scoped exception to the public-extension-only policy in the
2026-09-28 KWin design. A compositor-side adapter may use fixed-version KWin
interfaces for window capture and atomic targeted input. It must be rebuilt and
requalified with each pinned KWin update. No upstream fork, arbitrary command
execution, root session, unrestricted global capture/input or desktop cropping
is authorized by this exception. Existing package pins remain unchanged until
an adapter has passed actual runtime gates.

KWin owns native windows. The authenticated R-OS Rust broker owns browser grants.
ForgeDesktop owns the local adapter, identity/geometry/seat policy and native
visual integration. Linux/Android apps retain their native content; React owns
R-OS chrome. Every top-level maps to an independent web window. Popups follow
their verified transient chain; separate dialogs receive their own window/stream.
An app_id, title or PID alone is not authorization. Android runtime identity must
be correlated by its trusted adapter, never assumed from shared process metadata.

The current Rust executable is a policy process and the C++ companion is an
observer only. Neither is an implementation of compositor-atomic input. Standard
portal keyboard injection has no window target; focus-then-inject has a race.
No code may convert successful policy admission into delivered input. Capture
and input capabilities stay false until the final compositor gate exists.

The same physical seat is shared. One remote controller holds its lease. Local
interaction preempts remote input; a compositor adapter must revoke the lease,
release held input and require reacquisition. Lock or disconnect stops input and
streams. Only KScreenLocker/system session state can report unlock; a web login
or changed React screen does not unlock the system. The existing upstream locker
remains in place; no replacement password UI is installed by this increment.

P0 gate: independent real Qt/GTK/XWayland/Android window streams, popups extending
past their parent, modal dialogs, occlusion/minimization, scaling/resizing,
destroy/recreate, local focus races, no unauthorized pixels or input, stale
geometry rejection, disconnect/lock/revoke and recovery. Software VM and real GPU
results must be separate. State-machine and observer tests are not these gates.

Rollback: stop observer/bridge, disable the optional KWin observer script, retain
R-OS state and current Plasma/XFCE recovery. No default session is changed.

Sources: KDE KWin scripting API; KDE WindowScreenCastSource/ScreencastManager;
XDG ScreenCast and RemoteDesktop portal interfaces (links in bridge-v1.md).
