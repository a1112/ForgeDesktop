"""Ubuntu session paths and cache refresh without metadata execution."""

import unittest
from pathlib import PurePosixPath

from tools import ubuntu_desktop as desktop


class UbuntuDesktopTests(unittest.TestCase):
    def test_default_paths_include_all_native_exports_without_requiring_install(self):
        env = desktop.session_environment({}, PurePosixPath('/home/forge'))
        self.assertEqual(env['XDG_DATA_HOME'], '/home/forge/.local/share')
        self.assertEqual(env['XDG_DATA_DIRS'].split(':'), [
            '/usr/local/share', '/usr/share',
            '/home/forge/.local/share/flatpak/exports/share',
            '/var/lib/flatpak/exports/share', '/var/lib/snapd/desktop'])
        self.assertEqual(env['QT_QUICK_BACKEND'], 'software')

    def test_preserve_custom_data_home_and_path_order_deduplicate(self):
        source = {'XDG_DATA_HOME': '/home/forge/data space',
                  'XDG_DATA_DIRS': '/opt/shared:/usr/share:/opt/shared', 'LANG': 'zh_CN.UTF-8'}
        result = desktop.session_environment(source, PurePosixPath('/home/forge'))
        self.assertEqual(result['LANG'], source['LANG'])
        self.assertEqual(result['XDG_DATA_DIRS'].split(':')[:2], ['/opt/shared', '/usr/share'])
        self.assertIn('/home/forge/data space/flatpak/exports/share', result['XDG_DATA_DIRS'])
        self.assertEqual(source['XDG_DATA_DIRS'], '/opt/shared:/usr/share:/opt/shared')

    def test_custom_paths_retain_priority_and_include_deb_system_launchers(self):
        result = desktop.session_environment({'XDG_DATA_DIRS': '/opt/shared'},
                                             PurePosixPath('/home/forge'))
        self.assertEqual(result['XDG_DATA_DIRS'].split(':'), [
            '/opt/shared', '/usr/local/share', '/usr/share',
            '/home/forge/.local/share/flatpak/exports/share',
            '/var/lib/flatpak/exports/share', '/var/lib/snapd/desktop'])

    def test_final_expanded_paths_must_fit_count_and_byte_limits(self):
        for raw in (':'.join('/opt/d' + str(index) for index in range(64)),
                    ':'.join('/' + str(index) + 'a' * 4078 for index in range(4))):
            with self.subTest(raw_length=len(raw)):
                with self.assertRaises(ValueError):
                    desktop.session_environment({'XDG_DATA_DIRS': raw},
                                                 PurePosixPath('/home/forge'))

    def test_generated_user_export_must_fit_individual_path_limit(self):
        with self.assertRaises(ValueError):
            desktop.session_environment({'XDG_DATA_HOME': '/' + 'a' * 4095},
                                         PurePosixPath('/home/forge'))

    def test_reject_relative_control_ambiguous_and_unbounded_environment(self):
        for values in ({'XDG_DATA_DIRS': 'relative'}, {'XDG_DATA_DIRS': '/usr/share::/tmp'},
                       {'XDG_DATA_HOME': '/home/forge:data'}, {'XDG_DATA_HOME': '/home/../other'},
                       {'XDG_DATA_DIRS': '/tmp\nwhoami'},
                       {'XDG_DATA_DIRS': '/a' * 3000}):
            with self.subTest(values=values):
                with self.assertRaises(ValueError):
                    desktop.session_environment(values, PurePosixPath('/home/forge'))

    def test_upstream_commands_are_fixed_and_select_known_distro_helper(self):
        self.assertEqual(desktop.session_command(lambda p: p == '/usr/libexec/plasma-dbus-run-session-if-needed'),
                         ['/usr/libexec/plasma-dbus-run-session-if-needed', '/usr/bin/startplasma-wayland'])
        self.assertEqual(desktop.session_command(lambda p: p == '/usr/lib/plasma-dbus-run-session-if-needed'),
                         ['/usr/lib/plasma-dbus-run-session-if-needed', '/usr/bin/startplasma-wayland'])
        with self.assertRaises(ValueError):
            desktop.session_command(lambda p: False)
        self.assertEqual(desktop.REFRESH_COMMAND, ['/usr/bin/kbuildsycoca6', '--noincremental'])

    def test_root_or_unknown_action_cannot_start_or_refresh_session(self):
        for args, uid in ((['session'], 0), (['refresh'], 0), (['install', 'evil'], 1000), ([], 1000)):
            with self.subTest(args=args, uid=uid):
                with self.assertRaises(ValueError):
                    desktop.validate_invocation(args, uid)


if __name__ == '__main__':
    unittest.main()
