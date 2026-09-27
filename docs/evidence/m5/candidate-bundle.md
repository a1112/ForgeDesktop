# Native bundle candidate, not a release

The bundle producer now includes the compositor, shell, notification daemon,
ordinary-user session script and login chooser entry. The producer's 8 Linux
tests passed, including rejection of an altered login command. ForgeOS's
matching consumer tests and full repository gates passed separately.

A real seven-file candidate was staged from the pinned Arch builder outputs at
ForgeDesktop source commit `145c5e8fe78615720b9b651c9eef39a5652fc818`.
`tools/build_bundle.py` produced receipt SHA-256
`a4bbdaa4627a00bbd8ab14f8d73c9238bd7a1f9777cc3a72736ed87026552a55`.
ForgeOS's updated consumer validated that exact receipt and installed the
frozen bytes into a disposable offline directory. All seven installed payload
hashes matched and the fixture's LightDM default remained `xfce`.

The candidate inventory explicitly says `releaseAudit: pending`. Its digest is
**not** a committed trusted release pin. No full image was composed, no running
daily VM was modified, and no default session changed. The complete dependency
and license audit, desktop acceptance, image boot and recovery gates remain
necessary before M5 delivery.
