"""Production promotion requires staging evidence and an unchanged release."""
import hashlib
import importlib.util
import json
import os
import unittest
from pathlib import Path
from unittest.mock import patch

SPEC = importlib.util.spec_from_file_location('production_gate', Path(__file__).with_name('jenkins-release.py'))
GATE = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(GATE)
SHA = 'a' * 40
MANIFEST = json.dumps({'commit': SHA, 'images': {'frontend': 'tested-image'}}).encode()
READY = {
    'RELEASE_SHA': SHA,
    'STAGING_DEPLOYMENT_STATUS': 'VERIFIED',
    'STAGING_RELEASE_HASH': hashlib.sha256(MANIFEST).hexdigest(),
}
CONFIG = {
    'PRODUCTION_CLUSTER': 'production', 'PRODUCTION_FRONTEND_SERVICE': 'frontend',
    'PRODUCTION_BACKEND_SERVICE': 'backend', 'PRODUCTION_URL': 'https://production.example.com',
    'PRODUCTION_APPROVERS': 'release-managers', 'STAGING_CLUSTER': 'staging',
    'STAGING_URL': 'https://staging.example.com',
}


class ProductionGateTest(unittest.TestCase):
    def check_ready(self, settings, manifest=MANIFEST):
        with patch.dict(os.environ, settings, clear=True), patch('sys.argv', ['script', 'production-ready']), \
                patch.object(GATE, 'Path') as path, patch.object(GATE, 'aws') as aws:
            path.return_value.read_bytes.return_value = manifest
            GATE.main()
            aws.assert_not_called()

    def check_config(self, settings):
        with patch.dict(os.environ, settings, clear=True), patch('sys.argv', ['script', 'production-config']):
            GATE.main()

    def test_unchanged_staging_release_can_be_promoted(self):
        self.check_ready(READY)

    def test_staging_failure_blocks_promotion(self):
        with self.assertRaisesRegex(SystemExit, 'successful staging'):
            self.check_ready(dict(READY, STAGING_DEPLOYMENT_STATUS='FAILED_OR_ABORTED'))

    def test_missing_staging_evidence_blocks_promotion(self):
        with self.assertRaisesRegex(SystemExit, 'successful staging'):
            self.check_ready({'RELEASE_SHA': SHA})

    def test_changed_manifest_blocks_promotion(self):
        with self.assertRaisesRegex(SystemExit, 'manifest changed'):
            self.check_ready(READY, MANIFEST + b' ')

    def test_wrong_commit_blocks_promotion_even_when_hash_matches(self):
        with self.assertRaisesRegex(SystemExit, 'commit mismatch'):
            self.check_ready(dict(READY, RELEASE_SHA='b' * 40))

    def test_valid_production_settings(self):
        self.check_config(CONFIG)

    def test_missing_production_approvers_fail_closed(self):
        with self.assertRaisesRegex(SystemExit, 'PRODUCTION_APPROVERS'):
            self.check_config(dict(CONFIG, PRODUCTION_APPROVERS=''))

    def test_empty_approver_list_fails_closed(self):
        with self.assertRaisesRegex(SystemExit, 'at least one'):
            self.check_config(dict(CONFIG, PRODUCTION_APPROVERS=' , '))

    def test_staging_cluster_cannot_be_production_target(self):
        with self.assertRaisesRegex(SystemExit, 'separate ECS cluster'):
            self.check_config(dict(CONFIG, PRODUCTION_CLUSTER='staging'))

    def test_staging_url_cannot_be_production_target(self):
        with self.assertRaisesRegex(SystemExit, 'separate URL'):
            self.check_config(dict(CONFIG, PRODUCTION_URL=CONFIG['STAGING_URL'] + '/'))

    def test_production_requires_https(self):
        with self.assertRaisesRegex(SystemExit, 'HTTPS'):
            self.check_config(dict(CONFIG, PRODUCTION_URL='http://production.example.com'))


if __name__ == '__main__':
    unittest.main()
