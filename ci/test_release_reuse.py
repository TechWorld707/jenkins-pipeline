"""Verify retry reuse preserves exact source, image digests and scan gates."""
import importlib.util
import os
import subprocess
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

SPEC = importlib.util.spec_from_file_location('reuse_build', Path(__file__).with_name('jenkins-release.py'))
BUILD = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(BUILD)
SHA = 'a' * 40
ACCOUNT = '123456789012'
DIGEST = 'sha256:' + 'b' * 64
SETTINGS = {'CODEBUILD_PROJECT': 'test-builder', 'REPORT_BUCKET': 'test-reports', 'RELEASE_SHA': SHA}
RELEASE = {'commit': SHA, 'images': {
    component: f'{ACCOUNT}.dkr.ecr.eu-west-2.amazonaws.com/test-{component}@{DIGEST}'
    for component in ('frontend', 'backend')
}}


class ReleaseReuseTest(unittest.TestCase):
    def test_no_history_requires_new_build(self):
        with patch.dict(os.environ, SETTINGS, clear=True), patch.object(BUILD, 'aws', return_value={'ids': []}):
            self.assertFalse(BUILD.reuse_release(SHA))

    def test_wrong_commit_failed_or_other_project_cannot_be_reused(self):
        for changes in ({'resolvedSourceVersion': 'c' * 40}, {'buildStatus': 'FAILED'}, {'projectName': 'other'}):
            candidate = {'id': 'test-builder:previous', 'projectName': 'test-builder',
                         'buildStatus': 'SUCCEEDED', 'resolvedSourceVersion': SHA, **changes}
            with self.subTest(changes=changes), patch.dict(os.environ, SETTINGS, clear=True), \
                    patch.object(BUILD, 'aws', side_effect=[{'ids': [candidate['id']]}, {'builds': [candidate]}]), \
                    patch.object(BUILD, 'download_release') as download:
                self.assertFalse(BUILD.reuse_release(SHA))
                download.assert_not_called()

    def test_success_checks_both_images_and_both_scan_reports(self):
        candidate = {'id': 'test-builder:previous', 'projectName': 'test-builder',
                     'buildStatus': 'SUCCEEDED', 'resolvedSourceVersion': SHA}
        responses = [{'ids': [candidate['id']]}, {'builds': [candidate]}, {'Account': ACCOUNT},
                     {'imageDetails': [{'imageDigest': DIGEST}]}, {'imageDetails': [{'imageDigest': DIGEST}]}]
        with tempfile.TemporaryDirectory() as work, patch.dict(os.environ, SETTINGS, clear=True), \
                patch.object(BUILD, 'aws', side_effect=responses) as aws, \
                patch.object(BUILD, 'download_release', return_value=RELEASE) as download, \
                patch.object(BUILD.subprocess, 'run') as run, \
                patch.object(BUILD, 'Path', side_effect=lambda name: Path(work) / name):
            self.assertTrue(BUILD.reuse_release(SHA))
            download.assert_called_once_with(candidate['id'], SHA)
            self.assertEqual((Path(work) / 'codebuild-id.txt').read_text(), candidate['id'])
            self.assertEqual([call.args[0][-2:] for call in run.call_args_list],
                             [['frontend', SHA], ['backend', SHA]])
            self.assertEqual(sum(call.args[:2] == ('ecr', 'describe-images') for call in aws.call_args_list), 2)

    def test_changed_digest_blocks_reuse(self):
        with patch.dict(os.environ, SETTINGS, clear=True), \
                patch.object(BUILD, 'aws', side_effect=[{'Account': ACCOUNT},
                    {'imageDetails': [{'imageDigest': 'sha256:' + 'd' * 64}]}]), \
                patch.object(BUILD.subprocess, 'run') as run, \
                self.assertRaisesRegex(SystemExit, 'digest no longer matches'):
            BUILD.verify_reused_release(RELEASE, SHA)
        run.assert_not_called()

    def test_invalid_account_or_commit_blocks_reuse(self):
        for release in ({**RELEASE, 'commit': 'd' * 40}, RELEASE):
            with self.subTest(commit=release['commit']), patch.dict(os.environ, SETTINGS, clear=True), \
                    patch.object(BUILD, 'aws', return_value={'Account': '999999999999'}), \
                    patch.object(BUILD.subprocess, 'run') as run, self.assertRaises(SystemExit):
                BUILD.verify_reused_release(release, SHA)
            run.assert_not_called()

    def test_scan_failure_is_not_bypassed(self):
        with patch.dict(os.environ, SETTINGS, clear=True), \
                patch.object(BUILD, 'aws', side_effect=[{'Account': ACCOUNT},
                    {'imageDetails': [{'imageDigest': DIGEST}]}]), \
                patch.object(BUILD.subprocess, 'run', side_effect=subprocess.CalledProcessError(1, 'scan-gate')), \
                self.assertRaises(subprocess.CalledProcessError):
            BUILD.verify_reused_release(RELEASE, SHA)

    def test_reuse_does_not_start_another_codebuild(self):
        with patch.dict(os.environ, SETTINGS, clear=True), \
                patch.object(BUILD, 'reuse_release', return_value=True), patch.object(BUILD, 'aws') as aws:
            BUILD.build()
        aws.assert_not_called()
