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
by a panel. XFCE must be remeasured before M0 is complete.

The build host was downloading dependencies at low CPU usage during the valid
sample, with near-zero I/O pressure; no compiler or disk copy was running.
Repeat the final matched comparison with all unrelated work stopped.

An earlier attempt did not run because the VNC input path dropped the `n` in
`python3`. That failed attempt produced no accepted measurement. The command was
corrected and the resulting valid report transferred to a temporary loopback
receiver, which was then stopped. `ros-idle.png` is a visual reference for this
desktop layout, taken before the successful sample.

## Still required

- Exact XFCE process baseline and separately measured R-OS backend.
- Repeatable fresh/warm startup and interaction measurements.
- Frame timing and noVNC end-to-end latency measured independently.
- ForgeDesktop comparison after the actual compositor and shell run.

The R-OS result does not establish ForgeDesktop performance. No M1–M5 runtime,
stability or delivery gate is satisfied by these counters.
