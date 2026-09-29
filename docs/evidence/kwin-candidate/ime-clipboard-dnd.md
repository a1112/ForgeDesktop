# KWin daily input and transfer check

Date: 2026-09-29. This is a live check of the existing 6094 KWin Wayland
guest, before a new ForgeDesktop bundle or image is installed. The VM has
2 vCPU, 4 GiB RAM, software graphics, and a noVNC viewer. It is a candidate
session, not the default-session or M3 release acceptance.

## Observed behavior

- The guest's System Settings → Keyboard → Virtual Keyboard initially showed
  None. Selecting Fcitx 5 saved
  `[Wayland] InputMethod[$e]=/usr/share/applications/org.fcitx.Fcitx5.desktop`
  in the ordinary user's `~/.config/kwinrc`.
- In the Qt System Settings keyboard test field, typing `nihao` showed a
  positioned Fcitx Pinyin candidate for `你好`, and Space committed it. In GTK
  Mousepad, `nihao` and `shijie` showed candidates at the text cursor and
  committed `你好` and `世界`.
- GTK Mousepad's context-menu Copy of `世界` followed by Qt's Paste produced
  `你好世界` in the Qt field. Copying that entire Qt value and pasting through
  Mousepad's context menu replaced the GTK selection with `你好世界`.
  The viewer's Ctrl+C/Ctrl+V keyboard path did not produce reliable transfers;
  the application menu path isolated the guest clipboard behavior.
- Mousepad saved `~/文档/forge-dnd-check.txt` with `你好世界` (12 UTF-8 bytes).
  Thunar listed the file. With its Mousepad tab closed and a blank document
  active, dragging the file icon from Thunar into Mousepad opened the saved
  file and showed the same text. This exercises real file drag/drop between
  two GTK applications through the KWin Wayland session.

The current QEMU command for this guest does not include the `qemu-vdagent`
clipboard chardev and `com.redhat.spice.0` virtserialport. These observations
therefore do not establish guest↔Windows clipboard transfer. XWayland input,
logout/login persistence, file drag/drop across other toolkits, and the new
bundle's first-user defaults also remain separate checks.

## Source change and recovery

The Forge look-and-feel defaults now declare the same Fcitx KWin virtual
keyboard entry for profiles applying the theme, and the session wrapper sets
`XMODIFIERS=@im=fcitx` for XWayland clients. GTK_IM_MODULE and QT_IM_MODULE
remain unset globally for native Wayland toolkit integration. The bundle
declares Fcitx, Chinese addons and GTK/Qt bridge packages; ForgeOS checks
their presence in the installed image before publishing a derivative.
Existing user `kwinrc` files are not rewritten by this source change. XFCE
remains the recovery session, and the VM's system image and data overlay were
not replaced during this check.

## Isolated v8 image and first boot

The committed ForgeDesktop source `095e97902edc75d6b7513c8fdf9bff81be7137f6`
produced a verified bundle with receipt SHA-256
`11d9375ac82b77c596a15ebc082ddaecbbf2790b0001f5655e04aaff72c2f98e`.
ForgeOS commit `32c79d8` built a new read-only derivative from the preserved
daily source. The [v8 image receipt](kwin-ime-v8-image-receipt.json) records
image SHA-256 `7507e561fd81da3bc6a4eeddd2fa839c35a55eaa8c1e01afa9aa963063379a79`,
161 pinned packages, Chinese locale, and XFCE as the raw image default.

An offline read-only mount confirmed the installed session wrapper, the
look-and-feel `kwinrc` virtual keyboard entry, all five `fcitx5*` package
records, and the XFCE recovery default. A separate qcow2 overlay at
`/srv/forge-apps-fast/lab/kwin-ime-v8-test` selected the ForgeDesktop session
for automatic test login and preselected Fcitx in this **test profile**. The
unchanged raw image was not made the user's default. At first login, KWin Wayland
displayed the [Fcitx Pinyin welcome prompt](ime-v8-first-login.png), which
confirms the service started in a fresh boot. This boot did not repeat the
typing, clipboard, or drag/drop tests above. Those were performed in the
existing 6094 guest.

QMP requested ACPI powerdown; the Plasma shutdown screen appeared, and its
Shutdown control completed a normal QEMU exit with code 0. `qemu-img check`
reported no errors in the isolated overlay. No active user VM or overlay was
stopped or modified. The clean-profile look-and-feel application and
guest-to-Windows clipboard transfer remain to be tested.
