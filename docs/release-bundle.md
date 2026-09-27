# ForgeDesktop bundle producer

ForgeDesktop builds the native binaries. ForgeOS consumes a versioned external
directory only after checking its `bundle.json` against a separately committed
SHA-256 pin. The producer is `tools/build_bundle.py`; it does not modify an image
or a login session.

Stage the audited release files under these exact relative paths:

```
usr/bin/forge-compositor
usr/libexec/forge-desktop/forge-shell
usr/libexec/forge-desktop/forge-notificationd
usr/libexec/forge-desktop/forge-session
usr/share/wayland-sessions/forgedesktop.desktop
usr/share/forge-desktop/dependencies.json
usr/share/licenses/forge-desktop/LICENSE
```

The session script and three ELF binaries have mode `0755`; the login entry
and data files have mode `0644`. The login entry is constrained to the fixed
`forge-session` and `forge-compositor` paths and only makes ForgeDesktop
selectable in the login manager; it does not change the default session.
Additional non-executable data may be staged only under
`usr/share/forge-desktop/`, and license notices only under
`usr/share/licenses/forge-desktop/`; links and all other paths are rejected. Copy this repository's
`LICENSE-MIT` to the required `LICENSE` path. `dependencies.json` must be a JSON
object with `schemaVersion: 1` and `archSnapshot: "2026/08/01"`. For release,
populate it with the exact signed Arch package closure, Rust crates, Qt runtime,
source URLs, hashes and license references. The producer validates the schema
identifier and snapshot but **does not certify inventory completeness**; that
audit and runtime testing are separate M5 gates.

After committing and verifying the source, run on Linux:

```
python3 tools/build_bundle.py --staging /absolute/staged-tree \
  --output /absolute/new-bundle --version 0.1.0
```

The command refuses a dirty source repository or an existing output directory.
It prints the SHA-256 of the deterministic `bundle.json` receipt. Compare the
receipt's `sourceCommit` to the tested checkout; use the printed digest only
after the ForgeOS consumer, complete image and desktop acceptance pass. A valid
local bundle is not itself permission to switch the default session. Preserve
the XFCE and R-OS recovery paths until the M5 rollout gate is satisfied.
