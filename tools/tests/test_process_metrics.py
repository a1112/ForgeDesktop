import importlib.util
from pathlib import Path
import tempfile
import unittest

SPEC = importlib.util.spec_from_file_location('process_metrics', Path(__file__).parents[1] / 'process_metrics.py')
metrics = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(metrics)


class ProcessMetricsTests(unittest.TestCase):
    def test_stat_with_parentheses_and_spaces_in_name(self):
        fields = ['S', '1'] + ['0'] * 9 + ['12', '8'] + ['0'] * 6 + ['500']
        self.assertEqual(metrics.parse_stat('42 (worker (child)) ' + ' '.join(fields)),
                         {'pid': 42, 'name': 'worker (child)', 'ppid': 1, 'ticks': 20, 'start': 500})

    def test_pid_reuse_does_not_count_as_cpu_delta(self):
        old = {12: {'start': 2, 'ticks': 900}}
        new = {12: {'start': 3, 'ticks': 1100}}
        self.assertEqual(metrics.cpu_percent(old, new, 100, 10), 0)

    def test_cpu_is_percent_of_one_core(self):
        old = {12: {'start': 2, 'ticks': 100}, 13: {'start': 3, 'ticks': 400}}
        new = {12: {'start': 2, 'ticks': 125}, 13: {'start': 3, 'ticks': 425}}
        self.assertEqual(metrics.cpu_percent(old, new, 100, 10), 5)

    def test_pss_does_not_accidentally_sum_private_or_rss(self):
        self.assertEqual(metrics.parse_pss('Rss: 200 kB\nPss: 100 kB\nPrivate_Dirty: 70 kB\n'), 100)
        self.assertIsNone(metrics.parse_pss('Rss: 200 kB\n'))

    def test_group_includes_descendants_and_excludes_other_users(self):
        table = {
            10: {'ppid': 1, 'name': 'r-os-desktop', 'uid': 1000},
            11: {'ppid': 10, 'name': 'WebKitWebProcess', 'uid': 1000},
            12: {'ppid': 11, 'name': 'helper', 'uid': 1000},
            13: {'ppid': 10, 'name': 'other', 'uid': 1001},
            14: {'ppid': 1, 'name': 'other', 'uid': 1000},
        }
        self.assertEqual(metrics.select_group(table, {'r-os-desktop'}, 1000), {10, 11, 12})

    def test_missing_process_is_skipped(self):
        with tempfile.TemporaryDirectory() as directory:
            Path(directory, '77').mkdir()
            self.assertEqual(metrics.read_processes(Path(directory)), {})


if __name__ == '__main__':
    unittest.main()
