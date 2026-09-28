# Delivery status

Approved scope: complete daily-use native desktop, not merely a nested demo.
The user approved KWin/Plasma as the main window-management route on
2026-09-28. The existing Smithay results below remain experimental evidence.
The isolated KWin candidate booted on 2026-09-28 and passed initial login,
GTK/Qt window, tiling, and shell-restart checks. Its daily-service, stability,
visual-identity, and performance gates are still pending. See
`plans/2026-09-28-kwin-plasma-desktop-design.md`.

| Milestone | Status | Required evidence |
|---|---|---|
| M0 baseline/build environment | In progress | >=30 GiB workspace, fixed R-OS/XFCE metrics |
| M1 Smithay compositor | Passed scoped experimental milestone | Nested/DRM GTK+Qt input, focus/move/resize/wheel, LightDM crash recovery; spec/quality review passed |
| M2 Smithay native shell | Passed scoped experimental milestone | Native Qt shell, real GIO launch, task/workspace policy, nested and DRM shell-crash survival; spec/quality review passed |
| KWin/Plasma candidate | Initial boot/window acceptance passed; full acceptance pending | Pinned isolated image, ordinary-user Wayland session, GTK/Qt windows, maximize/tile/Alt-Tab, shell-crash survival; greeter return and further window paths pending |
| M3 Smithay daily integration | In progress (experimental) | IME, clipboard, notifications/tray, lock, outputs, portals/audio; notification and StatusNotifier tray slices verified in isolated VM |
| KWin M3 daily integration | Pending | IME, clipboard, notifications/tray, lock, outputs, portals/audio in the upstream session |
| M4 apps/stability | Pending | KWin app matrix, persistence, 8-hour soak, 20 session cycles |
| M5 delivery | Pending | KWin performance gates, artifacts/image, default switch/recovery |

Do not switch the user's default session while any required gate is pending.
