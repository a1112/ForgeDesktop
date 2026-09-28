# R-OS Window Controls Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Give ForgeDesktop R-OS-style ordinary window controls and maximized-window Fusion controls while retaining KWin's native window behavior.

**Architecture:** Package an original Aurorae decoration and a small Plasma 6 top-panel widget. The decoration handles server-side frames. The widget consumes Plasma's `TasksModel` and sends requests only to its current active task; KWin handles actual window actions. Bundle validators and ForgeOS pins prevent unreviewed files from entering the image.

**Tech Stack:** KWin/Plasma 6.7.3, Aurorae SVG, Plasma QML, Python bundle validator/tests, Arch Linux QEMU/KVM.

---

### Task 1: Closed bundle contract

**Files:** `tools/tests/test_build_plasma_bundle.py`, `tools/build_plasma_bundle.py`, `plasma/dependencies.json`.

1. Write failing tests that stage a complete window decoration and widget, then assert bundle inclusion and rejection of missing SVG buttons, external references, malformed widget metadata and off-scope paths.
2. Run `python -m unittest tools.tests.test_build_plasma_bundle -v`; verify expected failures are missing feature handling.
3. Extend `eligible_path`, required asset groups and content validators. Require a license record for every added file. Keep the session entry and script byte-exact.
4. Run the focused tests and full `python -m unittest discover -s tools/tests -v`; commit with DCO.

### Task 2: Ordinary KWin window decoration

**Files:** `plasma/aurorae/ForgeDark/{metadata.desktop,ForgeDarkrc,decoration.svg,minimize.svg,maximize.svg,restore.svg,close.svg}`, `plasma/look-and-feel/contents/defaults`, `plasma/dependencies.json`, relevant bundle tests.

1. Write a failing repository-assets test that requires the 32px title and right-side IAX controls, scalable SVG states and safe local-only XML.
2. Create original SVG assets and configure Aurorae's active/inactive/hover/pressed states; use a flat dark title surface and a red close hover. Set theme defaults through the documented KWin decoration group, preserving the theme as an optional selection.
3. Run the focused and full tests; inspect the actual decoration plugin and settings in the pinned guest. If the engine is absent, add and pin the required signed package in ForgeOS rather than silently falling back.
4. Commit with DCO.

### Task 3: Fusion top-panel widget

**Files:** `plasma/plasmoids/org.forge.windowcontrols/{metadata.json,contents/ui/main.qml}`, `plasma/look-and-feel/contents/layouts/org.kde.plasma.desktop-layout.js`, `plasma/look-and-feel/contents/defaults`, bundle tests.

1. Write failing tests for widget metadata, top-panel placement, active-task-only gating, full-maximize/non-fullscreen eligibility, enabled actions and absence of external command/DBus execution.
2. Implement the QML widget with `org.kde.taskmanager` `TasksModel`, its `activeTask`, task roles and `requestToggleMinimized`, `requestToggleMaximized`, `requestClose`. Re-evaluate state on click. Use labeled 40x32 controls, no timed polling or animation.
3. Set borderless maximized windows only within the Forge theme/session defaults after verifying the exact pinned KWin setting. Do not alter other sessions or existing users.
4. Run tests, `qmllint`/`qmlformat` where available in the guest, then commit with DCO.

### Task 4: Disposable VM integration

**Files:** `docs/evidence/kwin-candidate/r-os-window-controls.md`, screenshots; ForgeOS isolated image receipt/pin if promotion succeeds.

1. Stage the complete bundle, build and verify its receipt; install into a disposable overlay after capturing rollback state. Reuse one 4 GiB VM at a time on the 7.7 GiB builder.
2. Test Thunar, XFCE Terminal, Qt, Firefox and XWayland ordinary controls, maximize/Fusion, restore, minimize, close, task switch, KWin tile/menu, shell restart and client-drawn-header fallback. Reject a Fusion implementation that duplicates controls or controls stale tasks.
3. Capture guest and noVNC screenshots, logs and before/after 60-second PSS/CPU. Record any unmet function or performance gate honestly.
4. On successful acceptance, pin the exact ForgeDesktop bundle in ForgeOS's image workflow, verify the new image and preserve XFCE recovery. Do not switch default session until M3-M5 pass.
