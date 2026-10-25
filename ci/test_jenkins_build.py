"""Verify publication configuration and fail-closed staging approval settings."""
import importlib.util
import json
import os
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

SPEC = importlib.util.spec_from_file_location('jenkins_build', Path(__file__).with_name('jenkins-release.py'))
BUILD = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(BUILD)
SHA = 'a' * 40
SETTINGS = {'CODEBUILD_PROJECT': 'test-builder', 'REPORT_BUCKET': 'test-reports', 'RELEASE_SHA': SHA}
STAGING = {
    'STAGING_CLUSTER': 'staging', 'STAGING_FRONTEND_SERVICE': 'frontend',
    'STAGING_BACKEND_SERVICE': 'backend', 'STAGING_URL': 'https://staging.example.com',
    'STAGING_APPROVERS': 'release-reviewers',
}


class JenkinsBuildTest(unittest.TestCase):
    def test_publication_requires_no_deployment_parameters(self):
        with patch.dict(os.environ, SETTINGS, clear=True), patch('sys.argv', ['script', 'config']):
            BUILD.main()

    def test_staging_requires_named_approvers(self):
        settings = {key: value for key, value in STAGING.items() if key != 'STAGING_APPROVERS'}
        with patch.dict(os.environ, settings, clear=True), patch('sys.argv', ['script', 'staging-config']), \
                self.assertRaisesRegex(SystemExit, 'STAGING_APPROVERS'):
            BUILD.main()

    def test_valid_staging_configuration(self):
        with patch.dict(os.environ, STAGING, clear=True), patch('sys.argv', ['script', 'staging-config']):
            BUILD.main()

    def test_staging_rejects_plain_http(self):
        with patch.dict(os.environ, dict(STAGING, STAGING_URL='http://staging.example.com'), clear=True), \
                patch('sys.argv', ['script', 'staging-config']), \
                self.assertRaisesRegex(SystemExit, 'HTTPS'):
            BUILD.main()

    def test_success_publishes_exact_sha_without_ecs_calls(self):
        responses = [
            {'build': {'id': 'test-builder:run-id'}},
            {'builds': [{'buildStatus': 'SUCCEEDED', 'resolvedSourceVersion': SHA}]},
            {'builds': [{'buildStatus': 'SUCCEEDED', 'resolvedSourceVersion': SHA}]},
        ]
        with tempfile.TemporaryDirectory() as temp, patch.dict(os.environ, SETTINGS, clear=True), \
                patch.object(BUILD, 'aws', side_effect=responses) as aws, \
                patch.object(BUILD.subprocess, 'run') as run, \
                patch.object(BUILD, 'Path', side_effect=lambda name: Path(temp) / name):
            (Path(temp) / 'release.json').write_text(json.dumps({'commit': SHA, 'images': {}}))
            BUILD.build()
            start = aws.call_args_list[0].args
            self.assertEqual(start[:2], ('codebuild', 'start-build'))
            self.assertEqual(start[start.index('--source-version') + 1], SHA)
            self.assertTrue(all(call.args[0] == 'codebuild' for call in aws.call_args_list))
            self.assertEqual(run.call_count, 2)

    def test_wrong_source_sha_prevents_artifact_download(self):
        with tempfile.TemporaryDirectory() as temp, patch.dict(os.environ, SETTINGS, clear=True), \
                patch.object(BUILD, 'aws', side_effect=[
                    {'build': {'id': 'test-builder:run-id'}},
                    {'builds': [{'buildStatus': 'SUCCEEDED', 'resolvedSourceVersion': 'b' * 40}]},
                    {'builds': [{'buildStatus': 'SUCCEEDED', 'resolvedSourceVersion': 'b' * 40}]},
                ]), patch.object(BUILD.subprocess, 'run') as run, \
                patch.object(BUILD, 'Path', side_effect=lambda name: Path(temp) / name), \
                self.assertRaisesRegex(SystemExit, 'different commit'):
            BUILD.build()
        run.assert_not_called()


if __name__ == '__main__':
    unittest.main()
