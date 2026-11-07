"""Independent production gate keeps commit, manifest and immutable scan validation."""
import hashlib
import importlib.util
import json
import os
import unittest
from pathlib import Path
from unittest.mock import patch

SPEC = importlib.util.spec_from_file_location('production_only_gate', Path(__file__).with_name('production-only-ready.py'))
GATE = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(GATE)
SHA = 'a' * 40
MANIFEST = json.dumps({'commit': SHA, 'images': {}}).encode()


class ProductionOnlyGateTest(unittest.TestCase):
    def check(self, manifest=MANIFEST, sha=SHA, release_hash=None):
        settings = {'RELEASE_SHA': sha, 'PRODUCTION_RELEASE_HASH': (
            hashlib.sha256(MANIFEST).hexdigest() if release_hash is None else release_hash)}
        with patch.dict(os.environ, settings, clear=True), patch.object(GATE, 'Path') as path:
            path.return_value.read_bytes.return_value = manifest
            GATE.check_ready()

    def test_no_staging_required_but_images_and_scans_must_validate(self):
        with patch.object(GATE.RELEASE, 'verify_reused_release') as verify:
            self.check()
            verify.assert_called_once_with(json.loads(MANIFEST), SHA)

    def test_changed_manifest_fails_before_aws(self):
        with patch.object(GATE.RELEASE, 'verify_reused_release') as verify:
            with self.assertRaisesRegex(SystemExit, 'manifest changed'):
                self.check(manifest=MANIFEST + b' ')
            verify.assert_not_called()

    def test_missing_hash_fails_closed(self):
        with patch.object(GATE.RELEASE, 'verify_reused_release') as verify:
            with self.assertRaisesRegex(SystemExit, 'manifest changed'):
                self.check(release_hash='')
            verify.assert_not_called()

    def test_wrong_commit_fails_before_aws(self):
        with patch.object(GATE.RELEASE, 'verify_reused_release') as verify:
            with self.assertRaisesRegex(SystemExit, 'commit mismatch'):
                self.check(sha='b' * 40)
            verify.assert_not_called()

    def test_scan_or_digest_failure_blocks_release(self):
        with patch.object(GATE.RELEASE, 'verify_reused_release', side_effect=SystemExit('scan blocked')), \
                self.assertRaisesRegex(SystemExit, 'scan blocked'):
            self.check()


if __name__ == '__main__':
    unittest.main()
