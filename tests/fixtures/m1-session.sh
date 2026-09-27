#!/bin/sh
# Disposable LightDM acceptance image only; fixed probes, no command interface.
set -u
export WAYLAND_DISPLAY=forge-wayland-0
export QT_QPA_PLATFORM=wayland QT_QUICK_BACKEND=software
export LIBGL_ALWAYS_SOFTWARE=1 GDK_BACKEND=wayland
qt_pid='' gtk_pid=''
/usr/bin/forge-compositor --drm /dev/dri/card1 &
compositor_pid=$!
cleanup() {
    for child in "$qt_pid" "$gtk_pid" "$compositor_pid"; do
        [ -z "$child" ] || kill "$child" 2>/dev/null || :
    done
    wait 2>/dev/null || :
}
trap cleanup EXIT
trap 'exit 143' TERM HUP INT
for attempt in $(seq 1 100); do
    kill -0 "$compositor_pid" 2>/dev/null || break
    if [ -S "$XDG_RUNTIME_DIR/$WAYLAND_DISPLAY" ]; then
        /usr/libexec/forge-desktop/m1-qt-probe &
        qt_pid=$!
        sleep 2
        /usr/libexec/forge-desktop/m1-gtk-probe &
        gtk_pid=$!
        break
    fi
    sleep 0.1
done
wait "$compositor_pid"
status=$?
exit "$status"
