# M0 measurements (partial)

Measured on 2026-09-27 in the existing 2-vCPU/4-GiB/1280×800 daily VM.
Raw counters: `ros-idle.json`, sampler from commit `d526418`.

| Scope | Duration | Average PSS | Maximum PSS | Average CPU, one core |
|---|---:|---:|---:|---:|
| R-OS native host + WebKit descendants | 60.0001 s | 884.70 MiB | 884.85 MiB | 1.233% |

The R-OS process set stayed stable and every PSS read succeeded. The sample
covers `r-os-desktop`, `WebKitNetworkProcess`, and `WebKitWebProcess`. It excludes
the separate Python backend, Xorg, XFCE and ordinary applications. The long-lived
R-OS session was maximized with no internal application window open. This is a
warm existing-session baseline, not a fresh-login or cold-start measurement.

The accompanying XFCE group is **invalid for comparison**: recursive process
selection included temporary child processes. Its `stable_process_set` is false.
The sampler now supports exact executable groups to exclude applications started
by a panel. A corrected exact-group measurement is recorded below.

The build host was downloading dependencies at low CPU usage during the valid
sample, with near-zero I/O pressure; no compiler or disk copy was running.
Repeat the final matched comparison with all unrelated work stopped.

An earlier attempt did not run because the VNC input path dropped the `n` in
`python3`. That failed attempt produced no accepted measurement. The command was
corrected and the resulting valid report transferred to a temporary loopback
receiver, which was then stopped. `ros-idle.png` is a visual reference for this
desktop layout, taken before the successful sample.

## Corrected simultaneous idle sample

`xfce-exact-idle.json` was collected after a 10-second settling delay for
60.00015 seconds, with the terminal minimized and the same R-OS desktop visible.
Both groups had stable process identities and complete PSS reads.

| Scope | Average PSS | Maximum PSS | Average CPU, one core |
|---|---:|---:|---:|
| R-OS host + WebKit descendants | 889.25 MiB | 889.56 MiB | 1.167% |
| Exact XFCE core processes | 103.03 MiB | 103.06 MiB | 0.0167% |

XFCE selection is exactly `xfwm4`, `xfce4-panel`, `xfce4-session`, `xfdesktop`,
excluding their descendants (including ordinary applications). Panel plugin
helpers and Xorg are outside this scope; this is not total desktop-session RAM.
The separate R-OS Python backend is also outside the table. Build/test commands
on the Linux host were paused for the measurement window; the other isolated VM
was idle at its greeter. No reboot, disk copy or package install ran in the window.
The temporary report receiver was stopped after retrieving the successful report.

## Still required

- Separately measured R-OS backend and any additional stack-level comparison.
- Repeatable fresh/warm startup and interaction measurements.
- Frame timing and noVNC end-to-end latency measured independently.
- ForgeDesktop comparison after the actual compositor and shell run.

The R-OS result does not establish ForgeDesktop performance. No M1–M5 runtime,
stability or delivery gate is satisfied by these counters.
