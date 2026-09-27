#!/bin/sh
set -eu
work=/work/m1-nested-lifecycle
src=/work/forge-desktop/crates/forge-compositor/tests
mkdir -p "$work/runtime"
chmod 700 "$work/runtime"
export XDG_RUNTIME_DIR="$work/runtime" DISPLAY=:92 WAYLAND_DISPLAY=forge-wayland-0
wayland-scanner client-header /usr/share/qt6/wayland/protocols/xdg-shell/xdg-shell.xml "$work/xdg-shell.h"
wayland-scanner private-code /usr/share/qt6/wayland/protocols/xdg-shell/xdg-shell.xml "$work/xdg-shell.c"
cc "$src/lifecycle_probe.c" "$work/xdg-shell.c" -I"$work" -o "$work/probe" $(pkg-config --cflags --libs wayland-client)
Xvfb :92 -screen 0 1280x800x24 -nolisten tcp >"$work/xvfb.log" 2>&1 &
xvfb=$!; compositor= a= b=
trap 'for pid in "$a" "$b" "$compositor" "$xvfb"; do test -z "$pid" || kill "$pid" 2>/dev/null || true; done' EXIT
sleep 1
/target/debug/forge-compositor --nested >"$work/compositor.log" 2>&1 &
compositor=$!
sleep 1
test -p "$work/a.in" || mkfifo "$work/a.in"
test -p "$work/b.in" || mkfifo "$work/b.in"
exec 3<>"$work/a.in" 4<>"$work/b.in"
"$work/probe" <&3 >"$work/a.log" 2>&1 & a=$!
sleep 1
printf m >&3
sleep 1
/target/debug/examples/nested_input --isolated-xvfb pointer
"$work/probe" <&4 >"$work/b.log" 2>&1 & b=$!
sleep 1
# B has an xdg_toplevel and initial configure, but no buffer: A retains keys.
/target/debug/examples/nested_input --isolated-xvfb keys
sleep 1
grep -q 'key:33:1' "$work/a.log"
! grep -q 'keyboard-enter' "$work/b.log"
printf m >&4
sleep 1
# No motion since B mapped under the pointer: both click and wheel belong to B.
/target/debug/examples/nested_input --isolated-xvfb click-wheel
sleep 1
grep -q 'button:272:1' "$work/b.log"
grep -q 'axis:0' "$work/b.log"
! grep -q 'button:272:1\|axis:0' "$work/a.log"
printf u >&4
sleep 1
/target/debug/examples/nested_input --isolated-xvfb keys
sleep 1
test "$(grep -c 'key:33:1' "$work/a.log")" -eq 2
! grep -q 'key:33:1' "$work/b.log"
grep -q keyboard-leave "$work/b.log"
printf m >&4
sleep 1
/target/debug/examples/nested_input --isolated-xvfb keys
sleep 1
grep -q 'key:33:1' "$work/b.log"
# Shift pressed before host focus leaves must be released even without KeyRelease.
/target/debug/examples/nested_input --isolated-xvfb focus-cycle
sleep 1
grep -q 'key:42:0' "$work/b.log"
awk '/modifiers:/ {last=$0} END {exit last!="modifiers:0"}' "$work/b.log"
kill -0 "$compositor"
printf 'unmapped focus, NULL-buffer hide/remap, stationary click/wheel and host modifier release passed\n'
