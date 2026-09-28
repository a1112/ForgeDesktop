# KWin/Plasma ForgeDesktop Candidate Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Boot a reproducible, selectable ForgeDesktop KWin/Plasma Wayland session in an isolated ForgeOS VM while retaining Smithay and XFCE recovery, then measure its window behavior and resource use.

**Architecture:** ForgeDesktop provides a small verified session/visual package using documented Plasma and KWin extension points. ForgeOS installs an exact signed Arch package closure into a new derivative image and verifies the ForgeDesktop package before installing it. The candidate never changes the current daily VM overlay or login default.

**Tech Stack:** Arch Linux 2026/08/01 snapshot, KWin/Plasma 6, Qt/QML, LightDM, Python 3 standard library, QEMU/KVM, existing ForgeOS offline package verification.

---

The approved architecture is in `docs/plans/2026-09-28-kwin-plasma-desktop-design.md`. Apply @superpowers:test-driven-development for behavior changes and @superpowers:verification-before-completion before each commit or acceptance claim. The ForgeDesktop worktree is `L:/project/FOS/ForgeDesktop/.worktrees/kwin-plasma`; the ForgeOS worktree is `L:/project/FOS/ForgeOS/.worktrees/kwin-image`. File paths below are relative to the named repository. Commands run from the indicated repository root on Windows for source tests and from the isolated Linux builder for image/guest tests.

### Task 1: Record the new product architecture

**Files:**
- Modify: `AGENTS.md`
- Modify: `docs/STATUS.md`
- Modify: `docs/plans/native-desktop.md`
- Create (ForgeOS): `docs/adr/0014-kwin-plasma-candidate.md`

**Steps:**
1. Mark the Smithay plan and evidence as retained experimental work; set KWin/Plasma as the approved main route and keep all M3-M5 gates pending.
2. Record the separate-image, unprivileged-session, package-lock and rollback contract in ForgeOS ADR-0014; keep XFCE default in the physical and daily images.
3. Run `git diff --check` in each repository, read the staged diff, and commit with DCO sign-off. No runtime-success claim follows from this documentation change.

### Task 2: Build a bounded ForgeDesktop Plasma artifact

**Files:**
- Create: `plasma/session/forge-kwin-session`
- Create: `plasma/session/forgedesktop-kwin.desktop`
- Create: `plasma/README.md`
- Create: `tools/build_plasma_bundle.py`
- Create: `tools/tests/test_build_plasma_bundle.py`

**Steps:**
1. Write tests that reject an executable outside the two fixed session paths, absolute/traversing/link payload members, duplicate names, missing licenses, altered data and a wrapper that invokes arbitrary shell text. Verify the tests fail because the producer is absent.
2. Implement a deterministic, size-bounded manifest with file SHA-256, source commit, Arch snapshot and explicit package/asset license records. Accept only a fixed allowlist under `usr/libexec/forge-desktop/`, `usr/share/wayland-sessions/`, `usr/share/plasma/` and `usr/share/licenses/forge-desktop/`.
3. Make the non-root wrapper exec the pinned upstream `startplasma-wayland` entry and set only the session environment supported by the tested package version. Do not force software-rendering variables from the Smithay wrapper into the KWin session.
4. Run `python -m unittest tools.tests.test_build_plasma_bundle -v` and `python -m unittest discover -s tools/tests -p 'test_*.py'`; commit with DCO.

### Task 3: Pin and install the upstream Plasma closure in ForgeOS

**Files:**
- Create (ForgeOS): `supply-chain/kwin-desktop.json`
- Create (ForgeOS): `tools/prepare_kwin_image.py`
- Create (ForgeOS): `tools/install_forgedesktop_plasma.py`
- Create (ForgeOS): `tests/test_kwin_image.py`
- Create (ForgeOS): `tests/test_forgedesktop_plasma.py`

**Steps:**
1. Inspect the pinned 2026/08/01 Arch sync database on the Linux builder, resolve exact KWin/Plasma, portal, lock and session package dependencies, and record versions, sizes, URL, archive SHA-256, detached signature SHA-256 and licenses. Refuse an unresolvable or unsigned closure.
2. Write failing tests for incorrect base digest, package/signature changes, missing files, path traversal, output aliases, an already-existing output, a requested default-session change and a malformed artifact. Verify each fails for the intended reason.
3. Implement the derivative builder by copying the already accepted daily raw image to a new path. Use the existing daily builder's frozen-package, signature-check and offline pacman pattern; do not create or replace the `forge` user. Install the verified ForgeDesktop artifact and add the selectable session entry only.
4. Run `python -m unittest discover -s tests -p 'test_*.py'` and the ForgeOS boundary/schema/source-lock checks. Commit ForgeOS changes with DCO.

### Task 4: Prove the login session in a disposable VM

**Files:**
- Create: `tests/fixtures/kwin-guest-acceptance.py`
- Create: `docs/evidence/kwin-candidate/README.md`
- Modify: `docs/STATUS.md`

**Steps:**
1. Build a new read-only derivative on the Linux builder; record exact input/output digests. Boot it with its own qcow2 overlay and UEFI state, 2 vCPU, 4 GiB, 1280x800 and the same software-rendered QEMU device as the current daily VM.
2. Select `ForgeDesktop (KWin)` in LightDM and verify the ordinary `forge` user, KWin Wayland socket, Plasma shell, D-Bus and logind session. If LightDM cannot start the upstream session, diagnose this before considering a login-manager change.
3. Test focus, drag/resize, maximize, tile/snap, Alt-Tab, overview, workspace switching, Thunar, Mousepad, Firefox and a Qt client. Capture QMP output and a noVNC screenshot separately; record observed failures without equating viewer corruption with compositor corruption.
4. Exit/restart the shell and confirm app windows survive; exit KWin and confirm return to the greeter. Record commands, logs and screenshots. Keep XFCE selectable and unchanged.

### Task 5: Apply Forge visual identity through stable APIs

**Files:**
- Create: `plasma/look-and-feel/`
- Create: `plasma/layout/`
- Create: `plasma/kwin/`
- Modify: `tools/build_plasma_bundle.py`
- Modify: `tools/tests/test_build_plasma_bundle.py`
- Modify: `docs/design/visual-provenance.md`

**Steps:**
1. Add tests for asset provenance, fixed install paths and lack of private `WindowHeap` imports. Verify red before implementing the package additions.
2. Create a dark color scheme, top panel, bottom Dock, launch/search surface and window switcher using supported Plasma theme/widget/KWin extension paths. Start with upstream widgets wherever they meet the design.
3. Boot and inspect real 1280x800 screenshots; fix scaling, hit targets and readability. Disable costly blur/continuous animations for the VM profile. Commit after tests and visual review.

### Task 6: Daily-service, security and performance gates

**Files:**
- Create: `docs/evidence/kwin-candidate/app-matrix.md`
- Create: `docs/evidence/kwin-candidate/performance.md`
- Create: `docs/evidence/kwin-candidate/faults.md`
- Modify: `docs/STATUS.md`

**Steps:**
1. Run GTK, Qt, Electron, Flatpak, XWayland and CompatForge samples; test Fcitx 5, clipboard, drag/drop, notifications/tray, audio, file portal, ScreenCast consent/revoke and lock behavior.
2. Test two outputs, 100/150/200% scaling, output removal, shell/KWin/portal crashes and persistence after normal reboot. Perform the eight-hour mix and 20 session cycles before claiming stability.
3. Sample compositor+shell PSS, 60-second idle CPU, compositor frame P95, warm launcher P95 and noVNC end-to-end latency separately. Repeat matching R-OS/Smithay operations. Keep the published gates visible; ask for a gate revision only with a measured comparison.
4. Run ForgeDesktop protocol/artifact checks and all required ForgeOS checks. Report pass/fail for every gate, preserve XFCE and Smithay choices, and leave the default unchanged until M5 acceptance and a backed-up installation.

## Completion boundary

Tasks 1-4 produce a reviewable KWin session candidate. Tasks 5-6 are required before the product can claim the requested mature daily window experience. A successful candidate boot alone does not satisfy M3-M5 or authorize the default-session switch.
