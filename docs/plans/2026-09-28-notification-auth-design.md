# Notification-center authority in the native session

The accepted M3 plan gives the shell its only compositor-control capability
through an inherited Unix socketpair. The first notification daemon prototype
used a session D-Bus interface for `Snapshot`, `Dismiss` and `Invoke`, but any
session-bus peer could call it. This exposed other applications' notification
contents and could fabricate a user action. The standard notification producer
methods must remain available to application clients.

The compositor will own the independent notification daemon's lifetime and pass
it a second inherited Unix socketpair. After the shell starts, it sends its
actual D-Bus unique connection name through the existing private compositor
channel. The compositor accepts only a syntactically bounded unique name from
its current shell, forwards it to the daemon through the second private
channel, and revokes it when the shell exits. The daemon compares the D-Bus
message sender with that exact name before returning a snapshot or accepting a
center action. A restarted shell registers its new name and obtains the stored
notifications. The compositor does not handle notification bodies. The daemon
restarts under supervision if it fails; notifications stored in a failed daemon
are lost and the shell must display the service as unavailable until recovery.

The private channel uses small versioned lines, a fixed maximum size, and only
`authorize` and `revoke` verbs. Neither channel accepts an executable or
caller-supplied socket path. The shell marks inherited stdin close-on-exec
before launching applications; the daemon does the same. Standard
`org.freedesktop.Notifications` producer calls remain on the session bus. The
separate `org.forge.DesktopNotifications1` methods return AccessDenied unless
the actual D-Bus unique sender is the live shell connection. This limits UI
control without putting a potentially >1 MiB notification snapshot into the
compositor's 65,536-byte state frame.

Acceptance: a different bus connection cannot read, dismiss or invoke; the
active shell can do all three; a shell restart revokes the old unique name and
registers the new one; a notification remains visible across that restart; the
daemon cannot run as root or leave its inherited capability open to launched
applications. Real VM evidence is required in addition to unit tests.
