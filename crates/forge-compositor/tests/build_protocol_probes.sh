#!/bin/sh
# Reproducible native protocol fixtures using the pinned Cargo XML inputs.
set -eu
work=/work/m3-protocols
mkdir -p "$work"
registry=/cargo/registry/src/index.crates.io-1949cf8c6b5b557f
protocols="$registry/wayland-protocols-0.32.13/protocols"
generate(){ wayland-scanner client-header "$2" "$work/$1.h"; wayland-scanner private-code "$2" "$work/$1.c"; }
generate xdg-shell "$protocols/stable/xdg-shell/xdg-shell.xml"
generate fractional-scale "$protocols/staging/fractional-scale/fractional-scale-v1.xml"
generate viewporter "$protocols/stable/viewporter/viewporter.xml"
generate input-method "$registry/wayland-protocols-misc-0.3.12/protocols/input-method-unstable-v2.xml"
cc crates/forge-compositor/tests/output_probe.c -lwayland-client -o /work/output-probe
cc -I"$work" crates/forge-compositor/tests/fullscreen_output.c "$work/xdg-shell.c" -lwayland-client -o /work/fullscreen-output
cc -I"$work" crates/forge-compositor/tests/scale_output.c "$work/xdg-shell.c" "$work/fractional-scale.c" "$work/viewporter.c" -lwayland-client -o /work/scale-output
cc -I"$work" crates/forge-compositor/tests/persistent_ime.c "$work/input-method.c" -lwayland-client -o /work/persistent-ime
