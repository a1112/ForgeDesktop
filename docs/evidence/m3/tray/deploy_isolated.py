#!/usr/bin/env python3
"""Lab-only tray candidate deployment to the marked disposable guest.

Run on the VM host. The daily VM is never selected by this script.
"""
import base64
import hashlib
import sys
import time
from pathlib import Path

sys.path.insert(0, '/srv/forge-desktop-build/work')
from isolated_guest import Guest

MARKER = 'forgedesktop-daily-test'
PAYLOADS = (
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


def write_file(guest, data, path):
    started = guest.call('guest-exec', path='/usr/bin/tee', arg=[path],
                         **{'input-data': base64.b64encode(data).decode('ascii'),
                            'capture-output': False})
    pid = started['pid']
    for _ in range(100):
        result = guest.call('guest-exec-status', pid=pid)
        if result['exited']:
            if result.get('exitcode') != 0:
                raise RuntimeError(f'guest write failed: {result}')
            return
        time.sleep(0.1)
    raise TimeoutError('guest write is still running; inspect before retrying')


def main():
    guest = Guest()
    try:
        if run(guest, ['/usr/bin/cat', '/etc/forgedesktop-isolated-test']) != MARKER:
            raise RuntimeError('refusing an unmarked guest')
        hashes = {}
        for source, target in PAYLOADS:
            data = Path(source).read_bytes()
            digest = hashlib.sha256(data).hexdigest()
            backup = target + '.before-tray'
            staged = target + '.tray-next'
            run(guest, ['/usr/bin/cp', '-a', target, backup])
            write_file(guest, data, staged)
            run(guest, ['/usr/bin/chmod', '0755', staged])
            run(guest, ['/usr/bin/chown', 'root:root', staged])
            actual = run(guest, ['/usr/bin/sha256sum', staged]).split()[0]
            if actual != digest:
                raise RuntimeError(f'staged digest mismatch for {target}')
            run(guest, ['/usr/bin/mv', '-f', staged, target])
            hashes[target] = digest
        for target in hashes:
            result = guest.execute(['/usr/bin/pkill', '-TERM', '-f', '^' + target + '$'])
            if result.get('exitcode') not in (0, 1):
                raise RuntimeError(f'cannot request restart of {target}: {result}')
        time.sleep(3)
        for target, digest in hashes.items():
            pids = run(guest, ['/usr/bin/pgrep', '-f', '^' + target + '$']).split()
            if len(pids) != 1:
                raise RuntimeError(f'expected one restarted {target}, got {pids}')
            actual = run(guest, ['/usr/bin/sha256sum', f'/proc/{pids[0]}/exe']).split()[0]
            if actual != digest:
                raise RuntimeError(f'running process mismatch for {target}')
            print(f'{target} pid={pids[0]} sha256={digest}')
    finally:
        guest.close()


if __name__ == '__main__':
    main()
