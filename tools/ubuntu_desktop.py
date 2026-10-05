#!/usr/bin/env python3
"""Ordinary-user Ubuntu Plasma session paths and upstream launcher cache refresh.

Application discovery/launching stays in KDE; this helper never parses Exec
metadata, rewrites vendor desktop entries, or changes user settings.
"""

import os
from pathlib import Path, PurePosixPath
import subprocess
import sys

HELPERS = ('/usr/lib/x86_64-linux-gnu/libexec/plasma-dbus-run-session-if-needed',
           '/usr/libexec/plasma-dbus-run-session-if-needed',
           '/usr/lib/plasma-dbus-run-session-if-needed')
REFRESH_COMMAND = ['/usr/bin/kbuildsycoca6', '--noincremental']


def utf8_size(value):
    try:
        return len(value.encode('utf-8', errors='strict'))
    except UnicodeError as error:
        raise ValueError('XDG data path is not valid UTF-8') from error


def data_path(value):
    if (not isinstance(value, str) or not 1 <= len(value) <= 4096
            or utf8_size(value) > 4096
            or not value.startswith('/') or ':' in value
            or any(ord(char) < 32 or ord(char) == 127 for char in value)
            or any(part in ('.', '..') for part in value.split('/'))):
        raise ValueError('invalid XDG data path')
    return str(PurePosixPath(value))


def session_environment(source, home):
    result = dict(source)
    home = data_path(str(home))
    data_home = data_path(source.get('XDG_DATA_HOME') or home + '/.local/share')
    raw_dirs = source.get('XDG_DATA_DIRS') or '/usr/local/share:/usr/share'
    if len(raw_dirs) > 16384 or utf8_size(raw_dirs) > 16384 or len(raw_dirs.split(':')) > 64:
        raise ValueError('XDG data search path exceeds limit')
    dirs = [data_path(value) for value in raw_dirs.split(':')]
    # Preserve custom priority while always discovering normal .deb launchers
    # and exports, including before the first Flatpak or Snap package exists.
    dirs += ['/usr/local/share', '/usr/share', data_home + '/flatpak/exports/share',
             '/var/lib/flatpak/exports/share', '/var/lib/snapd/desktop']
    dirs = list(dict.fromkeys(data_path(value) for value in dirs))
    encoded_dirs = ':'.join(dirs)
    if len(dirs) > 64 or utf8_size(encoded_dirs) > 16384:
        raise ValueError('expanded XDG data search path exceeds limit')
    result.update(XDG_DATA_HOME=data_home, XDG_DATA_DIRS=encoded_dirs,
                  QT_QUICK_BACKEND='software', XMODIFIERS='@im=fcitx')
    return result


def session_command(executable=None):
    executable = executable or (lambda path: os.path.isfile(path) and os.access(path, os.X_OK))
    for helper in HELPERS:
        if executable(helper):
            return [helper, '/usr/bin/startplasma-wayland']
    raise ValueError('supported upstream Plasma session helper missing')


def validate_invocation(args, uid):
    if uid == 0 or args not in (['session'], ['refresh']):
        raise ValueError('requires ordinary user and exactly session or refresh')


def main():
    if os.name != 'posix':
        raise ValueError('requires Linux desktop session')
    validate_invocation(sys.argv[1:], os.geteuid())
    env = session_environment(os.environ, Path.home())
    if sys.argv[1] == 'session':
        command = session_command()
        os.execve(command[0], command, env)
    else:
        # Full rebuild removes deleted launchers too; kded normally monitors
        # these same directories automatically during a Plasma session.
        subprocess.run(REFRESH_COMMAND, env=env, check=True, timeout=30,
                       stdin=subprocess.DEVNULL, stdout=subprocess.DEVNULL,
                       stderr=subprocess.DEVNULL, close_fds=True)


if __name__ == '__main__':
    try:
        main()
    except (ValueError, OSError, subprocess.SubprocessError) as error:
        print('ForgeDesktop: ' + str(error), file=sys.stderr)
        raise SystemExit(1)
