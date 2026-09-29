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
JSON events, not the bridge command envelope. The supervisor must map UUIDs to
generation keys, order parents, validate app ownership, and serialize commands.
The optional KWin script supplies managed window metadata and does not mutate
windows. Script-visible popups are incomplete on some KWin versions; therefore
this observer is not the final compositor-side capture/input implementation.

Build in an isolated Linux directory:
`cmake -S services/window-bridge/companion -B BUILD && cmake --build BUILD`.
Run `ctest --test-dir BUILD --output-on-failure`. Start the observer under a
private broker-owned child before manually enabling the packaged KWin script in
a disposable test session. Nothing is auto-installed or enabled by this change.

Missing runtime pieces: supervised event reducer; pinned KWin capture/atomic
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
