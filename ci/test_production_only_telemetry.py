"""Production-only releases must not inherit a retired collector when disabled."""
import copy
import importlib.util
import json
import os
import unittest
from pathlib import Path
from unittest.mock import patch

SPEC = importlib.util.spec_from_file_location('production_only_deploy', Path(__file__).with_name('deploy-production-only.py'))
MODULE = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(MODULE)
TASK = {'family': 'backend', 'containerDefinitions': [
    {'name': 'backend', 'image': 'approved@sha256:abc', 'secrets': [{'name': 'DB_PASSWORD', 'valueFrom': 'db'}],
     'environment': [{'name': 'OBSERVABILITY_ENABLED', 'value': 'true'},
                     {'name': 'OTEL_EXPORTER_OTLP_ENDPOINT', 'value': 'retired'},
                     {'name': 'DB_HOST', 'value': 'database'}, {'name': 'RELEASE_SHA', 'value': 'sha'}],
     'dependsOn': [{'containerName': 'telemetry-collector', 'condition': 'START'}]},
    {'name': 'telemetry-collector', 'secrets': [{'name': 'TEMPO_AUTHORIZATION', 'valueFrom': 'deleted'}]}]}


class ProductionOnlyTelemetryTest(unittest.TestCase):
    def test_disabled_removes_collector_but_preserves_app_and_database(self):
        original = copy.deepcopy(TASK)
        task = MODULE.without_telemetry(TASK)
        self.assertEqual(TASK, original)
        self.assertEqual(len(task['containerDefinitions']), 1)
        app = task['containerDefinitions'][0]
        self.assertEqual(app['secrets'], original['containerDefinitions'][0]['secrets'])
        self.assertEqual(app['image'], 'approved@sha256:abc')
        env = {e['name']: e['value'] for e in app['environment']}
        self.assertEqual(env, {'DB_HOST': 'database', 'RELEASE_SHA': 'sha', 'OBSERVABILITY_ENABLED': 'false'})
        self.assertEqual(app['dependsOn'], [])

    def test_registration_disabled_sanitizes_before_aws(self):
        with patch.dict(os.environ, {'PRODUCTION_OBSERVABILITY_ENABLED': 'false'}, clear=True), \
                patch.object(MODULE, 'AWS') as aws:
            MODULE.aws('ecs', 'register-task-definition', '--cli-input-json', json.dumps(TASK))
            sent = json.loads(aws.call_args.args[-1])
            self.assertEqual(len(sent['containerDefinitions']), 1)

    def test_enabled_keeps_exact_terraform_collector(self):
        args = ('ecs', 'register-task-definition', '--cli-input-json', json.dumps(TASK))
        with patch.dict(os.environ, {'PRODUCTION_OBSERVABILITY_ENABLED': 'true'}, clear=True), \
                patch.object(MODULE, 'AWS') as aws:
            MODULE.aws(*args)
            aws.assert_called_once_with(*args)

    def test_other_aws_operations_are_unchanged(self):
        with patch.object(MODULE, 'AWS') as aws:
            MODULE.aws('ecs', 'describe-services', '--cluster', 'production')
            aws.assert_called_once_with('ecs', 'describe-services', '--cluster', 'production')

    def test_shared_deployer_still_enforces_approval(self):
        with patch.dict(os.environ, {}, clear=True), patch.object(MODULE, 'AWS') as aws:
            with self.assertRaisesRegex(SystemExit, 'manual approval'):
                MODULE.DEPLOY.deploy('PRODUCTION', {})
            aws.assert_not_called()


if __name__ == '__main__':
    unittest.main()
