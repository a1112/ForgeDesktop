#!/bin/sh
# Host nspawn must bind the compiled persistent_ime fixture over /usr/bin/fcitx5.
set -eu
work=/work/m3-persistent-ime
mkdir -p "$work/runtime" "$work/framebuffer"
chmod 700 "$work/runtime"
export XDG_RUNTIME_DIR="$work/runtime" DISPLAY=:92 LANG=C.UTF-8
c++ -fPIC crates/forge-compositor/tests/qt_probe.cpp -o "$work/probe" $(pkg-config --cflags --libs Qt6Widgets)
Xvfb :92 -screen 0 1280x800x24 -nolisten tcp -fbdir "$work/framebuffer" >"$work/xvfb.log" 2>&1 &
xvfb=$!; compositor=; first=; second=
trap 'for p in "$second" "$first" "$compositor" "$xvfb"; do test -z "$p" || kill "$p" 2>/dev/null || true; done' EXIT
sleep 1
/target/debug/forge-compositor --nested >"$work/compositor.log" 2>&1 &
compositor=$!
sleep 1
env WAYLAND_DISPLAY=forge-wayland-0 QT_QPA_PLATFORM=wayland QT_IM_MODULE=wayland QT_WAYLAND_TEXT_INPUT_PROTOCOL=zwp_text_input_v3 "$work/probe" "${1:-normal}" >"$work/first.log" 2>&1 &
first=$!
sleep 1
input(){ /target/debug/examples/nested_input --isolated-xvfb "$@"; }
input pointer 400 300
sleep 0.3
if test -z "${FORGE_TEST_IME_ALPHA:-}"; then input pixel 167 571 0 255 0; fi
if test "${1:-normal}" = popup; then
 input click 400 590
 sleep 1.5
 cp "$work/framebuffer/Xvfb_screen0" "$work/menu-active.xwd"
 if test -n "${FORGE_TEST_IME_ALPHA:-}"; then
  python crates/forge-compositor/tests/count_ime_pixels.py "$work/menu-active.xwd" alpha
  exit 0
 fi
 python crates/forge-compositor/tests/count_ime_pixels.py "$work/menu-active.xwd" 800
 exit 0
fi
env WAYLAND_DISPLAY=forge-wayland-0 QT_QPA_PLATFORM=wayland QT_IM_MODULE=wayland QT_WAYLAND_TEXT_INPUT_PROTOCOL=zwp_text_input_v3 "$work/probe" >"$work/second.log" 2>&1 &
second=$!
sleep 1
input drag 400 195 900 195
sleep 0.5
input pixel 697 601 0 255 0
input pixel 167 571 239 239 239
cp "$work/framebuffer/Xvfb_screen0" "$work/focused.xwd"
python crates/forge-compositor/tests/count_ime_pixels.py "$work/focused.xwd" 800
printf 'live input-method popup reparented without stale rendering\n'

