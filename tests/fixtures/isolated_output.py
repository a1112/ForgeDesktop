#!/usr/bin/env python3
"""Change only head 1's virtual connector in the marked disposable QEMU VM.

Uses QEMU's RFB SetDesktopSize hardware notification, never keyboard/pointer
events. QEMU 10.2.1 maps a zero size to virtio-gpu connector removal. This is
test infrastructure, not a desktop display-settings implementation.
"""
import argparse
import json
import os
from pathlib import Path
import socket
import stat
import struct
import time

from isolated_guest import Guest

LAB = Path('/srv/forge-desktop-build/daily-test-vm')


def receive(connection, length):
    result = bytearray()
    while len(result) < length:
        chunk = connection.recv(length - len(result))
        if not chunk:
            raise RuntimeError('RFB connection ended early')
        result.extend(chunk)
    return bytes(result)


def resize(width, height):
    if (width, height) != (0, 0) and not (640 <= width <= 3840 and 480 <= height <= 2160):
        raise ValueError('Use 0x0 removal or a bounded display mode')
    directory = LAB.lstat()
    endpoint = LAB / 'vnc-head1.sock'
    entry = endpoint.lstat()
    if (not stat.S_ISDIR(directory.st_mode) or directory.st_uid != os.getuid()
            or directory.st_mode & 0o077 or not stat.S_ISSOCK(entry.st_mode)
            or entry.st_uid != os.getuid()):
        raise RuntimeError('Expected owner-only lab directory and owned socket')
    with socket.socket(socket.AF_UNIX, socket.SOCK_STREAM) as connection:
        connection.settimeout(5)
        connection.connect(str(endpoint))
        if receive(connection, 12) != b'RFB 003.008\n':
            raise RuntimeError('Expected QEMU RFB 3.8')
        connection.sendall(b'RFB 003.008\n')
        count = receive(connection, 1)[0]
        if not 1 <= count <= 32 or 1 not in receive(connection, count):
            raise RuntimeError('Expected local-socket security type')
        connection.sendall(b'\x01')
        if receive(connection, 4) != b'\x00' * 4:
            raise RuntimeError('RFB negotiation rejected')
        connection.sendall(b'\x01')  # Shared client, preserve viewer connections.
        header = receive(connection, 24)
        name_length = struct.unpack('!I', header[20:24])[0]
        if name_length > 1024:
            raise RuntimeError('Unbounded RFB server name')
        if receive(connection, name_length) != b'QEMU (forgedesktop-daily-test)':
            raise RuntimeError('Refusing a different virtual machine')
        message = struct.pack('!BBHHBBIHHHHI', 251, 0, width, height, 1, 0,
                              0, 0, 0, width, height, 0)
        connection.sendall(message)
        # Keep the connection alive while QEMU forwards its debounced UI info.
        time.sleep(1)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('width', type=int)
    parser.add_argument('height', type=int)
    args = parser.parse_args()
    guest = Guest()
    try:
        marker = guest.execute(['/usr/bin/cat', '/etc/forgedesktop-isolated-test'])
        if marker.get('exitcode') != 0 or marker.get('out-data', '').strip() != 'forgedesktop-daily-test':
            raise RuntimeError('Guest marker mismatch')
        resize(args.width, args.height)
        result = guest.execute(['/usr/bin/python3', '-c',
            "from pathlib import Path; import json; "
            "print(json.dumps({str(p):p.read_text().strip() for p in "
            "Path('/sys/class/drm').glob('card*-*/status')}))"])
        if result.get('exitcode') != 0 or result.get('out-truncated'):
            raise RuntimeError('Guest connector observation failed')
        print(json.dumps({'requested': [args.width, args.height],
                          'connectors': json.loads(result['out-data'])}, indent=2))
    finally:
        guest.close()


if __name__ == '__main__':
    main()
