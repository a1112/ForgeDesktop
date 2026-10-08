# Native window lifecycle and Fusion controls implementation plan

**Goal:** Correct native activity lifecycle and prevent stale or retargeted Fusion button actions while retaining the original R-OS layout.

**Architecture:** Continue the user-approved KWin/Plasma architecture and the existing private metadata observer/reducer. Use public KWin events and Plasma task roles, preserve the ordinary-user boundary and all false capture/input/runtime capabilities. This increment repairs already approved window behavior; it does not replace the compositor, session locker or user configuration.

**Tech stack:** Existing safe Rust/serde, Qt Core/DBus companion, Plasma QML, Python tests, Node execution of the packaged KWin script and Qt Quick Test. No dependency, package pin or default session change.

## Context and alternatives

The user asked to continue improving ForgeOS native windows after approving the R-OS original right-side controls. Independent source and process audits reproduced missing startup activity, stale activity on desktop/null focus, and late activity repopulating a locked reducer. The control applet also reads task capabilities without a binding refresh and resolves its target only when a press is released.

Continue through supported KWin/Plasma integration (selected existing architecture); a separate shell would duplicate state/control integration, and a custom compositor would expand this corrective increment into the pending M3-M5 program. Retain the existing 48x32 ordinary / 40x32 Fusion geometry and title-left/minimize-restore-close-right layout.

## Task 1: Focus lifecycle regression and coordinated correction

Owned files: `crates/forge-window-bridge/src/observer.rs`, its observer tests, `services/window-bridge/companion/payload.cpp`, payload tests, `services/window-bridge/kwin-observer/contents/code/main.js`, a new executable script regression under `tools/tests`, and `docs/bridge-v1.md`.

1. Add failing actual-script tests for startup activity after window observations, null/desktop/Dock clear, activity after creation, and transient/app-ID changes. Add Rust state/CLI tests for explicit clear, initial/late locked activity, unlock without resurrection, unknown/reused/closed IDs, and malformed or missing IDs. Add Qt companion null-vs-missing and closed/window null rejection cases.
2. Record expected RED results before changing production. Accept only `active.id` as a required opaque string or explicit null. Preserve strict duplicate/unknown/type/frame rejection and required opaque IDs for close/window. Rename the required nullable deserializer to a neutral name if reused.
3. Publish activity at script startup after attaching existing windows, and on every activation (eligible ID or null). Observe public `transientChanged` and `desktopFileNameChanged` so lineage and hints can update without unrelated geometry/title changes. While locked, the reducer keeps activity absent; an unlock alone does not restore it.
4. Document coordinated installation: the new reducer accepts old string activity; an old consumer rejects explicit null closed, so install script, companion and reducer together. No policy-command or authorization capability change.
5. Run targeted and full bridge tests, fmt and strict Clippy locked/offline. Build/CTest the actual companion in a separate target directory when the existing Qt environment is available. Preserve failure outputs.

## Task 2: Fusion capability refresh and press intent

Owned files: `plasma/plasmoids/org.forge.windowcontrols/contents/ui/main.qml`, new test-only KDE imports and Qt Quick Test cases under `tools/tests`, and a portable test runner if needed. No producer allowlist or runtime asset addition unless required by the implementation.

1. Execute actual production QML under Qt Quick Test with test-only public KDE module boundaries. Keep active index and fused state unchanged, emit capability dataChanged, and assert both enabled directions. Press A, switch active to B, release, and assert no action; verify same-window pointer/keyboard operations, canceled press, invalid/multiple token, row reuse and capability/eligibility loss.
2. Record expected RED. Make minimize/close capability bindings explicitly track the same model serial as restore. Capture one public WinIdList identity on press, re-read current activeTask on click, and compare before dispatch; never keep a QModelIndex across changes or act on a missing/multiple identity. Clear armed state after click/cancel. Token is same-process UI intent only, never broker identity/authorization.
3. Run actual offscreen QML tests with explicitly selected Qt 6 and isolated environment; test stubs do not count as a real Plasma session. Run existing theme/panel/producer tests and build/verify a new create-only native visual bundle.

## Task 3: Integration, review and delivery

1. Review spec compliance and code quality separately. Fix any findings and repeat only affected checks.
2. Update STATUS with exact source/test/bundle scope; retain prior runtime evidence under its original versions. Add an artifact manifest/report for this increment and signed source commit; do not push or merge.
3. Keep ForgeOS/R-OS code, existing image31, daily VM, account state and service configuration unchanged. No new VM, automatic installation, capture, input injection, screen-lock bypass or default-session switch is part of these local corrective tests.

## Remaining runtime gates

Actual new-version KWin focus/lock/gesture and multi-output/hotplug validation, saving-in-progress outer-close observation, per-window capture/input integration and M3-M5 remain separate. Qt Quick/Test and CLI evidence prove code paths; they do not grant real compositor/media/hardware runtime qualification. Revert the signed increment or restore the previous native package to roll back; XFCE recovery remains available.

## Checklist

- [x] Read current architecture/status and reuse clean isolated `agent/ros-desktop` checkout.
- [x] Independently reproduce existing lifecycle/control gaps and retain the approved architecture/layout.
- [x] Task 1 RED/GREEN, companion and bridge verification; separate spec and quality review passed. Actual Qt 6.11.1 Linux Debug CTest passed, not a KWin runtime gate.
- [ ] Task 2 RED/GREEN, actual QML and native bundle verification.
- [ ] Spec review, quality review, signed integration and truthful delivery manifest.

Official API basis: https://develop.kde.org/docs/plasma/kwin/api/ ; https://raw.githubusercontent.com/KDE/plasma-workspace/Plasma/6.5/libtaskmanager/waylandtasksmodel.cpp . The existing pinned target runtime still requires separate validation.
