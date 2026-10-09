"""Explicit Ubuntu artifact identity, isolated from unchanged Arch contract."""
import hashlib
import json
from pathlib import Path
import unittest

from tools.build_plasma_bundle import (create_bundle, verify_bundle, validate_dependencies,
                                       UBUNTU_SCRIPT_BYTES)
from tools.tests import test_build_plasma_bundle as arch_tests


class UbuntuBundleTests(unittest.TestCase):
    # Reuse staging setup only; the Arch suite remains its own compatibility gate.
    def build(self):
        return create_bundle(self.stage, self.output, '0.2.0', 'a' * 40,
                             profile='ubuntu-26.04')

    def setUp(self):
        arch_tests.PlasmaBundleTests.setUp(self)
        repo = Path(__file__).resolve().parents[2]
        script = self.stage / 'usr/libexec/forge-desktop/forge-kwin-session'
        script.write_bytes((repo / 'plasma/session/forge-kwin-session-ubuntu').read_bytes().replace(b'\r\n', b'\n'))
        helper = self.stage / 'usr/libexec/forge-desktop/ubuntu-desktop'
        helper.write_bytes((repo / 'tools/ubuntu_desktop.py').read_bytes().replace(b'\r\n', b'\n'))
        helper.chmod(0o755)
        dep = self.stage / 'usr/share/forge-desktop/plasma/dependencies.json'
        self.inventory = {'schemaVersion': 2, 'runtimeProfile': 'ubuntu-26.04',
                          'runtimePackages': sorted(['fcitx5', 'fcitx5-chinese-addons',
                              'fcitx5-frontend-gtk3', 'fcitx5-frontend-qt6',
                              'kwin-wayland', 'plasma-workspace', 'python3', 'libkf6service-bin']),
                          'assetLicenses': {'usr/libexec/forge-desktop/ubuntu-desktop': 'MIT'}}
        dep.write_text(json.dumps(self.inventory))

    def test_ubuntu_round_trip_requires_explicit_profile_and_distinct_schema(self):
        with self.assertRaises(ValueError):
            create_bundle(self.stage, self.output, '0.2.0', 'a' * 40)
        receipt = verify_bundle(self.output, self.build())
        self.assertEqual(receipt['schemaVersion'], 2)
        self.assertEqual(receipt['runtimeProfile'], 'ubuntu-26.04')
        self.assertNotIn('archSnapshot', receipt)

    def test_repository_ubuntu_profile_is_closed_with_reviewed_helper_and_script(self):
        repo = Path(__file__).resolve().parents[2]
        inventory = validate_dependencies((repo / 'plasma/dependencies-ubuntu.json').read_bytes(),
                                           'ubuntu-26.04')
        self.assertEqual(inventory['runtimeProfile'], 'ubuntu-26.04')
        self.assertEqual((repo / 'plasma/session/forge-kwin-session-ubuntu').read_bytes().replace(b'\r\n', b'\n'),
                         UBUNTU_SCRIPT_BYTES)
        self.assertEqual(inventory['assetLicenses']['usr/libexec/forge-desktop/ubuntu-desktop'], 'MIT')

    def test_complete_repository_ubuntu_assets_build_and_verify(self):
        repo = Path(__file__).resolve().parents[2]
        inventory = json.loads((repo / 'plasma/dependencies-ubuntu.json').read_bytes())
        explicit = {
            'usr/libexec/forge-desktop/forge_provider_contract.py': 'tools/forge_provider_contract.py',
            'usr/libexec/forge-desktop/compatforge-provider-lock-v1.json': 'tools/compatforge-provider-lock-v1.json',
            'usr/share/plasma/look-and-feel/org.forge.desktop/contents/layouts/org.kde.plasma.desktop-layout.js':
                'plasma/look-and-feel-ubuntu/contents/layouts/org.kde.plasma.desktop-layout.js',
            'usr/libexec/forge-desktop/ubuntu-desktop': 'tools/ubuntu_desktop.py',
            'usr/libexec/forge-desktop/compatforge-desktop-sync': 'tools/compatforge_desktop.py',
            'usr/lib/systemd/user/forge-compatforge-desktop-sync.service':
                'services/compatforge/forge-compatforge-desktop-sync.service',
            'usr/lib/systemd/user/forge-compatforge-desktop-sync.timer':
                'services/compatforge/forge-compatforge-desktop-sync.timer'}
        prefixes = {
            'usr/share/plasma/look-and-feel/org.forge.desktop/': 'plasma/look-and-feel/',
            'usr/share/plasma/plasmoids/': 'plasma/plasmoids/',
            'usr/share/aurorae/themes/': 'plasma/aurorae/'}
        for target in inventory['assetLicenses']:
            source = explicit.get(target)
            if source is None:
                source = next(replacement + target[len(prefix):]
                              for prefix, replacement in prefixes.items() if target.startswith(prefix))
            path = self.stage / target
            path.parent.mkdir(parents=True, exist_ok=True)
            data = (repo / source).read_bytes()
            # Preserve binary message catalogs; normalize text checkout endings.
            path.write_bytes(data if source.endswith('.mo') else data.replace(b'\r\n', b'\n'))
            path.chmod(0o755 if target in ('usr/libexec/forge-desktop/compatforge-desktop-sync',
                                         'usr/libexec/forge-desktop/ubuntu-desktop') else 0o644)
        (self.stage / 'usr/share/forge-desktop/plasma/dependencies.json').write_text(json.dumps(inventory))
        receipt = verify_bundle(self.output, self.build())
        self.assertEqual(set(receipt['files']), set(self.files) | set(inventory['assetLicenses']))

    def test_reject_unknown_profile_and_mixed_inventory(self):
        with self.assertRaises(ValueError):
            create_bundle(self.stage, self.output, '0.2.0', 'a' * 40, profile='other')
        self.inventory['archSnapshot'] = '2026/08/01'
        (self.stage / 'usr/share/forge-desktop/plasma/dependencies.json').write_text(json.dumps(self.inventory))
        with self.assertRaises(ValueError):
            self.build()

    def test_reject_missing_helper_and_noncanonical_ubuntu_script(self):
        helper = self.stage / 'usr/libexec/forge-desktop/ubuntu-desktop'
        original = helper.read_bytes()
        helper.unlink()
        with self.assertRaises(ValueError):
            self.build()
        helper.write_bytes(original)
        helper.chmod(0o755)
        script = self.stage / 'usr/libexec/forge-desktop/forge-kwin-session'
        script.write_bytes(script.read_bytes() + b'exec /bin/sh\n')
        with self.assertRaises(ValueError):
            self.build()

    def test_ubuntu_cannot_be_relabelled_as_arch_even_with_new_receipt_digest(self):
        self.build()
        path = self.output / 'bundle.json'
        value = json.loads(path.read_bytes())
        value.pop('runtimeProfile')
        value.update(schemaVersion=1, archSnapshot='2026/08/01')
        raw = (json.dumps(value, sort_keys=True, separators=(',', ':')) + '\n').encode()
        path.write_bytes(raw)
        with self.assertRaises(ValueError):
            verify_bundle(self.output, hashlib.sha256(raw).hexdigest())
