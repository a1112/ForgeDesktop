"""Execute first-login script against the supported Plasma scripting surface."""

import json
from pathlib import Path
import shutil
import subprocess
import tempfile
import unittest

from tools import build_plasma_bundle as bundle


UBUNTU_IDS = ['org.kde.dolphin.desktop', 'org.kde.konsole.desktop',
              'forge-store.desktop', 'systemsettings.desktop']
ARCH_IDS = ['thunar.desktop', 'xfce4-terminal.desktop', 'org.xfce.mousepad.desktop',
            'firefox.desktop', 'systemsettings.desktop']
REPO = Path(__file__).resolve().parents[2]
UBUNTU_LAYOUT = REPO / 'plasma/look-and-feel-ubuntu/contents/layouts/org.kde.plasma.desktop-layout.js'


class UbuntuLayoutTests(unittest.TestCase):
    def test_repository_profile_selects_distinct_first_login_layout(self):
        ubuntu_sources = bundle.repository_asset_sources(REPO, profile='ubuntu-26.04')
        arch_sources = bundle.repository_asset_sources(REPO)
        self.assertEqual(ubuntu_sources[bundle.LOOK_LAYOUT], UBUNTU_LAYOUT)
        self.assertEqual(arch_sources[bundle.LOOK_LAYOUT],
                         REPO / 'plasma/look-and-feel/contents/layouts/org.kde.plasma.desktop-layout.js')
        self.assertEqual(set(ubuntu_sources), set(arch_sources) | {bundle.UBUNTU_HELPER})

    def test_real_repository_staging_keeps_arch_bytes_and_ubuntu_receipt_closed(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            for profile, expected, count in [('ubuntu-26.04', UBUNTU_LAYOUT, 22),
                                              (bundle.ARCH_PROFILE, REPO / 'plasma/look-and-feel/contents/layouts/org.kde.plasma.desktop-layout.js', 21)]:
                stage = root / profile
                bundle.stage_repository_assets(REPO, stage, profile=profile)
                self.assertEqual((stage / bundle.LOOK_LAYOUT).read_bytes(),
                                 expected.read_bytes().replace(b'\r\n', b'\n'))
                output = root / (profile + '-bundle')
                pin = bundle.create_bundle(stage, output, '0.2.1', 'a' * 40, profile=profile)
                self.assertEqual(len(bundle.verify_bundle(output, pin)['files']), count)

    def test_repository_staging_never_replaces_an_existing_directory(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            with self.assertRaises(ValueError):
                bundle.stage_repository_assets(REPO, root, profile='ubuntu-26.04')
            self.assertEqual(list(root.iterdir()), [])

    def execute_layout(self, layout, installed):
        node = shutil.which('node')
        if node is None:
            self.skipTest('Node required for host JavaScript behavioral harness')
        # Fake only the external Plasma objects; execute the whole real script.
        harness = r'''
const vm = require('vm');
const fs = require('fs');
const input = JSON.parse(fs.readFileSync(0, 'utf8'));
const configs = [];
const context = {currentActivity: () => 'test', desktopsForActivity: () => [],
 applicationExists: id => input.installed.includes(id),
 Panel: function() {this.addWidget = id => ({writeConfig: (key,value) =>
   configs.push({widget:id,key:key,value:value})});}};
vm.runInNewContext(input.script, context, {timeout:1000});
console.log(JSON.stringify(configs.filter(x => x.key === 'launchers')));
'''
        result = subprocess.run([node, '-e', harness],
                                input=json.dumps({'script': layout.read_text(), 'installed': installed}),
                                text=True, capture_output=True, timeout=10, check=True)
        records = json.loads(result.stdout)
        self.assertEqual(len(records), 1)
        return records[0]['value'].split(',') if records[0]['value'] else []

    def test_ubuntu_first_login_uses_only_verified_installed_ids(self):
        self.assertEqual(self.execute_layout(UBUNTU_LAYOUT, UBUNTU_IDS),
                         ['applications:' + name for name in UBUNTU_IDS])

    def test_missing_store_or_all_targets_produce_no_broken_pin(self):
        installed = [name for name in UBUNTU_IDS if name != 'forge-store.desktop']
        self.assertEqual(self.execute_layout(UBUNTU_LAYOUT, installed),
                         ['applications:' + name for name in installed])
        self.assertEqual(self.execute_layout(UBUNTU_LAYOUT, []), [])

    def test_arch_first_login_favorites_remain_unchanged(self):
        layout = REPO / 'plasma/look-and-feel/contents/layouts/org.kde.plasma.desktop-layout.js'
        self.assertEqual(self.execute_layout(layout, ARCH_IDS),
                         ['applications:' + name for name in ARCH_IDS])


if __name__ == '__main__':
    unittest.main()
