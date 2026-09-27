#!/bin/sh
# Xvfb hosts only the compositor. The X11 test application uses its distinct XWayland display.
set -eu
work=/work/m3-xwayland
mkdir -p "$work/runtime" "$work/framebuffer"
chmod 700 "$work/runtime"
export XDG_RUNTIME_DIR="$work/runtime" DISPLAY=:92 LANG=C.UTF-8 LC_ALL=C.UTF-8
cc crates/forge-compositor/tests/selection_probe.c -o "$work/probe" $(pkg-config --cflags --libs gtk+-3.0)
cc crates/forge-compositor/tests/x11_geometry.c -o "$work/geometry" -lX11
Xvfb :92 -screen 0 1280x800x24 -nolisten tcp -fbdir "$work/framebuffer" >"$work/xvfb.log" 2>&1 &
xvfb=$!; compositor=; native=; xclient=
trap 'for p in "$xclient" "$native" "$compositor" "$xvfb"; do test -z "$p" || kill "$p" 2>/dev/null || true; done' EXIT
sleep 1
${COMPOSITOR_BIN:-/target/debug/forge-compositor} --nested >"$work/compositor.log" 2>&1 &
compositor=$!
sleep 2
xdisplay=$(sed -n 's/.*XWayland ready DISPLAY=//p' "$work/compositor.log" | tail -1)
test -n "$xdisplay"
test "$xdisplay" != :92
env DISPLAY="$xdisplay" "$work/geometry"
sleep 0.3
input(){ /target/debug/examples/nested_input --isolated-xvfb "$@"; }
env WAYLAND_DISPLAY=forge-wayland-0 GDK_BACKEND=wayland "$work/probe" Native >"$work/native.log" 2>&1 &
native=$!
sleep 1
input click 400 250
input key 33
sleep 0.4
env DISPLAY="$xdisplay" GDK_BACKEND=x11 "$work/probe" XWayland >"$work/x11.log" 2>&1 &
xclient=$!
sleep 2
input click 400 230
input key 55
sleep 1
cp "$work/framebuffer/Xvfb_screen0" "$work/first-x11.xwd"
grep -Fx 'clipboard:Forge 中文剪贴板 😀' "$work/x11.log"
grep -Fx 'primary:Forge 中文剪贴板 😀' "$work/x11.log"
input key 33
sleep 0.4
input click 150 250
input key 55
sleep 1
grep -Fx 'clipboard:Forge 中文剪贴板 😀' "$work/native.log"
grep -Fx 'primary:Forge 中文剪贴板 😀' "$work/native.log"
cp "$work/framebuffer/Xvfb_screen0" "$work/both-clients.xwd"
old=$(pgrep -P "$compositor" -x Xwayland)
kill -KILL "$old"
sleep 3
kill -0 "$compositor"
kill -0 "$native"
new=$(pgrep -P "$compositor" -x Xwayland)
test "$new" != "$old"
test "$(grep -c 'XWayland ready' "$work/compositor.log")" -ge 2
echo "XWayland restarted: $old -> $new; native PID $native retained"
input click 400 250
input key 33
sleep 0.4
env DISPLAY="$xdisplay" GDK_BACKEND=x11 "$work/probe" XWayland-restarted >"$work/restarted.log" 2>&1 &
xclient=$!
sleep 2
input click 400 230
input key 55
sleep 1
cp "$work/framebuffer/Xvfb_screen0" "$work/restarted.xwd"
grep -Fx 'clipboard:Forge 中文剪贴板 😀' "$work/restarted.log"
grep -Fx 'primary:Forge 中文剪贴板 😀' "$work/restarted.log"
printf 'real XWayland selection both directions, keyboard focus and crash recovery passed\n'
