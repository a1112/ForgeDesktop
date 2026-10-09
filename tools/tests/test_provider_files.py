"""Raw protocol bytes and descriptor-bound reads, without a live provider."""
import json
import os
from pathlib import Path
import tempfile
import unittest
from unittest import mock

from tools import forge_provider_contract as contract


class ProviderFileTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.lock = self.root / "lock.json"
        self.lock.write_bytes((Path(__file__).parents[1] / "compatforge-provider-lock-v1.json").read_bytes())

    def test_lock_rejects_symlink_hardlink_fifo_and_linked_parent(self):
        link = self.root / "link"
        link.symlink_to(self.lock)
        hardlink = self.root / "hard"
        os.link(self.lock, hardlink)
        fifo = self.root / "fifo"
        os.mkfifo(fifo)
        parent = self.root / "linked-parent"
        parent.symlink_to(self.root, target_is_directory=True)
        for path in (link, hardlink, fifo, parent / "lock.json"):
            with self.subTest(path=path):
                with self.assertRaises(contract.ContractError):
                    contract.load_lock(path)

    def test_open_descriptor_rejects_path_substitution_and_bounds_growth(self):
        raw = self.lock.read_bytes()
        other = self.root / "other"
        other.write_bytes(raw)
        original_read = os.read
        replaced = False
        def swap(fd, count):
            nonlocal replaced
            if not replaced:
                replaced = True
                self.lock.unlink()
                self.lock.symlink_to(other)
            return original_read(fd, count)
        with mock.patch.object(contract.os, "read", swap):
            with self.assertRaises(contract.ContractError):
                contract.load_lock(self.lock)
        self.lock.unlink()
        self.lock.write_bytes(b"data")
        allocated = []
        def grow(fd, count):
            self.lock.write_bytes(b"x" * 65537)
            data = original_read(fd, count)
            allocated.append(len(data))
            return data
        with mock.patch.object(contract.os, "read", grow):
            with self.assertRaises(contract.ContractError):
                contract.read_regular_bytes(self.lock, 4)
        self.assertLessEqual(sum(allocated), 5)

    def test_utf8_only_and_shared_raw_vectors(self):
        value = dict(json.loads(self.lock.read_bytes()), sourceDirty=False)
        text = json.dumps(value)
        contract.decode(text.encode("utf-8"), report=True)
        for encoding in ("utf-16", "utf-16-le", "utf-16-be", "utf-32", "utf-32-le", "utf-32-be"):
            with self.subTest(encoding=encoding):
                with self.assertRaisesRegex(contract.ContractError, "schema-mismatch"):
                    contract.decode(text.encode(encoding), report=True)
        vectors = json.loads((Path(__file__).parents[2] / "contracts/provider-raw-vectors-v1.json").read_bytes())
        for case in vectors["cases"]:
            with self.subTest(case=case["name"]):
                raw = bytes.fromhex(case["rawHex"])
                if case["accepted"]:
                    contract.decode(raw, report=True)
                else:
                    with self.assertRaisesRegex(contract.ContractError, "schema-mismatch"):
                        contract.decode(raw, report=True)
