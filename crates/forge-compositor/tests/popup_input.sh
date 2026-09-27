#!/bin/sh
set -eu
work=/work/m3-popup-input
mkdir -p "$work/runtime" "$work/framebuffer"
chmod 700 "$work/runtime"
export XDG_RUNTIME_DIR="$work/runtime" DISPLAY=:92 LANG=C.UTF-8 FORGE_TEST_IME_ALPHA=1
protocols=/cargo/registry/src/index.crates.io-1949cf8c6b5b557f/wayland-protocols-0.32.13/protocols
wayland-scanner client-header "$protocols/stable/xdg-shell/xdg-shell.xml" "$work/xdg-shell.h"
wayland-scanner private-code "$protocols/stable/xdg-shell/xdg-shell.xml" "$work/xdg-shell.c"
wayland-scanner client-header "$protocols/unstable/text-input/text-input-unstable-v3.xml" "$work/text-input.h"
wayland-scanner private-code "$protocols/unstable/text-input/text-input-unstable-v3.xml" "$work/text-input.c"
cc -I"$work" crates/forge-compositor/tests/popup_input.c "$work/xdg-shell.c" "$work/text-input.c" -lwayland-client -o "$work/probe"
Xvfb :92 -screen 0 1280x800x24 -nolisten tcp -fbdir "$work/framebuffer" >"$work/xvfb.log" 2>&1 &
xvfb=$!; compositor=; probe=
trap 'for p in "$probe" "$compositor" "$xvfb"; do test -z "$p" || kill "$p" 2>/dev/null || true; done' EXIT
sleep 1
/target/debug/forge-compositor --nested >"$work/compositor.log" 2>&1 &
compositor=$!
sleep 1
test -p "$work/input" || mkfifo "$work/input"
exec 3<>"$work/input"
env WAYLAND_DISPLAY=forge-wayland-0 "$work/probe" ${1:-} <&3 >"$work/probe.log" 2>&1 &
probe=$!
sleep 1
input(){ /target/debug/examples/nested_input --isolated-xvfb "$@"; }
input click 300 280
sleep 0.5
if test "${1:-}" = bogus; then
 grep -q popup-done "$work/probe.log"
 if grep -q enabled-popup-input "$work/probe.log"; then exit 1; fi
 echo 'invalid popup serial rejected'
 exit 0
fi
grep -q enabled-popup-input "$work/probe.log"
for n in 1 2 3; do
 printf d >&3
 sleep 0.2
 printf e >&3
 sleep 0.3
done
cp "$work/framebuffer/Xvfb_screen0" "$work/toggled.xwd"
python crates/forge-compositor/tests/count_ime_pixels.py "$work/toggled.xwd" alpha
printf 'xdg-popup input disable/enable preserved one live candidate\n'
