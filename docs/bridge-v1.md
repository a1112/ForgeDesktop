# Forge window bridge v1

## Transport and trust

`forge-window-bridge --session-epoch NONZERO_U64` uses private inherited stdin/
stdout, UTF-8 newline-delimited JSON, max 65,536 bytes including newline. The
supervising authenticated broker creates a fresh unique session epoch whenever
KWin/adapter restarts. For the web-connected broker, allocate epochs no larger
than 9,007,199,254,740,991 (JavaScript Number.MAX_SAFE_INTEGER), not random u64
values. All HTTP/WS-facing epochs, generations and sequences must pass integer
and safe-range checks before conversion in either direction; reject out-of-range
values, never round them. The local core retains u64 for non-web consumers.
On safe-range exhaustion, fail closed and establish a newly authenticated
session rather than wrapping counters or resetting an active lease.
This is not an HTTP server. Never forward browser JSON to
this control pipe: observe, grant, revoke, lock and compositor_target are trusted
adapter/broker-only inputs. On EOF or fatal framing error revoke grants. The
supervisor must release held input and stop all streams on process death.

Envelope: `{"version":1,"request_id":1,"command":{"type":"capabilities"}}`.
Reply: same version/request_id and either `result` or string `error`.
Unknown fields, wrong types, version, truncated/oversized frames fail closed.

Current capabilities are always policy=true, capture=false, atomic_input=false,
runtime_verified=false. Admission returns admitted=true, delivered=false.

## Types and commands

- WindowKey: `{session_epoch:u64,id:string,generation:u64}`. ID is at most 128
  ASCII letters/digits, `_`, `-`, `{`, `}`. UUIDs are suitable. Generation must
  strictly increase upon reusing an ID; retired handles are never accepted.
- Geometry: `{x:i32,y:i32,width:u32,height:u32}` in logical compositor units;
  dimensions 1..16384, origins ±1,000,000. A changed rectangle increments the
  geometry_epoch; the compositor adapter must also invalidate on scale/content
  transform changes even if the rectangle is unchanged (not connected yet).
- Window: `{key,parent:WindowKey|null,kind:normal|dialog|popup,geometry,geometry_epoch}`.
- InputRequest: `{controller,target:WindowKey,geometry_epoch,lease_epoch,sequence,event}`.
  Sequence strictly increases per seat lease. Event is `{type:pointer,x:u32,y:u32}`
  in window logical coordinates; `{type:key,code:u32,pressed:bool}` with Linux
  evdev codes 0..767; or `{type:button,button:u32,pressed:bool}` for 272..279.

Commands (all tagged by `type`): capabilities; snapshot(offset=0,limit=64); observe(key,parent,kind,
geometry); geometry(key,geometry); close(key); lock(locked); grant(controller,
root); revoke; admit(request,compositor_target). The Rust enums are canonical.
Snapshot limit is 1..64; next_offset is null at the end. Every response is bounded
by the same 65,536-byte frame limit. The private command stream is serialized;
the broker must not insert observations between pages if it needs a stable list.
Parent must already exist. Descendants inherit a granted root; unknown/orphan
transients must be quarantined by the adapter, not attached by title or PID.
Closing a root removes descendants. KWin identity restart creates a new bridge.

## Observer implementation and remaining adapter

`services/window-bridge/companion` is a buildable Qt 6.8+ DBus executable. It refuses
root and accepts observations only from the current org.kde.KWin unique owner.
It observes the system ScreenSaver lock service, starts locked on uncertainty,
and exits locked on KWin/locker owner change. Its private stdout emits bounded
JSON events, not the bridge command envelope. The supervised reducer maps UUIDs
to generation keys and quarantines unresolved parents. The broker must still
validate app ownership and serialize trusted policy commands separately;
title/app_id are advisory hints.
The optional KWin script supplies managed window metadata and does not mutate
windows. Script-visible popups are incomplete on some KWin versions; therefore
this observer is not the final compositor-side capture/input implementation.

Build in an isolated Linux directory:
`cmake -S services/window-bridge/companion -B BUILD && cmake --build BUILD`.
Run `ctest --test-dir BUILD --output-on-failure`. Start the observer under a
private broker-owned child before manually enabling the packaged KWin script in
a disposable test session. Nothing is auto-installed or enabled by this change.

## Supervised metadata reducer

`ObserverReducer::new(session_epoch)` accepts only a nonzero epoch no larger than
JavaScript Number.MAX_SAFE_INTEGER. `apply_frame` consumes the actual private
companion format (not the policy command envelope), including strict nested
fields/duplicates, version 1, valid UTF-8, exactly one newline and the 65,536-byte
limit. `apply_event` validates the same identity, geometry and hint limits for
trusted in-process adapters. IDs follow the companion's bounded opaque-ID syntax,
including braced KWin UUIDs. Caption/app_id follow Qt's 4096/1024 UTF-16-unit limits.

Live windows are bounded at 4096, quarantined observations at 4096 and retired
identities at 65,536. Duplicate live observations update geometry/title; changed
rectangles advance geometry_epoch. A closed UUID's next incarnation advances its
generation. Parent/type changes retire the old subtree and create a fresh key.
Unknown-parent transients are not live or authorizable. A parent appearing with
the same name does not promote cached children: a fresh trusted child observation
is required to bind the parent's current generation. Closing a root removes its
live and quarantined subtree. Active-window metadata is a hint, not input authority.

The reducer starts locked. Lock advances revocation metadata and clears activity;
disconnect, invalid frames/events, limits or safe-counter exhaustion lock/revoke
and terminally close the epoch. Same-epoch unlock/re-observation is rejected.
The supervisor allocates a new unique epoch and constructs a new reducer after
owner/child restart. All counters use the safe integer range without wrapping.
No reducer API grants a controller or admits/delivers input. Capture, atomic_input
and runtime_verified stay false even if a caller advertises otherwise.

`snapshot(offset, limit)` accepts 1..64 requested records and can return fewer to
fit its actual JSON byte budget. next_offset is null at the end. Quarantined
records are reported as a count and never exposed as live WindowKeys. Hint values
do not prove application/Android identity. The geometry counter tracks rectangle
changes only; scale/content transforms and compositor-atomic checks remain open.

The executable's additional fixed metadata mode is:

```sh
COMPANION_BUILD/forge-kwin-observer | BRIDGE_BUILD/forge-window-bridge --observer-events --session-epoch 7
```

Run both as the same ordinary desktop user with the real session bus. The broker
must own/authenticate the child pipe and allocate the epoch; do not attach a
browser or network stream to stdin. The Qt executable checks current KWin and
ScreenSaver unique owners. The reducer does not replace that provenance check.
For every companion event the mode emits complete bounded metadata pages before
reading another event. EOF emits disconnected, locked metadata; bad frames emit
closed metadata then exit unsuccessfully. This mode cannot consume grant/input
commands and leaves the original `--session-epoch` policy protocol unchanged.

Rust unit/state tests and process-level stdin tests run with:
`cargo test --locked -p forge-window-bridge`. They are metadata/protocol evidence,
not real KWin streams, pixels or input qualification. The coordinating supervisor
records actual companion-to-reducer runtime evidence separately.

Missing runtime pieces: authenticated broker/supervisor integration; pinned KWin capture/atomic
input extension; PipeWire/WebRTC media; content/decoration coordinate mapping;
popup union bounds and stream transforms; key/button release tracking;
compositor-side local-seat preemption; real app/Android identity proof. Keep
runtime capability false until these are tested together, never substitute a
desktop stream, crop or test pattern.

Official basis:
- https://develop.kde.org/docs/plasma/kwin/api/
- https://github.com/KDE/kwin/blob/master/src/plugins/screencast/windowscreencastsource.cpp
- https://github.com/KDE/kwin/blob/master/src/plugins/screencast/screencastmanager.cpp
- https://flatpak.github.io/xdg-desktop-portal/docs/doc-org.freedesktop.portal.ScreenCast.html
- https://flatpak.github.io/xdg-desktop-portal/docs/doc-org.freedesktop.portal.RemoteDesktop.html
