# Private shell protocol v1

The compositor spawns only `/usr/libexec/forge-desktop/forge-shell`, as the
ordinary session user. Its stdin is one end of a new Unix stream socket pair.
There is no socket pathname, listening control port, exec verb or arbitrary
shell path. Rust uses `OwnedFd`/`Stdio`; no unsafe boundary is added. The Qt
process sets FD_CLOEXEC before Qt/GIO initialization. Launched CMake was checked
with stdin `/dev/null`, not the private socket.

Each message is a four-byte unsigned big-endian length followed by UTF-8.
Maximum payload 65,536 bytes; zero length rejected. Input buffered bytes <=
131,072; commands <=128 bytes, <=32 dispatched per compositor tick, <=16KiB
read per tick. One output frame plus one tiny presentation event is pending;
new snapshots coalesce until writable. Qt outgoing pending bytes <=4,228.
Invalid frame/version/verb disconnects and restarts the shell. Four workspaces,
up to 52 mapped roles/windows, title/app-id metadata truncated to 256 bytes each.

Fields are tab separated. No command accepts an executable or file path:

- `1\tactivate|close|minimize|restore|maximize|fullscreen|normal|left|right\tID`
- `1\tworkspace\t0..3`
- `1\tmove\tID\t0..3`
- `1\tlauncher\t0|1\tSERIAL` (unsigned 32-bit correlation number)

IDs look like `w0000000000000004`, are opaque to clients, contain no PID/pointer,
and are never reused in one compositor lifetime. Stale IDs are rejected against
the live mapped-window set. Maximize/fullscreen toggle, `normal` clears both,
snaps use the work area. Activation restores and switches to the window's
workspace. Lock policy gates controls; M3 still must implement real locking.

Authoritative snapshot header: `1\tstate\tWIDTH\tHEIGHT\tWORKSPACE\tLAUNCHER\n`.
Each window line: `ID\tTITLE_HEX\tAPP_ID_HEX\tWORKSPACE\tMINIMIZED\tMAXIMIZED\tFULLSCREEN\tFOCUSED\n`.
Lists are ordered by stable ID. State omits shell surfaces. Hex metadata cannot
inject delimiters; QML displays titles as PlainText. No output configuration
verb is advertised until M3 implements tested mode transactions.

Shell surface titles `forge.background`, `forge.panel`, `forge.dock`, and
`forge.launcher` only gain special placement after Wayland credentials match
the currently live spawned child's exact PID and UID. Title/app-id alone is
never authorization; duplicate privileged roles are rejected. Normal apps
are below panels; launcher receives keyboard focus when intentionally opened.
Top 38/bottom 84 pixels are reserved from maximized/snapped work area.

Shell exit/EOF/protocol failure tears down only the child/socket, preserving
all other Wayland connections. Restart backoff is 0.5s, 1s, 2s, 4s, 8s, 16s
(capped), reset after a minute of healthy runtime. A fresh child receives an
authoritative snapshot. Failed spawning uses the same bounded backoff.

## Optional timing records

Set `FORGE_DESKTOP_PERF_FILE` to a **new** private output path. Existing files
are never overwritten. CSV header `kind,elapsed_us,damaged`; rows `frame,N,0|1`.
At most 100,000 rows. Duration covers a dirty render attempt (Pixman composition,
damage handling and X11 upload/flush or DRM atomic/pageflip submission, frame
callbacks), not event-loop idle, vblank wait, scanout, browser decoding or input
transport. `damaged=0` attempts are separately identifiable and must not be
silently mixed with actually composed frames. This trace is not a workload
classifier: the caller must label drag/animation/idle measurement intervals.

With the same opt-in variable, stderr contains up to 10,000
`ForgeDesktop launcher-submit-us=N` samples from QML click handler calling
`showLauncher(true)` through Qt Quick's first `frameSwapped`, and
`ForgeDesktop launcher-compositor-submit-us=N` samples through a matching
`1\tpresented\tSERIAL` acknowledgement. The latter is queued only after a
damaged frame containing the launcher is submitted by the compositor. Both
use one process's monotonic elapsed timer, and correlation prevents delayed
acknowledgements from satisfying a subsequent request. Neither sample claims
physical presentation or noVNC end-to-end latency. The time before the QML
handler (input transport/dispatch) is not included. Default operation writes
neither perf file nor timing log.
