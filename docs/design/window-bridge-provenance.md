# Window bridge dependencies and validation provenance

Rust additions: serde 1.0.228 and serde_json 1.0.145, exact manifest versions and
Cargo.lock registry checksums. Both MIT OR Apache-2.0; official sources
https://github.com/serde-rs/serde and https://github.com/serde-rs/json . Rationale:
typed, bounded JSON IPC with unknown-field rejection rather than hand-written
parsing. Transitive additions are locked in Cargo.lock. No new unsafe Rust.

C++ companion: existing system Qt Core/DBus, minimum 6.8, dynamically linked;
Qt licensing/provenance must be supplied by the consuming OS package inventory.
No additional Qt/KWin package has been installed. Project code is MIT, upstream
KWin source was consulted rather than copied. Any future internal KWin adapter
must review KWin licensing and lock its exact ABI before shipment.

Validation environment 2026-09-29: Windows Rust 1.89, local WSL R-IME-Build
GNU C++ 14.2 and Qt 6.8.2. CMake/CTest built only an observer and payload test in
an isolated temporary directory. There is no KWin development/runtime session
qualification in this environment. No user VM, default theme/session, or global
capture/input permissions were changed.

Visual values in r-os-tokens-v1.json are measurements of the existing local
R-OS TSX utility classes. They are a shared design reference, not a claim of
deployed Plasma visual parity. Existing R-OS-inspired native Aurorae/Fusion
remains unchanged; authenticated custom lock theme awaits a real locker test.
