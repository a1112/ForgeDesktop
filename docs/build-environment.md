# Arch build environment

Runtime artifacts target the same Arch userspace snapshot as ForgeOS:
`2026/08/01`, x86_64. Building against the Ubuntu host's newer or differently
configured libraries is not sufficient runtime compatibility evidence.

Use an isolated root directory on the dedicated build volume. Initialize its
Arch keyring from the digest-pinned base image and populate the upstream Arch
packager keys. `tools/arch-build-packages.conf` requires package signatures and
pins archive URLs to the snapshot. Never disable signature validation to work
around a package failure. Record the final installed package versions, archive
hashes and signatures before publishing a runtime artifact.

Planned build/runtime packages include the Rust compiler, base-devel, CMake,
Ninja, pkgconf, Pixman, libdrm, libinput, libseat, libxkbcommon, Wayland and
protocols, Qt 6 Base/Declarative/Wayland/SVG, and XWayland. Xvfb and GTK demos are
test dependencies. The package closure is not yet frozen; no binary release is
published by this document.

Run build commands as the ordinary build user inside systemd-nspawn, with a
separate source/work directory. The compositor must refuse UID 0, use the
user's private XDG_RUNTIME_DIR, and acquire DRM/input devices through logind or
its libseat adapter in a real session. A successful root/container compile
does not certify session device access or desktop functionality.

Nested Pixman/X11 testing comes first. Dedicated DRM tests use a separate QEMU
instance. Fault injection must never target the user's live daily overlay.
