#!/bin/sh
# Install ONLY in the disposable forgedesktop-daily-test image.
set -eu
test "$(cat /etc/forgedesktop-isolated-test)" = forgedesktop-daily-test
exec >/var/log/forgedesktop-m1-fault.log 2>&1
for attempt in $(seq 1 300); do
    [ ! -S /run/user/1000/forge-wayland-0 ] || break
    sleep 0.1
done
test -S /run/user/1000/forge-wayland-0
sleep 60
target=$(/usr/bin/pgrep -u 1000 -f '^/usr/bin/forge-compositor --drm /dev/dri/card1$')
case "$target" in ''|*[!0-9]*) echo 'Expected exactly one compositor PID'; exit 1;; esac
printf 'M1_FAULT_SIGKILL pid=%s\n' "$target"
/usr/bin/ps -p "$target" -o pid,uid,comm
kill -KILL "$target"
sleep 10
/usr/bin/systemctl --no-pager --full status lightdm.service
/usr/bin/loginctl list-sessions
/usr/bin/journalctl -b -u lightdm.service --no-pager -n 25
printf 'M1_FAULT_CHECK_FINISHED\n'
