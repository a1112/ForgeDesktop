#!/bin/sh
set -eu
work=/work/m3-scale
mkdir -p "$work/runtime" "$work/framebuffer"
chmod 700 "$work/runtime"
export XDG_RUNTIME_DIR="$work/runtime" DISPLAY=:92 LANG=C.UTF-8
Xvfb :92 -screen 0 1280x800x24 -nolisten tcp -fbdir "$work/framebuffer" >"$work/xvfb.log" 2>&1 &
xvfb=$!; compositor=; probe=
trap 'for p in "$probe" "$compositor" "$xvfb"; do test -z "$p" || kill "$p" 2>/dev/null || true; done' EXIT
sleep 1
${COMPOSITOR_BIN:-/target/debug/forge-compositor} --nested >"$work/compositor.log" 2>&1 &
compositor=$!
sleep 2
test -p "$work/input" || mkfifo "$work/input"
exec 3<>"$work/input"
env WAYLAND_DISPLAY=forge-wayland-0 /work/scale-output 0 <&3 >"$work/probe.log" 2>&1 &
probe=$!
sleep 1
kill -0 "$probe"
grep -Fx 'preferred-scale:120' "$work/probe.log"
grep -Fx 'logical-size:1280x800' "$work/probe.log"
/target/debug/examples/nested_input --isolated-xvfb pixel 800 400 170 51 204
cp "$work/framebuffer/Xvfb_screen0" "$work/viewport-fullscreen.xwd"
printf 'fractional-scale feedback and viewport destination rendered\n'
