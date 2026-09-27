#!/bin/sh
# Disposable Arch build container only. Never the user's daily session.
set -eu
work=/work/m2-nested
mkdir -p "$work/runtime" "$work/framebuffer"
chmod 700 "$work/runtime"
export XDG_RUNTIME_DIR="$work/runtime" DISPLAY=:92
export XDG_CURRENT_DESKTOP=ForgeDesktop FORGE_DESKTOP_TRACE=1
Xvfb :92 -screen 0 1280x800x24 -nolisten tcp -fbdir "$work/framebuffer" >"$work/xvfb.log" 2>&1 &
xvfb=$!
compositor= qt= gtk=
trap 'for pid in "$qt" "$gtk" "$compositor" "$xvfb"; do test -z "$pid" || kill "$pid" 2>/dev/null || true; done' EXIT
sleep 1
/target/debug/forge-compositor --nested >"$work/compositor.log" 2>&1 &
compositor=$!
printf '%s\n' "$compositor" >"$work/compositor.pid"
sleep 3
kill -0 "$compositor"
cp "$work/framebuffer/Xvfb_screen0" "$work/desktop.xwd"
env WAYLAND_DISPLAY=forge-wayland-0 QT_QPA_PLATFORM=wayland /work/m1-nested-qt/probe >"$work/qt.log" 2>&1 &
qt=$!
env WAYLAND_DISPLAY=forge-wayland-0 GDK_BACKEND=wayland /work/m1-nested-gtk/probe >"$work/gtk.log" 2>&1 &
gtk=$!
printf '%s\n' "$qt" >"$work/qt.pid"
printf '%s\n' "$gtk" >"$work/gtk.pid"
sleep 2
cp "$work/framebuffer/Xvfb_screen0" "$work/applications.xwd"
# Remain available for bounded, explicit test input from nested_input.
sleep 600
