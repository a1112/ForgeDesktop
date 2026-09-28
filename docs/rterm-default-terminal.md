# R-Term terminal integration

Create a clean source export with `git -c core.autocrlf=false archive HEAD`.
`tools/stage_plasma_bundle.py` normalizes the closed set of text assets to LF,
so staging on Windows and Linux produces identical payload bytes and modes.

Plasma bundle 0.5.0 contains the terminal launcher, desktop entry and new-user
defaults. ForgeOS separately verifies and installs the native R-Term binary.
The launcher selects CPU rendering and explicitly selects Wayland when
`WAYLAND_DISPLAY` is set, otherwise X11 when `DISPLAY` is set. It executes an
argument array without shell interpolation. R-Term uses `org.forge.RTerm` as
its Wayland app ID, matching `org.forge.RTerm.desktop`.
The launcher forwards its inherited working directory as `--cwd`, preserving
file-manager and `Terminal=true` application directories. An explicit `--cwd`
argument overrides that inherited value.

Accounts created after bundle installation receive terminal settings and
`[KDE] LookAndFeelPackage=org.forge.desktop` through `/etc/skel/.config/kdeglobals`.
Their first Plasma login selects the packaged Forge look-and-feel and its
initial top panel and Dock, including R-Term. No prebuilt applet layout or
login-time layout reset is installed. The login manager's default session
remains unchanged; the user selects the ForgeDesktop KWin session.

An account already present in the base image, including `/home/forge`, does
not receive later `/etc/skel` changes. A fresh image boot is therefore not by
itself a new-account test. Existing accounts keep their theme and panel layout;
terminal migration does not apply a theme, including when the account has
never used Plasma. Migrate an existing account once, with the desktop stopped:

```sh
/usr/libexec/forge-desktop/terminal-defaults apply --home /home/forge
```

For offline image installation, pass the mounted guest home instead. The
migration only edits terminal keys, the terminal shortcut and the exact old
XFCE terminal Dock launcher. It retains unrelated configuration. A durable
receipt in `.local/state/forge-desktop/rterm-defaults-v1.json` holds before and
after bytes. Repeated application does not overwrite user changes. There is
no login-time migration service.

To restore, stop the desktop and run:

```sh
/usr/libexec/forge-desktop/terminal-defaults restore --home /home/forge
```

Restore first checks every affected file. Unchanged files return to their exact
original bytes. When Plasma or the user has updated other settings, restore
compares only the terminal keys actually changed by the migration against the
receipt's before/after values. It retains added colors, unrelated shortcuts,
comments and personal settings. A uniquely identifiable migrated Dock launcher
returns to XFCE terminal while retaining other launcher additions and order.
Existing R-Term preferences that migration did not change are left alone.

If a changed terminal key, shortcut or corresponding Dock item no longer matches
the recorded migration, or a duplicate entry makes its identity ambiguous,
restore refuses the whole operation before writing any settings. Keep those
later choices and recover the desired terminal entries manually from the
receipt. The original before/after file backups remain available for disaster
recovery; do not copy a whole backup over newer personal settings without
reviewing those changes. Interrupted restores can be retried, and restoring an
already restored receipt is idempotent. The old `xfce4-terminal` entry remains
installed throughout.

Changing defaults is a deployment gate, not a consequence of passing unit
tests. Native KWin Wayland clipboard, Fcitx input, PTY, scaling and persistence
must pass in an isolated guest before the existing desktop is migrated.

First-login validation must create a new ordinary account from the installed
skeleton, then enter the KWin session without manually applying a theme. Check
that `LookAndFeelPackage` and `~/.config/kdedefaults/package` select
`org.forge.desktop`, the Forge top panel and Dock appear, and the R-Term Dock
entry opens a native Wayland window. Change a panel preference and log in
again to verify that it survives. Separately verify that an existing profile's
theme and layout survive terminal migration, except for the terminal launcher
replacement described above.

Plasma's pinned upstream startup path applies the selected global theme in
[Defaults mode](https://github.com/KDE/plasma-workspace/blob/v6.7.3/startkde/startplasma.cpp),
and its [shell layout loader](https://github.com/KDE/plasma-workspace/blob/v6.7.3/shell/shellcorona.cpp)
uses the selected package's layout only when no saved containments are loaded.
