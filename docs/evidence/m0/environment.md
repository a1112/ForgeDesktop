# Baseline environment — 2026-09-27

## Preserved daily VM

- QEMU/KVM on the existing Ubuntu Hyper-V development host.
- Guest target: x86_64, 2 vCPU, 4 GiB RAM, 1280×800, software rendering.
- Existing base: `forgeos-daily-v2.raw`, SHA-256
  `0dc52c00c0ed5728943e2b6c3fb302432875df56c9436ea1bbac38d6aaf0b247`.
- Existing R-OS native bundle: v7; SHA-256
  `d27bb01c869316ae9257a752186356e85b5555f251af11ccfdb4ea789af24ca1`.
- XFCE remains the recovery/default session. No new desktop installed yet.

## Build storage

The host root had only 382 MiB free. Added a separate dynamic 128 GiB VHDX,
attached at Hyper-V SCSI controller 0, location 2. The original OS disk and DVD
were preserved. Linux identified the new blank disk as
`wwn-0x60022480ba13d322743d7e97a9ed9e3a`; size was verified before formatting.

New ext4 UUID: `9a6a7094-38aa-4b26-bfbc-4400c4da2c1c`.
Build mount: `/srv/forge-desktop-build`; approximately 125 GiB initially free.
The Arch build root is a separate copy of the existing read-only source root.
It does not mount the running daily VM overlay.

L: was identified as a SATA HDD. The destination selected for the new build disk
is D:, on the existing Lexar SSD, with 231.7 GiB free before the copy. Hyper-V
online storage migration failed its directory ACL check. The new disk alone was
cleanly unmounted and hot-detached, then copied to D: with the original retained.
The copy was too slow and was cancelled. Its incomplete destination was briefly
attached by a non-terminating PowerShell error, then immediately detached without
mounting it. No data was read or written through that incomplete filesystem.

A fresh `forge-desktop-build-ssd.vhdx` was instead created directly on D:. Its
blank WWN `6002248051e83175438f5c3cb83cd82c` and size were checked before format.
The active ext4 UUID is now `7e07ca5a-e1c9-43c2-8d92-fef69f00008b`.
Formatting and copying the read-only Arch source completed in about four seconds;
the mounted volume has 123 GiB available after the source copy. This did not
migrate the Ubuntu OS disk or the running ForgeOS guest's data. The unused HDD
disk and incomplete SSD copy are retained outside the active VM.

Initial filesystem setup/copy incurred high host I/O pressure. Performance
samples during this preparation are invalid as desktop comparison evidence.

## Measurements

Pending: R-OS/XFCE process PSS and CPU, startup, frame/interaction timing,
noVNC end-to-end delay. No performance target is claimed as passed.
The sampler records executable names and counters, not process command lines.
