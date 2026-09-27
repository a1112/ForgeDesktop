#!/bin/sh
set -eu
work=/work/m2-policy
mkdir -p "$work/runtime" "$work/framebuffer"
chmod 700 "$work/runtime"
export XDG_RUNTIME_DIR="$work/runtime" DISPLAY=:92 XDG_CURRENT_DESKTOP=ForgeDesktop
c++ -fPIC shell/tests/window_probe.cpp -o "$work/probe" $(pkg-config --cflags --libs Qt6Widgets)
Xvfb :92 -screen 0 1280x800x24 -nolisten tcp -fbdir "$work/framebuffer" >"$work/xvfb.log" 2>&1 &
xvfb=$!
compositor= primary= secondary=
trap 'for pid in "$primary" "$secondary" "$compositor" "$xvfb";do test -z "$pid" || kill "$pid" 2>/dev/null || true;done' EXIT
sleep 1
/target/debug/forge-compositor --nested >"$work/compositor.log" 2>&1 &
compositor=$!
sleep 2
env WAYLAND_DISPLAY=forge-wayland-0 QT_QPA_PLATFORM=wayland "$work/probe" >"$work/primary.log" 2>&1 &
primary=$!
sleep 1
env WAYLAND_DISPLAY=forge-wayland-0 QT_QPA_PLATFORM=wayland "$work/probe" second >"$work/secondary.log" 2>&1 &
secondary=$!
sleep 1
input(){ /target/debug/examples/nested_input --isolated-xvfb "$@"; }
green(){ input pixel "$1" "$2" 32 180 100; }
blue(){ input pixel "$1" "$2" 40 100 220; }
control(){ input click 644 765 3;input click "$1" 240;sleep 0.2; }
keys(){ grep -c '^key:' "$1" || true; }
clicks(){ grep -c '^click:' "$1" || true; }
control 550 # primary fullscreen: must cover both former chrome regions
green 100 15
green 640 765
input click 100 15
input click 640 765
grep -Fx 'click:100,15' "$work/primary.log"
grep -Fx 'click:640,765' "$work/primary.log"
cp "$work/framebuffer/Xvfb_screen0" "$work/fullscreen.xwd"
# Intentional launcher access must remain possible from fullscreen.
input key 133 # Super_L
control 625 # normal
green 150 300
control 682 # left snap: x0..639 and work area y38..715
green 50 400
blue 700 400
control 732 # right snap must move, not just acknowledge the verb
blue 400 400
green 900 400
input click 900 400
input word
before=$(keys "$work/primary.log")
before_clicks=$(clicks "$work/primary.log")
control 390 # minimize primary
blue 700 400
input click 900 400 # former primary-only region must not receive hidden input
input word
test "$(keys "$work/primary.log")" = "$before"
test "$(clicks "$work/primary.log")" = "$before_clicks"
test "$(keys "$work/secondary.log")" -ge 5
input click 644 765 # restore primary, including keyboard focus
green 900 400
input word
test "$(keys "$work/primary.log")" -eq "$((before+5))"
input click 644 765 3
input click 400 280 # move primary to workspace 2
input click 938 112
blue 700 400
before=$(keys "$work/primary.log")
before_clicks=$(clicks "$work/primary.log")
input click 900 400
input word
test "$(keys "$work/primary.log")" = "$before"
test "$(clicks "$work/primary.log")" = "$before_clicks"
input click 141 19 # switch to primary workspace: restore input
green 900 400
input word
test "$(keys "$work/primary.log")" -eq "$((before+5))"
before_second=$(keys "$work/secondary.log")
before_second_clicks=$(clicks "$work/secondary.log")
input click 400 400 # former secondary-only area on workspace 1
input word
test "$(keys "$work/secondary.log")" = "$before_second"
test "$(clicks "$work/secondary.log")" = "$before_second_clicks"
cp "$work/framebuffer/Xvfb_screen0" "$work/workspace-2.xwd"
printf 'fullscreen edges rendered + received input; intentional launcher accessible\n'
printf 'left/right pixels, minimize/restore visibility+input, workspace visibility+input passed\n'
