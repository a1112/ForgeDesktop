#!/bin/sh
# Ordinary build user, isolated Arch container, Xvfb :92. No production IPC test door.
set -eu
work=/work/m2-smoke
mkdir -p "$work/runtime" "$work/framebuffer"
chmod 700 "$work/runtime"
export XDG_RUNTIME_DIR="$work/runtime" DISPLAY=:92 XDG_CURRENT_DESKTOP=ForgeDesktop FORGE_DESKTOP_TRACE=1
export FORGE_DESKTOP_PERF_FILE="$work/frames-$(date +%s).csv"
c++ -fPIC crates/forge-compositor/tests/qt_probe.cpp -o "$work/qt" $(pkg-config --cflags --libs Qt6Widgets)
cc crates/forge-compositor/tests/gtk_probe.c -o "$work/gtk" $(pkg-config --cflags --libs gtk+-3.0)
c++ -fPIC shell/tests/spoof.cpp -o "$work/spoof" $(pkg-config --cflags --libs Qt6Widgets)
Xvfb :92 -screen 0 1280x800x24 -nolisten tcp -fbdir "$work/framebuffer" >"$work/xvfb.log" 2>&1 &
xvfb=$!
compositor= qt= gtk= spoof=
trap 'for pid in "$spoof" "$qt" "$gtk" "$compositor" "$xvfb"; do test -z "$pid" || kill "$pid" 2>/dev/null || true; done' EXIT
sleep 1
/target/debug/forge-compositor --nested >"$work/compositor.log" 2>&1 &
compositor=$!
sleep 2
cp "$work/framebuffer/Xvfb_screen0" "$work/desktop.xwd"
env WAYLAND_DISPLAY=forge-wayland-0 QT_QPA_PLATFORM=wayland "$work/qt" >"$work/qt.log" 2>&1 &
qt=$!
env WAYLAND_DISPLAY=forge-wayland-0 GDK_BACKEND=wayland "$work/gtk" >"$work/gtk.log" 2>&1 &
gtk=$!
sleep 2
input(){ /target/debug/examples/nested_input --isolated-xvfb "$@"; }
control(){ input click 644 765 3; input click "$1" 240; }
input click 644 765
input click 400 558
input word
input click 700 765
input click 400 370
input word
grep -Fx 'qt-entry:forge' "$work/qt.log"
grep -Fx 'gtk-entry:forge' "$work/gtk.log"
shell=$(sed -n 's/^ForgeDesktop shell started pid=//p' "$work/compositor.log" | tail -1)
test "$(awk '{print $4}' /proc/"$shell"/stat)" = "$compositor"
kill -KILL "$shell"
sleep 2
kill -0 "$qt"
kill -0 "$gtk"
next=$(sed -n 's/^ForgeDesktop shell started pid=//p' "$work/compositor.log" | tail -1)
test "$next" != "$shell"
input click 644 765
input click 400 558
input word
input click 700 765
input click 400 370
input word
grep -Fx 'qt-entry:forgeforge' "$work/qt.log"
grep -Fx 'gtk-entry:forgeforge' "$work/gtk.log"
printf 'same GTK/Qt PIDs and existing editable text survived shell SIGKILL\n'
control 470 # maximize
grep -Fx 'qt-size:1274x645' "$work/qt.log"
control 550 # fullscreen
grep -Fx 'qt-size:1280x800' "$work/qt.log"
control 625 # normal
control 682 # snap left
grep -Fx 'qt-size:634x645' "$work/qt.log"
control 732 # snap right
control 390 # minimize
input click 644 765 # restore
input click 644 765 3
input click 400 280 # move workspace 2
input click 938 112 # close launcher
input click 141 19 # switch workspace 2
sleep 1
cp "$work/framebuffer/Xvfb_screen0" "$work/workspace-2.xwd"
input click 102 19 # workspace 1
input click 45 19 # launcher
sleep 1
cp "$work/framebuffer/Xvfb_screen0" "$work/launcher.xwd"
input click 690 230 # actual installed CMake desktop entry, GIO Exec
sleep 2
cp "$work/framebuffer/Xvfb_screen0" "$work/launched-cmake.xwd"
cmake=
for path in /proc/[0-9]*/comm;do
    if test "$(cat "$path" 2>/dev/null || true)" = cmake-gui;then cmake=${path#/proc/};cmake=${cmake%/comm};break;fi
done
test -n "$cmake"
test "$(readlink /proc/"$cmake"/fd/0)" = /dev/null
shell=$(sed -n 's/^ForgeDesktop shell started pid=//p' "$work/compositor.log" | tail -1)
test "$(awk '{print $4}' /proc/"$shell"/stat)" = "$compositor"
kill -KILL "$shell"
sleep 2
kill -0 "$cmake"
printf 'GIO-launched CMake retained its PID across shell SIGKILL; private fd not inherited\n'
grep -F 'Window("maximize"' "$work/compositor.log"
grep -F 'Window("fullscreen"' "$work/compositor.log"
grep -F 'Window("left"' "$work/compositor.log"
grep -F 'Window("right"' "$work/compositor.log"
grep -F 'Move(' "$work/compositor.log"
grep -F 'Workspace(1)' "$work/compositor.log"
env WAYLAND_DISPLAY=forge-wayland-0 QT_QPA_PLATFORM=wayland "$work/spoof" >"$work/spoof.log" 2>&1 &
spoof=$!
sleep 1
grep -Fx 'spoof-size:634x447' "$work/spoof.log"
if grep -F 'x38' "$work/spoof.log";then exit 1;fi
printf 'ordinary title/app-id spoof stayed an ordinary application\n'
kill -0 "$compositor"
kill -0 "$qt"
kill -0 "$gtk"
input click 588 765 3 # first task with four application tiles
input click 787 240 # close the Qt fixture through typed private request
sleep 1
if kill -0 "$qt" 2>/dev/null;then printf 'Qt close request did not exit\n' >&2;exit 1;fi
grep -F 'Window("close"' "$work/compositor.log"
qt=
printf 'M2 nested smoke passed; screenshots and capped timing samples recorded\n'
