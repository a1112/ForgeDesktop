# Native notification service design

The approved M3.3 scope requires a session notification service whose state
survives a QML shell restart. ForgeDesktop will own the session bus name
`org.freedesktop.Notifications` in a separate, ordinary-user process. It will
implement version 1.3 of the [freedesktop notification protocol](https://specifications.freedesktop.org/notification/1.3/protocol.html).
Qt 6 DBus is already shipped with the Qt base dependency used by the shell.

The service stores at most 64 live notifications and assigns nonzero,
monotonic IDs to fresh notices; replacement retains the requested ID. It
supports replacement, client close, expiry and explicit user
dismissal with the protocol's close reasons. Summary/body/app/action strings
are bounded before storage, and the shell renders them as plain text. Hints
and icon paths are not trusted as executable content. A full store evicts the
oldest entry with reason 4. A sender may replace or close only its own entry;
this protects apps from modifying each other's notices while permitting normal
same-session delivery. D-Bus itself is the transport limit; the service does
not advertise images, markup or sounds until those are actually rendered.
It advertises body text and action buttons, which the native center displays.
The complete serialized snapshot has a 10 MiB consumer limit: 64 entries times
at most 21,888 UTF-16 units of bounded display fields, at six JSON escape bytes
per unit, plus framing, fit below that limit. Tests cover the worst escaped
field lengths so a full legal store cannot make the center appear offline.

The same process exposes a small, versioned session interface
`org.forge.DesktopNotifications1`: `Snapshot()` returns bounded JSON containing
only displayable fields, `Dismiss(id)` and `Invoke(id,key)` handle UI actions,
and `Changed` announces a new snapshot. A restarted shell subscribes, then
loads Snapshot, so it can reconstruct current notices without restarting
applications. A review found that session-bus visibility alone does not
authenticate the shell for these cross-application operations. The amended
[authority design](2026-09-28-notification-auth-design.md) restricts all three
methods to the current shell's actual D-Bus unique sender, established through
two inherited private channels. The service refuses to queue or replace
another notification daemon if that D-Bus name is already owned. The
compositor supervises it independently of the restartable shell; XFCE keeps
its own service in the recovery session.

Acceptance uses a private `dbus-run-session`: verify method signatures,
replacement IDs, bounds, reasons, expiry, action emission, multi-notification
state, cross-sender rejection and shell reconnection. Then install in the
marked DRM guest and verify visible notifications before M3.3 is marked
complete.
