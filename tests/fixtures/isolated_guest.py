#!/usr/bin/env python3
"""Lab-only QEMU Guest Agent client for the disposable native-desktop VM.

Never ship this fixture or qemu-guest-agent in the release desktop bundle. The
channel gives the trusted VM host root execution inside its own isolated guest.
No TCP listener, shell expansion, or production-instance selection is provided.
"""
import argparse
import base64
import json
import secrets
import socket
import stat
import os
from pathlib import Path
import time

DIRECTORY = Path('/srv/forge-desktop-build/daily-test-vm')
LIMIT = 4 * 1024 * 1024


class Guest:
    def __init__(self):
        info = DIRECTORY.stat()
        if DIRECTORY.is_symlink() or info.st_uid != os.geteuid() or info.st_mode & 0o077:
            raise ValueError('isolated VM directory is not private to the current user')
        path = DIRECTORY / 'qga.sock'
        if path.is_symlink() or not stat.S_ISSOCK(path.stat().st_mode):
            raise ValueError('isolated guest socket missing')
        self.socket = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
        self.socket.settimeout(10)
        self.socket.connect(str(path))
        self.reader = self.socket.makefile('rb')
        nonce = secrets.randbits(63)
        self.socket.sendall(b'\xff' + json.dumps(dict(execute='guest-sync-delimited',
                              arguments=dict(id=nonce))).encode() + b'\n')
        for _ in range(16):
            raw = self.line()
            if b'\xff' in raw:
                response = json.loads(raw.rsplit(b'\xff', 1)[1])
                if response.get('return') == nonce:
                    break
        else:
            raise ValueError('guest agent synchronization failed')

    def line(self):
        data = self.reader.readline(LIMIT + 1)
        if len(data) > LIMIT or not data.endswith(b'\n'):
            raise ValueError('guest response is incomplete or too large')
        return data

    def call(self, command, **arguments):
        self.socket.sendall(json.dumps(dict(execute=command, arguments=arguments)).encode() + b'\n')
        response = json.loads(self.line())
        if 'error' in response:
            raise RuntimeError(response['error'])
        return response['return']

    def execute(self, argv, timeout=30):
        pid = self.call('guest-exec', path=argv[0], arg=argv[1:], **{'capture-output': True})['pid']
        deadline = time.monotonic() + timeout
        while time.monotonic() < deadline:
            result = self.call('guest-exec-status', pid=pid)
            if result['exited']:
                for key in ('out-data', 'err-data'):
                    if key in result:
                        result[key] = base64.b64decode(result[key], validate=True).decode('utf-8', 'replace')
                return result
            time.sleep(0.1)
        raise TimeoutError('guest command still running; do not blindly retry a mutation')

    def close(self):
        self.reader.close()
        self.socket.close()


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--timeout', type=int, default=30)
    parser.add_argument('command', nargs=argparse.REMAINDER)
    args = parser.parse_args()
    if not args.command or not args.command[0].startswith('/') or not 1 <= args.timeout <= 600:
        parser.error('provide an absolute guest executable and a timeout from 1 to 600 seconds')
    guest = Guest()
    try:
        marker = guest.execute(['/usr/bin/cat', '/etc/forgedesktop-isolated-test'])
        if marker.get('exitcode') != 0 or marker.get('out-data', '').strip() != 'forgedesktop-daily-test':
            raise ValueError('refusing execution outside the marked disposable test guest')
        result = guest.execute(args.command, args.timeout)
        print(json.dumps(result, ensure_ascii=False))
        return result.get('exitcode', 1)
    finally:
        guest.close()


if __name__ == '__main__':
    raise SystemExit(main())
