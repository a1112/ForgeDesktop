# ForgeDesktop engineering

ForgeDesktop owns the native compositor, shell and desktop integration. ForgeOS
owns image/policy integration. CompatForge owns Windows runtime orchestration.
Read docs/plans/native-desktop.md and docs/STATUS.md before making changes.

- Follow the approved M0-M5 plan; do not call a prototype a complete desktop.
- Rust + Smithay compositor; separate Qt 6/QML shell; software rendering first.
- Tests precede behavior changes. Keep runtime evidence distinct from unit tests.
- No root compositor, shell command construction from application metadata,
  unauthenticated private control, or unreviewed global input/capture access.
- Keep XFCE and existing user state recoverable until all delivery gates pass.
- New dependencies require pins, upstream source and license rationale.
- Deny unsafe in our Rust crates; if a real FFI boundary needs unsafe, isolate it
  in a reviewed boundary crate with explicit safety contracts and tests.
- Commit with DCO sign-off. Do not include credentials or personal runtime state.
