"""Approved first launches activate capacity only after health checks pass."""
import importlib.util
import json
import os
import unittest
from pathlib import Path
from unittest.mock import MagicMock, patch

SPEC = importlib.util.spec_from_file_location('deployment', Path(__file__).with_name('deploy-ecs.py'))
DEPLOY = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(DEPLOY)
SHA = 'a' * 40
IMAGE = '671662643382.dkr.ecr.eu-west-2.amazonaws.com/app@sha256:' + 'b' * 64
ENV = {
    'RELEASE_SHA': SHA, 'STAGING_CLUSTER': 'cluster',
    'STAGING_BACKEND_SERVICE': 'backend', 'STAGING_FRONTEND_SERVICE': 'frontend',
    'STAGING_URL': 'https://staging.example.com', 'STAGING_DEPLOYMENT_STATUS': 'DEPLOYING',
    'STAGING_APPROVER': 'reviewer', 'STAGING_APPROVED_AT': '2026-10-28T12:00:00Z',
}


class DeploymentActivationTest(unittest.TestCase):
    def run_deployment(self, count=0, unhealthy=False, invalid_capacity=False, approved=True):
        calls = []
        registered = set()

        def aws(*args):
            calls.append(args)
            if args[:2] == ('ecs', 'describe-services'):
                name = args[-1]
                return {'services': [{'deploymentController': {'type': 'ECS'}, 'desiredCount': count,
                                     'taskDefinition': 'new-' + name if name in registered else 'old-' + name,
                                     'runningCount': 1, 'pendingCount': 0}]}
            if args[:2] == ('application-autoscaling', 'describe-scalable-targets'):
                return {'ScalableTargets': [{'ScalableTargetARN': 'target-arn', 'MaxCapacity': 6}]}
            if args[:2] == ('application-autoscaling', 'list-tags-for-resource'):
                return {'Tags': {'ReleaseMinCapacity': '0' if invalid_capacity else '2'}}
            if args[:2] == ('ecs', 'describe-task-definition'):
                name = args[-1].removeprefix('old-')
                return {'taskDefinition': {'family': name, 'containerDefinitions': [{'name': name}]}}
            if args[:2] == ('ecs', 'register-task-definition'):
                name = json.loads(args[-1])['family']
                registered.add(name)
                return {'taskDefinition': {'taskDefinitionArn': 'new-' + name}}
            return {}

        environment = dict(ENV)
        if not approved:
            environment.pop('STAGING_APPROVER')
        response = MagicMock()
        response.__enter__.return_value.status = 200
        with patch.dict(os.environ, environment, clear=True), \
                patch.object(DEPLOY.Path, 'read_text', return_value=json.dumps({
                    'commit': SHA, 'images': {'frontend': IMAGE, 'backend': IMAGE}})), \
                patch.object(DEPLOY, 'aws', side_effect=aws), \
                patch.object(DEPLOY.subprocess, 'run'), \
                patch.object(DEPLOY.time, 'sleep'), \
                patch.object(DEPLOY.urllib.request, 'urlopen',
                             side_effect=RuntimeError('unhealthy') if unhealthy else None,
                             return_value=response):
            if unhealthy:
                with self.assertRaisesRegex(RuntimeError, 'unhealthy'):
                    DEPLOY.main('STAGING')
            elif invalid_capacity or not approved:
                with self.assertRaises(SystemExit):
                    DEPLOY.main('STAGING')
            else:
                DEPLOY.main('STAGING')
        return calls

    def test_idle_services_start_then_scaling_activates(self):
        calls = self.run_deployment()
        updates = [c for c in calls if c[:2] == ('ecs', 'update-service')]
        self.assertEqual(len(updates), 2)
        self.assertTrue(all(c[-2:] == ('--desired-count', '2') for c in updates))
        self.assertEqual([c[1] for c in calls[-2:]], ['register-scalable-target'] * 2)
        self.assertTrue(all(json.loads(c[-1])['DynamicScalingOutSuspended'] is False for c in calls[-2:]))

    def test_later_release_preserves_autoscaled_count(self):
        calls = self.run_deployment(count=5)
        updates = [c for c in calls if c[:2] == ('ecs', 'update-service')]
        self.assertTrue(all('--desired-count' not in c for c in updates))

    def test_failed_health_checks_do_not_activate_scaling(self):
        calls = self.run_deployment(unhealthy=True)
        self.assertFalse(any(c[:2] == ('application-autoscaling', 'register-scalable-target') for c in calls))

    def test_invalid_capacity_blocks_all_mutations(self):
        calls = self.run_deployment(invalid_capacity=True)
        self.assertFalse(any(c[1] in {'register-task-definition', 'update-service', 'register-scalable-target'}
                             for c in calls))

    def test_missing_approval_blocks_all_aws_calls(self):
        self.assertEqual(self.run_deployment(approved=False), [])


if __name__ == '__main__':
    unittest.main()
