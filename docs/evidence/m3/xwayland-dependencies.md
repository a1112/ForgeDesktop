# Rust dependencies enabled for Smithay XWayland

Smithay remains pinned to 0.7.0. Enabling its `xwayland` feature requires six
additional crates. Downloaded from crates.io on 2026-09-28; exact versions and
registry SHA256 checksums are recorded in Cargo.lock. Offline locked builds then
passed. Licenses below are read from the downloaded package Cargo.toml files.

| Crate | Version | License | Upstream |
|---|---|---|---|
| encoding_rs | 0.8.42 | (Apache-2.0 OR MIT) AND BSD-3-Clause | https://github.com/hsivonen/encoding_rs |
| core_detect | 1.0.0 | MIT OR Apache-2.0 | https://github.com/thomcc/core_detect |
| multiversion_no_op | 1.0.0 | Apache-2.0 OR MIT | https://github.com/hsivonen/multiversion_no_op |
| rustversion | 1.0.23 | MIT OR Apache-2.0 | https://github.com/dtolnay/rustversion |
| scopeguard | 1.2.0 | MIT OR Apache-2.0 | https://github.com/bluss/scopeguard |
| simdutf8 | 0.1.5 | MIT OR Apache-2.0 | https://github.com/rusticstuff/simdutf8 |

These are transitive requirements of the pinned Smithay implementation, covering
X11 text conversion and scoped cleanup. This checkpoint enables compilation; the
XWayland runtime and protocol acceptance are a following source checkpoint.
