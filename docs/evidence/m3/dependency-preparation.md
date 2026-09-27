# M3 session dependency preparation

Status: dependencies prepared in the disposable daily test image only. No M3
functionality, IME positioning, screen locking or authentication acceptance is
claimed. The production VM and its base/overlay remain unchanged.

## Rationale and provenance

Direct requested packages from the pinned Arch 2026/08/01 x86_64 snapshot:

- Fcitx 5, Chinese addons, GTK/Qt integration and configtool: reuse established
  Chinese input engines, dictionaries and native configuration interfaces.
- swaylock: established PAM-backed client for ext-session-lock-v1.
- wl-clipboard: real Wayland selection clients for clipboard integration tests.

`session-packages.json` records the 25 missing packages installed into this
particular daily-test base, including archive URL, exact version/size/SHA-256,
detached signature digest and Arch license identifiers. It is a delta inventory,
not the entire desktop/image license list. All archives and signatures were
validated by pacman against the existing pinned builder keyring in a private
network namespace. The transaction succeeded; hooks completed, root was synced
and unmounted, and the loop device detached.

The first attempted closure was resolved against the build root, which already
had boost-libs; the guest correctly rejected missing dependencies before any
transaction. Resolution was repeated against the actual stopped guest's package
database using the same snapshot metadata. This produced the 25-package delta,
including boost-libs. No dependency checks or signatures were bypassed.

Arch's Chinese addon dependency chain includes Qt WebEngine. That dependency is
not used to render ForgeDesktop's shell; the shell remains Qt Quick/QML with the
software renderer. Include its notices in the final complete image inventory.
The current test base already had XWayland, PipeWire/WirePlumber and the GTK
portal; protocol/provider integration and real application tests are still next.

The test VM is stopped after this preparation, pending the reviewed M2 binaries.
