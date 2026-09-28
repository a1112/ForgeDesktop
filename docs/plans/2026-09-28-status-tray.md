# M3.3 StatusNotifier tray behavior

This is the next slice of the approved daily integration plan. The existing
`forge-notificationd` owns the watcher for the native session, so registered
items remain listed while `forge-shell` restarts. The shell owns the panel
surface and never receives an unrestricted session-bus command facility.

The service implements the KDE StatusNotifierWatcher name used by current
Linux applications and the freedesktop watcher name. A registration is accepted
only from the bus owner of the submitted name or from a client submitting its
own object path. Registrations are bounded, removed when the bus owner leaves,
and served to the live shell through a private view guarded by the compositor's
existing inherited authorization channel. The view contains bounded plain-text
titles, status and themed icon names. Clicking an item sends only its standard
Activate or ContextMenu method; arbitrary method names are not accepted.

The integration check uses a real D-Bus item to prove registration, sender
validation, shell authorization/revocation, item activation and removal. The
test also covers a synthetic DBusMenu layout and clicked event, a missing menu
provider, a signal burst, and isolation of an invalid item status. Item
properties are refreshed at most once at a time per item and coalesced on a
short timer. Unknown statuses are treated as Active by the service; the shell
filters an invalid item if it receives one. A failed menu load reports
"Menu unavailable" rather than leaving a loading indicator forever. Menu-only
items open on left click.

The isolated guest uses Fcitx 5 to verify actual status/icon changes, DBusMenu
selection and shell restart. The first menu implementation reads a bounded
level on demand, supports submenu navigation, separators, disabled and checked
items, and sends only validated `clicked` events. It does not yet support
pixmap-only item icons or the complete DBusMenu update/shortcut protocol; the
panel keeps a labelled fallback for missing themed icons.

The menu is an xdg toplevel with a compositor-owned role and bounded top-right
geometry. A Qt Popup trial exposed an unreleased popup input grab on immediate
reopen, so it is excluded from this slice until that compositor path is fixed.
