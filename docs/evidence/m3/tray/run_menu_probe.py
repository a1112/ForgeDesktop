#!/usr/bin/env python3
"""Run the lab-only Qt DBusMenu type probe in the marked disposable VM."""
import base64
import re
import sys
import time
from pathlib import Path

sys.path.insert(0, '/srv/forge-desktop-build/work')
from isolated_guest import Guest

SOURCE = Path('/srv/forge-desktop-build/work/notification-build/menu_type_probe')
TARGET = '/tmp/forge-menu-type-probe'
BUS_ENV = 'DBUS_SESSION_BUS_ADDRESS=unix:path=/run/user/1000/bus'


def main():
    guest = Guest()
    try:
        marker = guest.execute(['/usr/bin/cat', '/etc/forgedesktop-isolated-test'])
        if marker.get('out-data', '').strip() != 'forgedesktop-daily-test':
            raise RuntimeError('unmarked guest')
        payload = base64.b64encode(SOURCE.read_bytes()).decode('ascii')
        pid = guest.call('guest-exec', path='/usr/bin/tee', arg=[TARGET],
                         **{'input-data': payload, 'capture-output': False})['pid']
        for _ in range(100):
            result = guest.call('guest-exec-status', pid=pid)
            if result['exited']:
                if result.get('exitcode') != 0:
                    raise RuntimeError(result)
                break
            time.sleep(0.1)
        else:
            raise TimeoutError('guest write still running')
        guest.execute(['/usr/bin/chmod', '0755', TARGET])
        registered = guest.execute(['/usr/bin/runuser', '-u', 'forge', '--',
            '/usr/bin/env', BUS_ENV, '/usr/bin/gdbus', 'call', '--session',
            '--dest', 'org.kde.StatusNotifierWatcher',
            '--object-path', '/StatusNotifierWatcher',
            '--method', 'org.freedesktop.DBus.Properties.Get',
            'org.kde.StatusNotifierWatcher', 'RegisteredStatusNotifierItems'])
        match = re.search(r'(:1\.\d+)/StatusNotifierItem',
                          registered.get('out-data', ''))
        if not match:
            raise RuntimeError('no live status item')
        result = guest.execute(['/usr/bin/runuser', '-u', 'forge', '--',
            '/usr/bin/env', BUS_ENV, TARGET, match.group(1)])
        print(result)
    finally:
        guest.close()


if __name__ == '__main__':
    main()
