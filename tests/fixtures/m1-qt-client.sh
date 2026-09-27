#!/bin/sh
# Only for an isolated M1 acceptance image.
set -eu
for attempt in $(seq 1 100); do
    if [ -S "$XDG_RUNTIME_DIR/forge-wayland-0" ]; then
        exec /usr/libexec/forge-desktop/m1-qt-probe
    fi
    sleep 0.1
done
echo 'M1 Qt client: compositor socket did not appear' >&2
exit 1
