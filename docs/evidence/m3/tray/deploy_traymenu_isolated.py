#!/usr/bin/env python3
"""Stage the tray/menu compositor and Qt candidates in the marked test VM."""
import base64
import gzip
import hashlib
import sys
import time
from pathlib import Path

sys.path.insert(0, '/srv/forge-desktop-build/work')
from isolated_guest import Guest

PAYLOADS = (
    ('/srv/forge-desktop-build/work/rust-arch-target/release/forge-compositor',
     '/usr/bin/forge-compositor'),
    ('/srv/forge-desktop-build/work/notification-build/forge-notificationd',
     '/usr/libexec/forge-desktop/forge-notificationd'),
    ('/srv/forge-desktop-build/work/notification-shell-build/forge-shell',
     '/usr/libexec/forge-desktop/forge-shell'),
)


def run(guest, argv):
    result = guest.execute(argv)
    if result.get('exitcode') != 0:
        raise RuntimeError(f'{argv[0]}: {result}')
    return result.get('out-data', '').strip()


def stage(guest, target, data):
    staged = target + '.traymenu-next'
    compressed = gzip.compress(data, compresslevel=9)
    if len(base64.b64encode(compressed)) >= 3 * 1024 * 1024:
        raise RuntimeError(f'compressed guest payload is too large: {target}')
    pid = guest.call('guest-exec', path='/usr/bin/tee', arg=[staged + '.gz'],
        **{'input-data': base64.b64encode(compressed).decode('ascii'),
           'capture-output': False})['pid']
    for _ in range(100):
        result = guest.call('guest-exec-status', pid=pid)
        if result['exited']:
            if result.get('exitcode') != 0:
                raise RuntimeError(f'guest write failed: {result}')
            break
        time.sleep(0.1)
    else:
        raise TimeoutError('guest write still running')
    run(guest, ['/usr/bin/gzip', '-d', '-f', staged + '.gz'])
    run(guest, ['/usr/bin/chmod', '0755', staged])
    run(guest, ['/usr/bin/chown', 'root:root', staged])
    expected = hashlib.sha256(data).hexdigest()
    actual = run(guest, ['/usr/bin/sha256sum', staged]).split()[0]
    if actual != expected:
        raise RuntimeError(f'guest staged digest mismatch for {target}')
    run(guest, ['/usr/bin/mv', '-f', staged, target])
    print(f'{target} sha256={expected}')


def main():
    guest = Guest()
    try:
        if run(guest, ['/usr/bin/cat', '/etc/forgedesktop-isolated-test']) != \
                'forgedesktop-daily-test':
            raise RuntimeError('refusing unmarked guest')
        for source, target in PAYLOADS:
            if guest.execute(['/usr/bin/test', '-e', target + '.before-traymenu']).get('exitcode') != 0:
                run(guest, ['/usr/bin/cp', '-a', target, target + '.before-traymenu'])
            stage(guest, target, Path(source).read_bytes())
    finally:
        guest.close()


if __name__ == '__main__':
    main()
