# Supervised observer reducer implementation plan

**Goal:** Consume real private Qt companion events into bounded, generation-safe native window metadata while capture and atomic input remain closed.

**Architecture:** A standalone ObserverReducer owns one supervisor-allocated safe, nonzero session epoch. It accepts the companion's strict event schema, binds live children to actual parent generation keys, quarantines unresolved transient observations, and never exposes grant/admit/input. The fixed observer-events CLI consumes inherited private stdin and serially emits bounded metadata pages; the original policy CLI protocol stays unchanged.

**Tech stack:** Existing safe Rust 2024/std, serde 1.0.228 and serde_json 1.0.145. Workspace MSRV 1.85 is compatible with the available Windows Rust 1.89. No additional dependency or native runtime/session change is required.

Approved scope follows AGENTS.md and ADR 0004. The companion checks the current KWin and ScreenSaver unique bus owners. Title/app_id remain hints; this reducer does not prove application/Android identity or implement capture/atomic input. M0–M5 and actual compositor admission gates remain separate. No theme, STATUS or ADR file changes and no commits are part of this increment.

## Task 1: Strict event and lifecycle regression tests

- Create crates/forge-window-bridge/tests/observer.rs and a minimal compileable observer API skeleton.
- Cover genuine companion-shaped window/closed/active/lock/capabilities/disconnected frames, nested/duplicate/unknown fields, version, invalid UTF-8, exactly one newline and the 65,536-byte frame bound.
- Observe/update/close/reuse UUIDs, geometry changes, popup/dialog lineage and subtree retirement. Unknown-parent children remain quarantined until a fresh trusted child event, never automatically revive after parent-name reuse.
- Verify lock/revoke, terminal same-epoch disconnect/invalid-frame behavior, safe integer creation/counter exhaustion, bounded registries and byte-budgeted snapshot pages.
- Run cargo test --locked -p forge-window-bridge --test observer and retain behavioral RED evidence before implementing each group.

## Task 2: Minimal metadata reducer

- Create src/observer.rs; export it from lib.rs without changing existing Bridge policy semantics.
- Deserialize tagged strict event structs with deny_unknown_fields; validate all identity/text/geometry limits before registry changes. Follow the companion's 1..128 ASCII opaque IDs, 4096/1024 UTF-16 caption/app_id limits and existing geometry bounds.
- Bound live/quarantine/retired registries at 4096/4096/65536. Reused closed IDs get strictly increasing generations; geometry counters only advance on changed rectangles. Parent/type changes retire the old subtree before any new binding.
- Lock clears activity and advances revocation metadata. Disconnect, invalid events, limits or safe-counter exhaustion fail closed, clear live/quarantine state and prohibit further same-epoch observation/unlock. New supervisor epochs require a new reducer.
- Paginate at 1..64 entries and reduce page count according to actual serialized JSON size, reserving frame overhead; emit no fabricated empty success when metadata cannot fit.
- Run integration/unit tests and focused clippy after GREEN. Counter exhaustion is injected only in private unit tests, not a production bypass API.

## Task 3: Actual private stdin consumer

- Add only the fixed --observer-events --session-epoch SAFE_INTEGER CLI mode. Keep existing --session-epoch policy mode and command envelope intact.
- Consume bounded newline frames from inherited stdin, apply real reducer transitions, and emit complete bounded metadata pages before the next event. EOF disconnects/revokes; malformed/truncated input emits closed metadata then exits with an error.
- Add process-level CLI tests using the built executable for actual event consumption, generation/subtree behavior, false capabilities and rejected control/browser messages.
- Publish the companion-to-reducer command in docs/bridge-v1.md. No subprocess discovery, shell construction, browser grants or enabled native adapter is added.

## Task 4: Verification and handoff

- cargo test --locked -p forge-window-bridge
- cargo fmt --all -- --check (format only owned files if unrelated snapshots are changing)
- cargo clippy --locked -p forge-window-bridge --all-targets -- -D warnings
- Report Windows host evidence distinctly from the coordinating agent's real Linux companion pipeline. Do not start/stop a VM or claim capture/input/runtime qualification.
- Update only docs/bridge-v1.md and this plan; hand off owned source hashes and exact CLI invocation for independent review. Do not commit until requested by the coordinating agent.
