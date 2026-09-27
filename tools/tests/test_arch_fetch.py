import importlib.util
from pathlib import Path
import tempfile
import unittest

SPEC = importlib.util.spec_from_file_location('fetch_arch', Path(__file__).parents[1] / 'fetch_arch_packages.py')
fetch = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(fetch)


class ArchiveFetchTests(unittest.TestCase):
    def test_only_exact_archive_snapshot_and_package_names(self):
        good = 'https://archive.archlinux.org/repos/2026/08/01/core/os/x86_64/gcc-1-1-x86_64.pkg.tar.zst'
        self.assertEqual(fetch.archive_filename(good), 'gcc-1-1-x86_64.pkg.tar.zst')
        for bad in (good.replace('https:', 'http:'), good.replace('/08/01/', '/08/02/'),
                    good.replace('gcc-1', '../gcc-1'), good + '?other',
                    good.replace('archive.archlinux.org', 'example.org')):
            with self.subTest(url=bad), self.assertRaises(ValueError):
                fetch.archive_filename(bad)

    def test_rejects_corrupt_cached_package(self):
        with tempfile.TemporaryDirectory() as root:
            path = Path(root) / 'package'
            path.write_bytes(b'bad')
            self.assertFalse(fetch.valid_file(path, 3, '0' * 64))
            self.assertFalse(fetch.valid_file(path, 4, '0' * 64))
            self.assertFalse(fetch.valid_file(Path(root) / 'missing', 3, '0' * 64))


if __name__ == '__main__':
    unittest.main()
