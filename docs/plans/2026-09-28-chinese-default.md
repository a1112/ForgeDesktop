# Chinese-default bilingual desktop implementation plan

**Goal:** Ship and demonstrate a Chinese-default ForgeOS/ForgeDesktop that can
switch between Simplified Chinese and English through Plasma Region & Language.

**Architecture:** KDE gettext catalogues and translated desktop metadata live in
ForgeDesktop. ForgeOS supplies generated libc locales and user-overridable KDE
defaults, verifies language-pack provenance and builds a new image.

**Tech stack:** Plasma 6, KConfig, ki18n/gettext, Arch locale-gen, Python artifact
validators and tests, QEMU/KVM/noVNC.

## 1. Desktop translations

- Extend `tools/tests/test_build_plasma_bundle.py` with localized-entry positive
  tests and rejection of translated command keys, catalogue content/placeholder
  tests, and the narrowly allowed catalogue path. Run the tests and observe the
  missing behavior before implementation.
- Add `plasma/translations/zh_CN.po` and its MO catalogue under the applet's
  `contents/locale/zh_CN/LC_MESSAGES`. Use standard `i18n` calls and translated
  tooltips in `plasma/plasmoids/org.forge.windowcontrols/contents/ui/main.qml`.
- Update theme/widget/session metadata, `plasma/dependencies.json`, and
  `tools/build_plasma_bundle.py`. Keep executable entry fields fixed.
- Run `python -m unittest discover -s tools/tests -q`; compile the catalogue with
  gettext `msgfmt --check` and verify actual lookup. Commit with DCO.

## 2. System locale and image integration (ForgeOS)

- Add tests for idempotent locale generation inputs, Chinese system/KDE
  defaults, preserving existing generated locales and per-user settings, and
  refusal of unsafe destination links. Add catalogue/entry consumer tests.
- Implement `tools/configure_desktop_locale.py` and invoke it from
  `tools/prepare_kwin_image.py`. Reuse this helper for a stopped test overlay.
- Extend `tools/install_forgedesktop_plasma.py` only for the reviewed translation
  path and display-name keys. Pin the new bundle and matching signed Firefox
  Chinese pack in `supply-chain/kwin-desktop.json`; update lock tests.
- Run focused tests, boundary/source/image validators and required repository
  gates in the appropriate Windows/Linux environment. Commit with DCO.

## 3. Build, exercise, and record

- Produce a versioned bundle and a new immutable image; verify the installed
  catalogue, locales and image receipt. Preserve v6 and its overlay.
- Cleanly stop the existing disposable guest, retain a snapshot, and boot the
  localized candidate. Verify Chinese menus, settings, file manager, terminal,
  Firefox and Fusion tooltip/window controls through the real desktop.
- Use Region & Language to select English, log in again, inspect English UI,
  then return to Chinese and verify persisted preferences. Capture native QMP
  screenshots and record exact build identities and any remaining limitations.
- Leave the Chinese desktop at the 6087 viewer, commit evidence, and push the
  existing ForgeOS branch. ForgeDesktop has no configured remote.
