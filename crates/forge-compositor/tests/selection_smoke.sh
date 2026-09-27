#!/bin/sh
# Disposable Xvfb host; applications are two distinct native Wayland clients.
set -eu
work=/work/m3-selection
mkdir -p "$work/runtime" "$work/framebuffer"
chmod 700 "$work/runtime"
export XDG_RUNTIME_DIR="$work/runtime" DISPLAY=:92 LANG=C.UTF-8 LC_ALL=C.UTF-8
cc /work/forge-desktop/crates/forge-compositor/tests/selection_probe.c -o "$work/probe" $(pkg-config --cflags --libs gtk+-3.0)
cc /work/forge-desktop/crates/forge-compositor/tests/ime_registry_probe.c -o "$work/registry" $(pkg-config --cflags --libs wayland-client)
Xvfb :92 -screen 0 1280x800x24 -nolisten tcp -fbdir "$work/framebuffer" >"$work/xvfb.log" 2>&1 &
xvfb=$!; compositor=; producer=; consumer=
trap 'for p in "$consumer" "$producer" "$compositor" "$xvfb"; do test -z "$p" || kill "$p" 2>/dev/null || true; done' EXIT
sleep 1
/target/debug/forge-compositor --nested >"$work/compositor.log" 2>&1 &
compositor=$!
sleep 1
env WAYLAND_DISPLAY=forge-wayland-0 timeout 5 "$work/registry"
env WAYLAND_DISPLAY=forge-wayland-0 GDK_BACKEND=wayland "$work/probe" producer >"$work/producer.log" 2>&1 &
producer=$!
sleep 1
input='/target/debug/examples/nested_input --isolated-xvfb'
$input click 400 250
$input key 33
sleep 1
env WAYLAND_DISPLAY=forge-wayland-0 GDK_BACKEND=wayland "$work/probe" consumer >"$work/consumer.log" 2>&1 &
consumer=$!
sleep 1
$input click 400 250
$input key 55
sleep 1
grep -Fx 'clipboard:Forge 中文剪贴板 😀' "$work/consumer.log"
grep -Fx 'primary:Forge 中文剪贴板 😀' "$work/consumer.log"
# Client supplies a solid green 20x20 cursor with hotspot (3,5).
$input pixel 397 245 0 255 0
$input pointer 400 300
sleep 0.1
$input pixel 397 295 0 255 0
$input drag 150 400 800 400
sleep 1
grep -Fx 'drop:file-uri-exact' "$work/consumer.log"
cp "$work/framebuffer/Xvfb_screen0" "$work/selection.xwd"
printf 'cross-process UTF-8 clipboard/primary, cursor surface/hotspot, file URI drag/drop passed\n'
