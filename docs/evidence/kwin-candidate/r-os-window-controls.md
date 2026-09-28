# R-OS-inspired window controls in the isolated KWin candidate

Date: 2026-09-28. Candidate: Arch 2026/08/01, KWin and Plasma 6.7.3-1,
1280×800 software-rendered QEMU/KVM guest, accessed through noVNC on port 6087.
This is the disposable ForgeOS KWin test instance, not the production overlay.

The original ForgeDark Aurorae theme and `org.forge.windowcontrols` applet were
installed in the test guest. `kwinrc` and the user's Plasma applet configuration
were backed up before the experiment. `KWin.supportInformation` reported
`Plugin: org.kde.kwin.aurorae`, `Theme: __aurorae__svg__ForgeDark`, and
`borderlessMaximizedWindows: true`. The applet is in the top panel.

- [Ordinary Thunar and Terminal windows](r-os-normal-window.png): KWin draws
  the dark frame and the right-side minimize, maximize and close controls.
- [Maximized Thunar](r-os-fusion-maximized.png): KWin removes the title frame;
  the top panel shows the live window title and three controls.
- The top-panel restore button returned maximized Thunar to its normal frame.
  The minimize button hid it and the Dock restored it. The close button closed
  Thunar while the Terminal window stayed open.
- Maximizing Terminal changed the Fusion title to Terminal. Opening normal
  Thunar in front hid Fusion even while Terminal remained maximized behind it;
  maximizing Thunar changed Fusion back to Thunar.
- Qt System Settings used the Aurorae frame in normal mode and displayed its
  own title and actions in Fusion when maximized.
- [Firefox client-side decoration fallback](r-os-firefox-fallback.png): its
  maximized tab bar already contains a close control. The measured task AppId
  is `firefox.desktop`; the Fusion widget excludes that AppId, leaving one set
  of controls. An XWayland `xmessage` window retained its KWin frame.
- Restarting `plasma-plasmashell.service` left the application windows open and
  restored the panel controls. A runtime probe confirmed the active task's
  `IsWindow`, `IsActive`, `IsMaximized`, `CanSetNoBorder`, and `HasNoBorder`
  roles were true for maximized Thunar.

The first widget revision displayed no controls because Plasma did not create
its `compactRepresentationItem` in this fixed-width panel applet. A runtime
probe reported `compactRepresentationItem=null` while the root was visible and
the active maximized task was eligible. Rendering the `RowLayout` as a direct
child of `PlasmoidItem` fixed the display; explicit light glyph colors made the
buttons legible against the dark panel. These observations are covered by the
repository test for the panel item shape and by manual button tests above.

The screenshots are native QMP `screendump` PNGs of the guest display, not
browser crops. They show actual 1280×800 output. This acceptance covers the
tested Thunar, XFCE Terminal, Qt System Settings, Firefox, and XWayland
`xmessage` paths. Other client-decorated AppIds need individual verification
before adding them to the exclusion list. Multi-output behavior, timed
performance gates, and a new immutable image boot remain separate validation
gates; no default-session switch is claimed here. XFCE recovery remains the
current login default.
