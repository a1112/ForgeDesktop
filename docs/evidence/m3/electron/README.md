# Electron 43 native Wayland probe (isolated DRM VM)

Date: 2026-09-28. This is a scoped M4 application matrix observation, not a
claim that Electron, XWayland or the complete daily desktop is accepted.

## Reproducible input

- VM: `forgedesktop-daily-test`, 2 vCPU, 4 GiB, 1280 x 800, software desktop;
  `/etc/forgedesktop-isolated-test` contains `forgedesktop-daily-test`. The
  daily user VM and its overlay were not touched.
- Test app: `tests/fixtures/electron_probe/`, a local HTML page in a sandboxed
  Electron renderer. It makes no network request. `node --check main.js` passes.
- Arch snapshot 2026/08/01 packages: `c-ares 1.34.8-1` and
  `electron43 43.2.0-1`, exact archive URLs, SHA-256 values, signature digests
  and license identifiers in `../electron-packages.json`.
- Both package archives matched the pinned SHA-256 values; `gpgv` accepted each
  detached signature against the guest's Arch keyring (keyring SHA-256
  `45be20e923b6d156203b73daf96c3b0fc0b4e646967ed7942d7bebc80a6151f3`).
  After independent signature verification, a temporary offline pacman config
  with `SigLevel = Never` installed the two frozen local archives. The config
  and package staging directory were removed before boot. The guest then
  reported the exact installed versions via `pacman -Q`.

## Actual DRM observation

The normal user `forge` launched
`electron43 --ozone-platform=wayland /tmp/forge-electron-probe` with
`WAYLAND_DISPLAY=forge-wayland-0`. `ss -xapn` showed Electron PID 755 socket
inode 40709 paired with forge-compositor PID 546 socket inode 37458 on
`/run/user/1000/forge-wayland-0`. This verifies an actual native Wayland
connection instead of inferring it from the Ozone flag. The Electron renderer
process contained `--enable-sandbox`.

The noVNC screen showed the Electron window, its editable field, and live echo.
Ordinary key input worked. Fcitx 5 pinyin candidate appeared at the field's
caret for `nihao`; Space committed `你好`, which appeared in both field and
echo. [Screenshot](electron-wayland-chinese.jpg).

The guest log contained a VA-API initialization warning from virtio video,
while the window continued to render and accept input. This test does not yet
cover clipboard, drag and drop, XWayland, crash recovery, sustained usage or
performance. Those remain separate M3/M4 acceptance gates.
