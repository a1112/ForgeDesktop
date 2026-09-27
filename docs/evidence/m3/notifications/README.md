# Native notifications, isolated VM

The standalone ordinary-user `forge-notificationd` owns
`org.freedesktop.Notifications` on the user session bus. It was compiled in
the pinned Arch builder with Qt 6, and the Store Qt test plus private
`dbus-run-session` interface smoke test passed. A real call in the marked
isolated VM returned notification ID 1 for a Chinese summary and body. The
Qt/QML shell showed `Notices (1)` and rendered both strings as plain text.
After `forge-shell` was terminated, the compositor restarted it and the same
notification remained in the count and center without relaunching the sender.

The disposable image was then normally booted through its isolated-only
LightDM `forgedesktop` autologin override. The initial `forge-session` started
`forge-notificationd` before the compositor; all three, plus XWayland and the
shell, ran as `forge`, not root. A new real D-Bus `Notify` call returned ID 1,
and [the native center screenshot](notification-center.png) shows the Chinese
summary and body. This second boot confirms the session startup path rather
than relying on the earlier transient user unit.

This is an interim M3.3 slice. Competing-daemon behavior, normal logout and
the other M3 services remain pending. The
isolated autologin override is a test fixture only; it is not a release
default-session or authentication decision. This evidence does not meet the
full M3 gate yet.

Code review then identified a cross-application authority gap in the custom
center D-Bus interface. The revised candidate uses compositor-supervised
notificationd and private shell identity registration. The private-bus test
checks a different sender cannot read, dismiss, replace or invoke, and checks
the standard action/close signals. The revised compositor, shell and daemon
were installed into the same marked image and booted normally. Their SHA-256
values were respectively `5d0ed5db958511b877701f254d97249b588f57ee14385c2cad982bae04efc7fc`,
`5dda786a31cecc882f248671a472459bf65cd1c8222ebc561b5881f07e65c5a2`,
and `8d39b3a39ef1edc5da001ae71bac523aee949103d7989723a17f95d46b09b4b3`.

In that boot an independent `gdbus` client received `AccessDenied` for
`Snapshot`, `Dismiss` and `Invoke`. Standard `Notify` returned ID 1, while the
shell showed `Notices (1)`. Terminating shell PID 686 caused compositor to
start PID 832; daemon PID 609 stayed alive and the notification remained.
Eight action buttons, including two long labels, wrapped within the center
([screenshot](actions-wrapped.png)). Clicking the eighth produced the real
`ActionInvoked (2, 'key7')` D-Bus signal. Clicking its close control produced
`NotificationClosed (2, 2)` and reduced the visible count. These processes all
ran as UID 1000; the daemon's parent was the compositor. The isolated test
fixture remains separate from the daily VM and is not a release default.

The final shell review also found that a full store of heavily escaped text
could exceed the original 2 MiB parser limit. The shell now bounds both UTF-16
length and encoded UTF-8 bytes at 10 MiB, above the producer's worst legal
snapshot. The `acceptsFullStoreWithEscapedBodies` and
`maximumEscapedSnapshotFitsShellBudget` regressions passed. A separate private
bus test makes the first Snapshot return `AccessDenied`, authorizes the shell
without any `Changed` signal, and confirms the old notification appears on the
next timed retry. Both shell CTest cases and both notification service CTest
cases passed in the pinned Arch builder.

The corrected shell binary (`sha256:
2ae42c1c3223ef61972723e6d6925269fdcb4e1fdfc0b5d6c1a261c351ca17bb`)
was copied atomically into the marked isolated guest. After the compositor
restarted the shell (PID 832 to 963), `/proc/963/exe` matched that digest. The
surviving notice still appeared in the center
([latest screenshot](latest-shell-restart.png)); the notification daemon and
guest remained running. Reviewer followup found no remaining blocking issue
in this notification slice.

An isolated fault test then sent `SIGKILL` to notification daemon PID 609.
The compositor (PID 583) stayed alive and started daemon PID 996; shell PID
963 also stayed alive. As specified, notices held only in the crashed daemon
were lost, and the center showed an online, empty state rather than stale
content. A fresh independent D-Bus client still received `AccessDenied` from
`Snapshot`, while standard `Notify` returned ID 1 and the new Chinese notice
appeared in the unchanged shell
([recovery screenshot](daemon-crash-recovery.png)). All three processes remained
UID 1000, with the compositor as the daemon and shell parent. This tests
recovery of the service boundary, not persistence of in-memory notices across
a daemon crash.
