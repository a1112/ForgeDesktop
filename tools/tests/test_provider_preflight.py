"""Synthetic CLI tests: rejected providers cannot export or edit launchers."""
import copy
import json
import os
from pathlib import Path
import sys
import tempfile
import unittest
from unittest import mock

from tools import compatforge_desktop as desktop
from tools import forge_provider_contract as contract


class ProviderPreflightTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.trace = self.root / "trace"
        self.client = self.root / "compatforge-cli"
        self.requirements = json.loads(desktop.PROVIDER_LOCK.read_bytes())
        self.report = dict(self.requirements, sourceDirty=False)
        self.script = ("#!" + sys.executable + "\n"
            "import json, pathlib, sys, time\n"
            f"root = pathlib.Path({str(self.root)!r})\n"
            "with (root / 'trace').open('a') as stream: stream.write(sys.argv[1] + '\\n')\n"
            "if sys.argv[1] == 'provider-info':\n"
            "    data = json.loads((root / 'report.json').read_text())\n"
            "    print(json.dumps(data))\n"
            "else: print('{\"schemaVersion\":\"1\",\"entries\":[]}')\n")
        self.client.write_text(self.script)
        self.client.chmod(0o755)
        self.patch = mock.patch.object(desktop, "CLIENT", str(self.client))
        self.patch.start()
        self.addCleanup(self.patch.stop)

    def query(self, value):
        (self.root / "report.json").write_text(json.dumps(value))
        return desktop.query_export()

    def test_matching_provider_queries_export(self):
        self.assertEqual(self.query(self.report), {"schemaVersion": "1", "entries": []})
        self.assertEqual(self.trace.read_text().splitlines(), ["provider-info", "desktop-export"])

    def test_missing_commands_schema_and_version_fail_before_export_and_filesystem(self):
        cases = [("commands", {}, "capability-missing"),
                 ("schemas", {"desktop-export": "2"}, "schema-mismatch"),
                 ("providerVersion", "0.13.0", "unsupported-version"),
                 ("contractVersion", "2.0.0", "unsupported-version"),
                 ("sourceCommit", "f" * 40, "source-mismatch"),
                 ("sourceDirty", True, "source-mismatch")]
        for field, value, code in cases:
            with self.subTest(field=field):
                self.trace.unlink(missing_ok=True)
                report = copy.deepcopy(self.report)
                report[field] = value
                with self.assertRaises(contract.ContractError) as caught:
                    desktop.reconcile(self.query(report), self.root / "apps", self.root / "state")
                self.assertEqual(caught.exception.code, code)
                self.assertEqual(self.trace.read_text().splitlines(), ["provider-info"])
                self.assertFalse((self.root / "apps").exists())
                self.assertFalse((self.root / "state").exists())

    def test_old_cli_rejects_provider_info_without_trying_export(self):
        self.client.write_text(self.script.split("if sys.argv")[0] + "sys.exit(2)\n")
        with self.assertRaisesRegex(contract.ContractError, "provider-unavailable"):
            desktop.query_export()
        self.assertEqual(self.trace.read_text().splitlines(), ["provider-info"])

    def test_malformed_duplicate_oversized_and_timed_out_reports_fail_closed(self):
        for output in ("{bad", '{"schemaVersion":"1","schemaVersion":"1"}', "x" * 65537):
            self.client.write_text("#!" + sys.executable + "\nprint(" + repr(output) + ")\n")
            with self.assertRaisesRegex(contract.ContractError, "schema-mismatch"):
                desktop.query_export()
        self.client.write_text("#!" + sys.executable + "\nimport time\ntime.sleep(2)\n")
        with mock.patch.object(contract, "PROBE_TIMEOUT", 0.05):
            with self.assertRaisesRegex(contract.ContractError, "provider-unavailable"):
                desktop.query_export()

    def test_shared_vectors_match_adapter_errors(self):
        vectors = json.loads((Path(__file__).parents[2] / "contracts/provider-vectors-v1.json").read_bytes())
        for case in vectors["cases"]:
            report = copy.deepcopy(vectors["report"])
            report[case["field"]] = case["value"]
            with self.subTest(case=case["name"]):
                with self.assertRaises(contract.ContractError) as caught:
                    contract.negotiate(report, vectors["requirements"])
                self.assertEqual(caught.exception.code, case["code"])

    def test_public_interop_v1_adapter_preserves_error_families(self):
        for domain, public in [("provider-unavailable", "CAPABILITY_UNAVAILABLE"),
                               ("capability-missing", "CAPABILITY_UNAVAILABLE"),
                               ("schema-mismatch", "SCHEMA_INVALID"),
                               ("unsupported-version", "UNSUPPORTED_VERSION"),
                               ("source-mismatch", "BINDING_MISMATCH")]:
            self.assertEqual(contract.ContractError(domain, "detail").public_code, public)


if __name__ == "__main__":
    unittest.main()
