# CompatForge desktop integration

The shared CompatForge daemon is the only runtime owner. This ordinary-user
consumer calls the fixed `/usr/bin/compatforge-cli desktop-export` client; it
does not open Bottle files or start Wine. The private daemon authenticates the
user at both ends. Installation, update, rollback and uninstall converge through
a 15-second user timer even when the application manager UI is closed. Failed
queries preserve the current launcher set.

## Installed assets

| Repository source | Installed path | Mode |
|---|---|---|
| `tools/compatforge_desktop.py` | `/usr/libexec/forge-desktop/compatforge-desktop-sync` | 0755 |
| `services/compatforge/forge-compatforge-desktop-sync.service` | `/usr/lib/systemd/user/forge-compatforge-desktop-sync.service` | 0644 |
| `services/compatforge/forge-compatforge-desktop-sync.timer` | `/usr/lib/systemd/user/forge-compatforge-desktop-sync.timer` | 0644 |

Enable the timer with the user systemd manager in the ForgeOS image integration.
The units are included in the closed Plasma bundle allowlist and MIT inventory.
Runtime packages added here are `python` (stdlib only) and `desktop-file-utils`.
ForgeOS pins exact package builds and verifies its own installation allowlist;
this source change alone does not constitute updated-image acceptance.

Python is the already present Arch system interpreter, not a new pip dependency.
Upstream provenance: https://www.python.org/ (PSF-2.0) and
https://www.freedesktop.org/wiki/Software/desktop-file-utils/ (GPL-2.0-or-later).
`update-desktop-database` updates supported MIME types after changed entries.
The consumer never writes `mimeapps.list` or selects a default application.

## Ownership, recovery and bounds

Entries have stable `org.forgeos.CompatForge.APP.LAUNCHER.desktop` names under
`$XDG_DATA_HOME/applications` (default `~/.local/share/applications`). Exec is
validated against the fixed CompatForge client and standalone `%F`; no metadata
shell commands are allowed. Reviewed theme icon names and WM_CLASS hints come
from CompatForge. The desktop's field expansion passes each selected file as a
separate argv; CompatForge converts it to a Wine Z-drive path.

The versioned manifest and a bounded durable intent are stored under
`$XDG_STATE_HOME/forge-desktop/compatforge` (default `~/.local/state/...`). An
exclusive process lock serializes reconcilers. Before file changes, a transaction
records the old manifest hash, the next manifest and each before/after entry.
Writes use temporary files, fsync and atomic replace. On interruption, recovery
finishes only steps whose bytes match a known before or after state. User edits,
foreign files, links and unexpected content remain untouched. The manifest's
revision distinguishes transactions that restore an absent file without changing
its intended content. Corrupt metadata fails closed and requires diagnosis;
the consumer never guesses ownership or removes application data.

Limits: 256 entries, 16 KiB per entry, 256 KiB manifest, 8 MiB intent, 16 MiB CLI
output, 70-second query deadline and 90-second oneshot unit timeout. Capacity is
checked before writing entries. A failed query never means an empty catalogue.
These bounds can be raised only together with corresponding tests and image
policy; this first integration is not an unbounded marketplace index.

## Verification boundary

Pure consumer tests cover install/update/uninstall, Unicode titles, literal
percent signs, MIME-default preservation, foreign/user-edited entries, directory
links, capacity rejection, interrupted first install and partial multi-entry
transactions. CompatForge tests cover the literal Exec serializer, selected
generation verification, argv preservation, socket ownership, bounded transport,
recoverable errors, automatic job polling and shutdown acknowledgement.

Actual timer activation in Plasma, menu/Dock icons and task grouping, selecting a
Chinese filename through a real file manager, application save and reboot remain
Task 4 VM gates. Existing M3-M5 and stability/performance gates remain unchanged.
