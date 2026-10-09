# Versioned CompatForge launcher preflight

The fixed Desktop client queries `provider-info` before `desktop-export`.
`tools/compatforge-provider-lock-v1.json` pins a clean exact provider commit,
version, Linux target, user service, commands, schemas and operations. The
bounded Python adapter rejects missing commands, wrong schema/version, stale or
dirty source, malformed/duplicate JSON, oversized output and timed-out probes.
No launcher/state directory or reconciliation intent is created on rejection.

The adapter is identical to CompatForge's standard-library v1 adapter and shares
the Rust negotiator's negative vectors and R-SDK interop error-family mapping.
The independent Forge protocol and native ABIs stay unchanged. No R-SDK source
is modified. The bundle includes the adapter and lock as two 0644 files beside
the existing 0755 sync script, with explicit license records. Omitting either
file or weakening the required protocol set rejects bundle production.

ForgeOS's separately reviewed candidate allows this closed asset pair and
validates the lock before accepting a bundle. Its existing receipt version is
retained because no receipt fields change; legacy bundles without the pair keep
their prior schema. The new exact combination requires the new producer and
consumer source pins and both contract assets.

Rollback selects the previous complete source/artifact combination and retains
existing user-owned launcher files. This local slice has only synthetic contract
and temporary bundle verification. It does not certify Wine, a running Linux
service, image/VM startup, desktop performance or the unresolved R-OS Rust
producer. Existing M0–M5 gates and session-default policy remain unchanged.

Independent review supersedes the CLI-only v1 gate with contract 2.0.0. The
actual `desktop-export` execution receives the fixed lock and a fresh correlation
ID as argv, validates its own compiled identity and negotiates the actual daemon
on one connection before its operation. The consumer validates executor and
daemon identity/capabilities/schema plus correlation in the bound v2 result.
Unbound legacy output and a path replacement's different source cannot trigger
launcher removal. Inner desktop metadata remains schema 1; CLI/transport major
is 2. Shared raw-byte vectors define UTF-8 without BOM identically in Rust and
Python. Lock reads use no-follow, nonblocking, validated descriptors and hard
read limits. No credential or authorization scope is introduced.
