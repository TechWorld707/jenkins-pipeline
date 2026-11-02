"""Deploy approved release digests; activate idle services and scaling after verification."""
import json
import os
import re
import subprocess
import sys
import time
import urllib.request
from pathlib import Path

from telemetry.events import emit

DIMENSION = 'ecs:service:DesiredCount'


def aws(*args):
    return json.loads(subprocess.check_output(['aws', *args, '--output', 'json']))


def deploy(stage, evidence):
    if stage not in {'STAGING', 'PRODUCTION'}:
        raise SystemExit('Unknown environment')
    if (os.environ.get(f'{stage}_DEPLOYMENT_STATUS') != 'DEPLOYING'
            or not os.environ.get(f'{stage}_APPROVER') or not os.environ.get(f'{stage}_APPROVED_AT')):
        raise SystemExit('Deployment requires the Jenkins manual approval record')
    release = json.loads(Path('release.json').read_text())
    if release['commit'] != os.environ['RELEASE_SHA']:
        raise SystemExit('Release SHA mismatch')
    for component in ('backend', 'frontend'):
        if not re.fullmatch(r'[0-9]{12}\.dkr\.ecr\.eu-west-2\.amazonaws\.com/[^@]+@sha256:[0-9a-f]{64}',
                            release['images'][component]):
            raise SystemExit('Expected an immutable ECR image digest')
    cluster = os.environ[f'{stage}_CLUSTER']
    templates = None
    if stage == 'PRODUCTION' and os.getenv('PRODUCTION_OBSERVABILITY_ENABLED', '').lower() == 'true':
        templates = json.loads(aws('ssm', 'get-parameter', '--name',
                                   '/webtech-production/observability/task-templates')['Parameter']['Value'])
    prepared = []
    # Validate BOTH services and their capacity metadata before registering or deploying anything.
    for component in ('backend', 'frontend'):
        service = os.environ[f'{stage}_{component.upper()}_SERVICE']
        response = aws('ecs', 'describe-services', '--cluster', cluster, '--services', service)
        if response.get('failures') or len(response.get('services', [])) != 1:
            raise SystemExit(f'Service unavailable: {service}')
        current = response['services'][0]
        if current.get('deploymentController', {}).get('type') != 'ECS':
            raise SystemExit('This pipeline requires ECS rolling deployments')
        resource_id = f'service/{cluster}/{service}'
        targets = aws('application-autoscaling', 'describe-scalable-targets', '--service-namespace', 'ecs',
                      '--scalable-dimension', DIMENSION, '--resource-ids', resource_id)['ScalableTargets']
        if len(targets) != 1:
            raise SystemExit(f'Missing autoscaling target: {service}')
        target = targets[0]
        tags = aws('application-autoscaling', 'list-tags-for-resource',
                   '--resource-arn', target['ScalableTargetARN'])['Tags']
        minimum = int(tags.get('ReleaseMinCapacity', '0'))
        if not 1 <= minimum <= target['MaxCapacity']:
            raise SystemExit(f'Invalid ReleaseMinCapacity tag for {service}; apply the updated infrastructure first')
        task = aws('ecs', 'describe-task-definition', '--task-definition', current['taskDefinition'])['taskDefinition']
        if templates is not None:
            task = aws('ecs', 'describe-task-definition', '--task-definition', templates[component])['taskDefinition']
        if stage == 'PRODUCTION':
            evidence[service] = {'previous': current['taskDefinition'], 'image': release['images'][component],
                                 'rollback': 'not_attempted'}
        matches = [c for c in task['containerDefinitions'] if c['name'] == component]
        if len(matches) != 1:
            raise SystemExit(f'Task must contain a container named {component}')
        matches[0]['image'] = release['images'][component]
        if stage == 'PRODUCTION':
            environment = matches[0].setdefault('environment', [])
            environment[:] = [item for item in environment if item['name'] != 'RELEASE_SHA']
            environment.append({'name': 'RELEASE_SHA', 'value': release['commit']})
        for key in ('taskDefinitionArn', 'revision', 'status', 'requiresAttributes', 'compatibilities',
                    'registeredAt', 'registeredBy', 'deregisteredAt'):
            task.pop(key, None)
        prepared.append((service, task, current['desiredCount'], resource_id, minimum))
    updates = []
    for service, task, count, resource_id, minimum in prepared:
        new_task = aws('ecs', 'register-task-definition', '--cli-input-json',
                       json.dumps(task))['taskDefinition']['taskDefinitionArn']
        updates.append((service, new_task, count, resource_id, minimum))
        if stage == 'PRODUCTION':
            evidence[service]['requested'] = new_task
    for service, task, count, _, minimum in updates:
        if stage == 'PRODUCTION':
            emit('production.service.update', 'started', environment='production', service_name=service,
                 task_revision=task, image=evidence[service]['image'])
        args = ['ecs', 'update-service', '--cluster', cluster, '--service', service, '--task-definition', task]
        # Wake idle scaffolding only after approval; preserve capacity chosen by autoscaling on later releases.
        if count == 0:
            args += ['--desired-count', str(minimum)]
        aws(*args)
        if stage == 'PRODUCTION':
            evidence[service]['updated'] = True
    if stage == 'PRODUCTION':
        emit('production.stability', 'started', environment='production')
    subprocess.run(['aws', 'ecs', 'wait', 'services-stable', '--cluster', cluster, '--services',
                    *[row[0] for row in updates]], check=True)
    for service, expected, _, _, _ in updates:
        result = aws('ecs', 'describe-services', '--cluster', cluster, '--services', service)['services'][0]
        if result['taskDefinition'] != expected or result['runningCount'] < 1 or result['pendingCount'] != 0:
            raise SystemExit(f'{service} did not reach the requested release (possible rollback)')
    url = os.environ[f'{stage}_URL'].rstrip('/')
    if stage == 'PRODUCTION':
        emit('production.stability', 'succeeded', environment='production')
    for path in ('/', '/healthz', '/api/health/db'):
        for attempt in range(12):
            try:
                with urllib.request.urlopen(url + path, timeout=15) as response:
                    if response.status != 200:
                        raise ValueError('Non-200 health response')
                if stage == 'PRODUCTION':
                    emit('production.smoke', 'succeeded', environment='production', route=path)
                break
            except Exception:
                if attempt == 11:
                    if stage == 'PRODUCTION':
                        emit('production.smoke', 'failed', environment='production', route=path)
                    raise
                time.sleep(10)
    # Failed initial deployments never activate autoscaling. Existing active scaling is left intact on failure.
    for _, _, _, resource_id, minimum in updates:
        aws('application-autoscaling', 'register-scalable-target', '--service-namespace', 'ecs',
            '--scalable-dimension', DIMENSION, '--resource-id', resource_id,
            '--min-capacity', str(minimum), '--suspended-state',
            json.dumps({'DynamicScalingInSuspended': False, 'DynamicScalingOutSuspended': False,
                        'ScheduledScalingSuspended': False}))
    print(f'{stage} verified for {release["commit"]}; autoscaling active')


def main(stage):
    if stage != 'PRODUCTION':
        return deploy(stage, {})
    evidence = {}
    outcome = 'failed'
    emit('production.deploy', 'started', environment='production')
    try:
        deploy(stage, evidence)
        outcome = 'succeeded'
    finally:
        for service, item in evidence.items():
            try:
                current = aws('ecs', 'describe-services', '--cluster', os.environ['PRODUCTION_CLUSTER'],
                              '--services', service)['services'][0]
                item['actual'] = current['taskDefinition']
                requested = item.get('requested')
                if requested and item.get('updated') and current['taskDefinition'] == item['previous']:
                    completed = any(d.get('taskDefinition') == item['previous'] and d.get('status') == 'PRIMARY'
                                    and d.get('rolloutState') == 'COMPLETED' for d in current.get('deployments', []))
                    item['rollback'] = 'succeeded' if completed and current.get('runningCount', 0) > 0 and not current.get('pendingCount', 0) else 'attempted'
                elif requested and current['taskDefinition'] != requested:
                    item['rollback'] = 'partial'
                else:
                    item['rollback'] = 'not_attempted'
            except (KeyError, IndexError, OSError, ValueError, subprocess.SubprocessError):
                item['rollback'] = 'unknown'
            emit('production.service.result', outcome, environment='production', service_name=service, **item)
        Path('production-deployment.json').write_text(json.dumps({'outcome': outcome, 'services': evidence}, indent=2))
        emit('production.deploy', outcome, environment='production', services=evidence)


if __name__ == '__main__':
    main(sys.argv[1])
