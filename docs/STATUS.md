# Delivery status

Approved scope: complete daily-use native desktop, not merely a nested demo.

| Milestone | Status | Required evidence |
|---|---|---|
| M0 baseline/build environment | In progress | >=30 GiB workspace, fixed R-OS/XFCE metrics |
| M1 compositor | Passed scoped milestone | Nested/DRM GTK+Qt input, focus/move/resize/wheel, LightDM crash recovery; spec/quality review passed |
| M2 native shell | Passed scoped milestone | Native Qt shell, real GIO launch, task/workspace policy, nested and DRM shell-crash survival; spec/quality review passed |
| M3 daily integration | In progress | IME, clipboard, notifications/tray, lock, outputs, portals/audio |
| M4 apps/stability | Pending | App matrix, persistence, 8-hour soak, 20 session cycles |
| M5 delivery | Pending | Performance gates, artifacts/image, default switch/recovery |

Do not switch the user's default session while any required gate is pending.
