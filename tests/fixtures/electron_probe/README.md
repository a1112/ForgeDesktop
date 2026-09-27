# Electron application matrix probe

This small MIT-licensed fixture loads only local HTML, keeps Electron's renderer
sandbox on, and creates a real editable window. It is test data, not an app in
the release desktop image. Enter Chinese through the viewer and check both the
visible `textarea` and mirrored `output`; inspect the process' actual Wayland or
X11 connection rather than assuming the chosen Ozone flag proves the path.

After signature-verified installation of Arch snapshot `electron43 43.2.0-1`
into the marked disposable VM, copy this directory there and invoke it as the
ordinary desktop user:

```
electron43 --ozone-platform=wayland /path/to/electron_probe
```

For the separate XWayland case, use `--ozone-platform=x11` only after the native
compositor has launched a real XWayland server. Record the child process/socket,
keyboard input, focus, candidate position, clipboard, screenshot and crash
recovery. Do not count the existing X11-host nested tests as XWayland evidence.
