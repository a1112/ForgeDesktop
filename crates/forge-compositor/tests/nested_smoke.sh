#!/bin/sh
# Run within the disposable build container, as its ordinary build user.
set -eu
toolkit=${1:-gtk}
case "$toolkit" in gtk|qt) ;; *) exit 2 ;; esac
work=/work/m1-nested-$toolkit
mkdir -p "$work/runtime" "$work/framebuffer"
chmod 700 "$work/runtime"
export XDG_RUNTIME_DIR="$work/runtime" DISPLAY=:92
if test "$toolkit" = gtk; then
    cc /work/forge-desktop/crates/forge-compositor/tests/gtk_probe.c -o "$work/probe" $(pkg-config --cflags --libs gtk+-3.0)
else
    c++ -fPIC /work/forge-desktop/crates/forge-compositor/tests/qt_probe.cpp -o "$work/probe" $(pkg-config --cflags --libs Qt6Widgets)
fi
Xvfb :92 -screen 0 1280x800x24 -nolisten tcp -fbdir "$work/framebuffer" >"$work/xvfb.log" 2>&1 &
xvfb=$!
compositor= gtk= second=
trap 'test -z "$second" || kill "$second" 2>/dev/null || true; test -z "$gtk" || kill "$gtk" 2>/dev/null || true; test -z "$compositor" || kill "$compositor" 2>/dev/null || true; kill "$xvfb" 2>/dev/null || true' EXIT
sleep 1
/target/debug/forge-compositor --nested >"$work/compositor.log" 2>&1 &
compositor=$!
sleep 1
env WAYLAND_DISPLAY=forge-wayland-0 GDK_BACKEND=wayland QT_QPA_PLATFORM=wayland QT_QUICK_BACKEND=software "$work/probe" >"$work/client.log" 2>&1 &
gtk=$!
sleep 2
/target/debug/examples/nested_input --isolated-xvfb "$toolkit"
sleep 1
kill -0 "$compositor"
kill -0 "$gtk"
grep -F "$toolkit-entry:forge" "$work/client.log"
if test "$toolkit" = qt; then
    grep -Fx 'qt-wheel:0,120' "$work/client.log"
    grep -Fx 'qt-wheel:-120,0' "$work/client.log"
    awk -F'[:x]' '/^qt-size:/ {if (++n==2) start=$2; end=$2} END {if (n<3 || end-start!=100) exit 1; print "Qt resize +100 pixels verified"}' "$work/client.log"
    env WAYLAND_DISPLAY=forge-wayland-0 QT_QPA_PLATFORM=wayland "$work/probe" >"$work/second-client.log" 2>&1 &
    second=$!
    sleep 1
    /target/debug/examples/nested_input --isolated-xvfb focus
    sleep 1
    grep -F 'qt-entry:forgeforge' "$work/client.log"
    grep -Fx 'qt-entry:forge' "$work/second-client.log"
fi
cp "$work/framebuffer/Xvfb_screen0" "$work/nested-$toolkit.xwd"
socket_before=$(stat -c %i "$XDG_RUNTIME_DIR/forge-wayland-0")
set +e
timeout 3 /target/debug/forge-compositor --nested >"$work/duplicate.log" 2>&1
duplicate_status=$?
set -e
test "$duplicate_status" -eq 1
test "$(stat -c %i "$XDG_RUNTIME_DIR/forge-wayland-0")" = "$socket_before"
kill -0 "$compositor"
kill -KILL "$compositor"
wait "$compositor" 2>/dev/null || true
/target/debug/forge-compositor --nested >"$work/restart.log" 2>&1 &
compositor=$!
sleep 1
kill -0 "$compositor"
test -S "$XDG_RUNTIME_DIR/forge-wayland-0"
printf 'nested %s Wayland rendering + five keyboard keys passed\n' "$toolkit"
printf 'live socket collision rejected; SIGKILL socket recovery passed\n'
