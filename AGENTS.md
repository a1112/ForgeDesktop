# ForgeDesktop engineering

ForgeDesktop owns the product desktop shell, window behavior extensions and
desktop integration. ForgeOS owns image/policy integration. CompatForge owns
Windows runtime orchestration. Read
docs/plans/2026-09-28-kwin-plasma-desktop-design.md and docs/STATUS.md before
making changes.

- KWin Wayland + Plasma is the approved main route; use documented upstream
  extension points. Keep the Rust/Smithay + Qt shell as an experimental session.
- Preserve the M0-M5 acceptance gates; do not call a prototype a complete desktop.
- Measure software-rendered VM behavior before any performance claim. Do not
  silently revise the existing performance targets.
- Tests precede behavior changes. Keep runtime evidence distinct from unit tests.
- No root desktop session, shell command construction from application metadata,
  unauthenticated private control, or unreviewed global input/capture access.
- Keep XFCE and existing user state recoverable until all delivery gates pass.
- New dependencies require pins, upstream source and license rationale.
- Deny unsafe in our Rust crates; if a real FFI boundary needs unsafe, isolate it
  in a reviewed boundary crate with explicit safety contracts and tests.
- Commit with DCO sign-off. Do not include credentials or personal runtime state.
