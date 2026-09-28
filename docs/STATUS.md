# Delivery status

Approved scope: complete daily-use native desktop, not merely a nested demo.
The user approved KWin/Plasma as the main window-management route on
2026-09-28. The existing Smithay results below remain experimental evidence.
The isolated KWin candidate booted on 2026-09-28 and passed initial login,
GTK/Qt window, tiling, and shell-restart checks. A second verified build now
includes the Forge dark theme, centered Dock, and pinned installed applications;
the final-image VM displayed it and opened/tiled Thunar and XFCE Terminal.
Daily-service, stability, and performance gates remain pending. See
`plans/2026-09-28-kwin-plasma-desktop-design.md` and
`evidence/kwin-candidate/visual-acceptance.md`.
An initial no-app 60-second measurement exceeded the 400 MiB PSS target;
Qt Quick software rendering improved the disposable overlay measurement but
also remained over target. The fourth pinned image started a fresh software
Qt Quick session: exact KWin plus Plasma Shell counters averaged 332.40 MiB
PSS and 0.067% of one CPU core for 60 seconds, meeting those two VM targets.
See `evidence/kwin-candidate/software-backend-acceptance.md`. Frame/launcher
latency, M3 services, long-term stability and default-switch gates remain open.

| Milestone | Status | Required evidence |
|---|---|---|
| M0 baseline/build environment | In progress | >=30 GiB workspace, fixed R-OS/XFCE metrics |
| M1 Smithay compositor | Passed scoped experimental milestone | Nested/DRM GTK+Qt input, focus/move/resize/wheel, LightDM crash recovery; spec/quality review passed |
| M2 Smithay native shell | Passed scoped experimental milestone | Native Qt shell, real GIO launch, task/workspace policy, nested and DRM shell-crash survival; spec/quality review passed |
| KWin/Plasma candidate | Initial boot/window and Forge visual acceptance passed; full acceptance pending | Pinned isolated image, ordinary-user Wayland session, GTK/Qt windows, maximize/tile/Alt-Tab, shell-crash survival, centered Dock and real launchers; greeter return and further window paths pending |
| M3 Smithay daily integration | In progress (experimental) | IME, clipboard, notifications/tray, lock, outputs, portals/audio; notification and StatusNotifier tray slices verified in isolated VM |
| KWin M3 daily integration | Pending | IME, clipboard, notifications/tray, lock, outputs, portals/audio in the upstream session |
| M4 apps/stability | Pending | KWin app matrix, persistence, 8-hour soak, 20 session cycles |
| M5 delivery | Pending | KWin performance gates, artifacts/image, default switch/recovery |

Do not switch the user's default session while any required gate is pending.
