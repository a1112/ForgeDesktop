import importlib.util
from pathlib import Path
import unittest

PATH = Path(__file__).resolve().parents[1] / 'performance_report.py'


class PerformanceReportTests(unittest.TestCase):
    def setUp(self):
        self.assertTrue(PATH.exists(), 'performance reporter missing')
        spec = importlib.util.spec_from_file_location('performance_report', PATH)
        self.api = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(self.api)

    def test_p95_uses_nearest_rank_not_mean(self):
        values = [1] * 94 + [50] * 6
        self.assertEqual(self.api.distribution(values)['p95_ms'], 50)

    def test_rejects_empty_nonfinite_and_negative_timings(self):
        for values in ([], [float('nan')], [float('inf')], [-1]):
            with self.subTest(values=values), self.assertRaises(ValueError):
                self.api.distribution(values)

    def test_frame_results_separate_actual_damage_from_empty_attempts(self):
        result = self.api.frames('kind,elapsed_us,damaged\nframe,20000,1\nframe,100,0\n')
        self.assertEqual(result['damaged_frames']['p95_ms'], 20)
        self.assertEqual(result['undamaged_attempts']['p95_ms'], .1)
        self.assertFalse(result['enough_samples_for_gate'])
        with self.assertRaises(ValueError):
            self.api.frames('kind,elapsed_us\nframe,20\n')

    def test_missing_or_one_sided_launcher_samples_do_not_pass(self):
        result = self.api.launcher('ForgeDesktop launcher-submit-us=100\n')
        self.assertIsNone(result['compositor_submission'])
        self.assertFalse(result['enough_samples_for_gate'])

    def test_unstable_short_or_incomplete_process_capture_is_not_qualified(self):
        capture = {'schemaVersion':1, 'duration_seconds':60, 'uid':1000,
                   'selection':{'desktop':{'names':['forge-compositor','forge-shell'], 'descendants':False}},
                   'summary':{'desktop':{'stable_process_set':True, 'complete_pss':True,
                     'cpu_percent_one_core':1, 'pss_mib_max':90, 'pss_mib_mean':89}}}
        self.assertTrue(self.api.processes(capture)['qualified'])
        for field in ('stable_process_set', 'complete_pss'):
            capture['summary']['desktop'][field] = False
            self.assertFalse(self.api.processes(capture)['qualified'])
            capture['summary']['desktop'][field] = True
        capture['duration_seconds'] = 59
        self.assertFalse(self.api.processes(capture)['qualified'])
        capture['duration_seconds'] = float('inf')
        self.assertFalse(self.api.processes(capture)['qualified'])
        capture['duration_seconds'] = 60
        capture['selection']['desktop']['descendants'] = True
        self.assertFalse(self.api.processes(capture)['qualified'])

    def test_novnc_timeout_is_retained_and_prevents_qualification(self):
        capture = {'schemaVersion':1, 'metric':'pointer-down-to-first-roi-pixel-change',
                   'observations':[{'case':'open','outcome':'changed','elapsedMs':20}]*30}
        self.assertTrue(self.api.novnc(capture)['enough_valid_samples'])
        capture['observations'].append({'case':'open','outcome':'timeout','elapsedMs':3000})
        result = self.api.novnc(capture)
        self.assertFalse(result['enough_valid_samples'])
        self.assertEqual(result['failures'], {'timeout':1})


if __name__ == '__main__':
    unittest.main()
