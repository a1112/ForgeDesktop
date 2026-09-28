# StatusNotifier tray, isolated VM checkpoint

The native session service now owns the KDE and freedesktop watcher bus names.
Only the process owning an item bus name can register it. The private snapshot,
activation and DBusMenu methods require the live shell identity supplied by
the compositor over its inherited channel. D-Bus tests cover forged item
registration, unauthorized read/action, revocation, shell reauthorization and
item removal when its bus connection leaves. A synthetic DBusMenu tests
`AboutToShow`, `GetLayout`, a valid click, and a missing menu object's failure
state. Two hundred item signals in one burst yielded at most three property
reads after the initial refresh. A menu with 65 hidden children is rejected
against the raw child count. Unknown item status is normalized, and the
shell skips an invalid item without discarding valid siblings. The shell parser
and reconnect tests cover bounds and reconstruction. The Arch builder passed
all three notification service tests and all three shell tests; the Rust
workspace passed 29 tests, formatting and Clippy with warnings denied.

The marked, network-isolated `forgedesktop-daily-test` VM was updated with
SHA-256 checked binaries, then normally rebooted. After boot the compositor,
service and shell process digests were respectively:

```
99593a653c65bd35c23ed87018ae122860d05e67c2efbace7643d5da32c975f9
28f7270c4ec4769d143234eff1df50bcd217ed840c4b9e99db3e1db8fb2e55b9
6c4cdc4f53f1bb23fdeb7b820598457c7dd328b8b62187fc2450e9410beffb01
```

Fcitx 5 registered `:1.22/StatusNotifierItem`; its real icon appeared in the
top bar. The context menu displayed from Fcitx's `com.canonical.dbusmenu`
object. Selecting Pinyin changed the icon and checked menu entry; selecting
English restored both. The menu closed and reopened on the next right-click.
After terminating shell PID 692, the compositor started PID 777 while daemon
PID 616 stayed alive, and the same Fcitx item and menu remained available.
[English menu](fcitx-menu.png), [Pinyin selected](fcitx-pinyin-menu.png), and
[menu after shell restart](shell-restart-menu.png) are visual evidence.
After the refined build was installed and normally rebooted, Fcitx's Pinyin
selection changed its icon and checked menu item again. A second shell-only
restart changed shell PID 685 to 803 while compositor PID 590 and notification
daemon PID 609 survived. The tray and menu remained usable. See
[refined menu](refined-live-menu.png) and
[menu after second shell restart](refined-shell-restart.png).
The final service and shell were rebuilt with the hidden-child bound and
menu-only fallback fix, staged in the same marked VM, and normally rebooted.
The final [live menu](final-menu.png) opened successfully; the desktop was left
clean with English input selected.

During development, a Qt D-Bus overload mistake caused one isolated daemon
crash while parsing Fcitx's menu. The standalone [type probe](menu_type_probe.cpp)
showed that a mutable `QDBusArgument::beginStructure()` selected the marshal
overload; a const argument selects the demarshal overload. The parser now
checks the exact nested signatures before reading. The compositor restarted
the daemon after that fault; this is not evidence of a crash-free soak run.

This remains an M3.3 checkpoint. Pixmap-only tray icons, DBusMenu update
signals/shortcuts, per-icon compositor menu placement, remote action failure
feedback, wider application interop, full M3 daily controls and M4/M5
stability/performance gates are pending. The daily user VM and default login
session were not changed.
