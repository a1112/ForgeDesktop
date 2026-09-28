# R-Term terminal integration

Plasma bundle 0.5.0 contains the terminal launcher, desktop entry and new-user
defaults. ForgeOS separately verifies and installs the native R-Term binary.
The launcher selects CPU rendering and explicitly selects Wayland when
`WAYLAND_DISPLAY` is set, otherwise X11 when `DISPLAY` is set. It executes an
argument array without shell interpolation. R-Term uses `org.forge.RTerm` as
its Wayland app ID, matching `org.forge.RTerm.desktop`.

New users receive terminal settings through `/etc/skel`; the Forge Plasma
look-and-feel supplies the menu/Dock entry. Existing users are migrated once,
with the desktop stopped:

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

Restore first checks every affected file. If a user subsequently edited one,
it refuses to overwrite anything; retain that edit and recover the relevant
terminal keys from the receipt manually. The old `xfce4-terminal` entry
remains installed. Restoring an already restored receipt is idempotent.

Changing defaults is a deployment gate, not a consequence of passing unit
tests. Native KWin Wayland clipboard, Fcitx input, PTY, scaling and persistence
must pass in an isolated guest before the existing desktop is migrated.
