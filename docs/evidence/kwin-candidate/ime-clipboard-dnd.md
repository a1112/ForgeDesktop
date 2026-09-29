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
