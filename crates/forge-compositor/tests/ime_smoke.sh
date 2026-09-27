#!/bin/sh
# Invoke under dbus-run-session inside the disposable build container.
set -eu
toolkit=${1:-gtk}
case "$toolkit" in gtk|qt) ;; *) exit 2;; esac
work=/work/m3-ime-$toolkit
mkdir -p "$work/runtime" "$work/framebuffer" "$work/config/fcitx5"
chmod 700 "$work/runtime" "$work/config"
export XDG_RUNTIME_DIR="$work/runtime" XDG_CONFIG_HOME="$work/config" DISPLAY=:92 LANG=C.UTF-8 LC_ALL=C.UTF-8
cat >"$work/config/fcitx5/profile" <<'EOF'
[Groups/0]
Name=Default
Default Layout=us
DefaultIM=pinyin

[Groups/0/Items/0]
Name=keyboard-us
Layout=

[Groups/0/Items/1]
Name=pinyin
Layout=

[GroupOrder]
0=Default
EOF
if test "$toolkit" = gtk; then
 cc crates/forge-compositor/tests/gtk_probe.c -o "$work/probe" $(pkg-config --cflags --libs gtk+-3.0)
else
 c++ -fPIC crates/forge-compositor/tests/qt_probe.cpp -o "$work/probe" $(pkg-config --cflags --libs Qt6Widgets)
fi
Xvfb :92 -screen 0 1280x800x24 -nolisten tcp -fbdir "$work/framebuffer" >"$work/xvfb.log" 2>&1 &
xvfb=$!; compositor=; client=
trap 'for p in "$client" "$compositor" "$xvfb"; do test -z "$p" || kill "$p" 2>/dev/null || true; done' EXIT
sleep 1
/target/debug/forge-compositor --nested >"$work/compositor.log" 2>&1 &
compositor=$!
sleep 2
env WAYLAND_DISPLAY=forge-wayland-0 GDK_BACKEND=wayland GTK_IM_MODULE=wayland QT_QPA_PLATFORM=wayland QT_IM_MODULE=wayland QT_WAYLAND_TEXT_INPUT_PROTOCOL=zwp_text_input_v3 "$work/probe" >"$work/client.log" 2>&1 &
client=$!
sleep 1
input(){ /target/debug/examples/nested_input --isolated-xvfb "$@"; }
input pointer 400 300
sleep 0.3
fcitx5-remote -s pinyin
fcitx5-remote -o
sleep 0.5
for key in 57 31 43 38 32; do input key "$key"; done
sleep 0.5
if test "$toolkit" = gtk; then input pixel 200 360 192 192 192; fi
if test "$toolkit" = qt; then input pixel 167 571 128 128 128; fi
cp "$work/framebuffer/Xvfb_screen0" "$work/candidate.xwd"
input key 65
sleep 0.5
grep -Fx "$toolkit-entry:你好" "$work/client.log"
# Kill only our compositor's supervised child; recovery must reconnect its role.
ime=$(sed -n 's/^ForgeDesktop input method started pid=//p' "$work/compositor.log" | tail -1)
test -n "$ime"
kill -KILL "$ime"
sleep 3
replacement=$(sed -n 's/^ForgeDesktop input method started pid=//p' "$work/compositor.log" | tail -1)
test "$replacement" != "$ime"
fcitx5-remote -s pinyin
fcitx5-remote -o
sleep 0.5
for key in 57 31 43 38 32 65; do input key "$key"; done
sleep 0.5
grep -Fx "$toolkit-entry:你好你好" "$work/client.log"
printf '%s native text-input-v3, Chinese composition and IME restart passed\n' "$toolkit"
