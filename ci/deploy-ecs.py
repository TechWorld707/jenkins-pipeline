"""Deploy the same release digests to existing ECS services; never rebuild."""
import json
import os
from pathlib import Path
import re
import subprocess
import sys
import time
import urllib.request


def aws(*args):
    return json.loads(subprocess.check_output(['aws', *args, '--output', 'json']))


stage = sys.argv[1]
if stage not in {'STAGING', 'PRODUCTION'}:
    raise SystemExit('Unknown environment')
release = json.loads(Path('release.json').read_text())
if release['commit'] != os.environ['RELEASE_SHA']:
    raise SystemExit('Release SHA mismatch')
cluster = os.environ[f'{stage}_CLUSTER']
updates = []
# Prepare BOTH task definitions before changing either service.
for component in ('backend', 'frontend'):
    image = release['images'][component]
    if not re.fullmatch(r'[0-9]{12}\.dkr\.ecr\.eu-west-2\.amazonaws\.com/[^@]+@sha256:[0-9a-f]{64}', image):
        raise SystemExit('Expected an immutable ECR image digest')
    service = os.environ[f'{stage}_{component.upper()}_SERVICE']
    response = aws('ecs', 'describe-services', '--cluster', cluster, '--services', service)
    if response.get('failures') or len(response.get('services', [])) != 1:
        raise SystemExit(f'Service unavailable: {service}')
    current = response['services'][0]
    if current.get('deploymentController', {}).get('type') != 'ECS':
        raise SystemExit('This pipeline requires ECS rolling deployments')
    task = aws('ecs', 'describe-task-definition', '--task-definition', current['taskDefinition'])['taskDefinition']
    matches = [c for c in task['containerDefinitions'] if c['name'] == component]
    if len(matches) != 1:
        raise SystemExit(f'Task must contain a container named {component}')
    matches[0]['image'] = image
    for key in ('taskDefinitionArn', 'revision', 'status', 'requiresAttributes', 'compatibilities',
                'registeredAt', 'registeredBy', 'deregisteredAt'):
        task.pop(key, None)
    new_task = aws('ecs', 'register-task-definition', '--cli-input-json', json.dumps(task))['taskDefinition']['taskDefinitionArn']
    updates.append((service, new_task))
for service, task in updates:
    aws('ecs', 'update-service', '--cluster', cluster, '--service', service, '--task-definition', task)
subprocess.run(['aws', 'ecs', 'wait', 'services-stable', '--cluster', cluster, '--services',
                *[service for service, _ in updates]], check=True)
for service, expected in updates:
    result = aws('ecs', 'describe-services', '--cluster', cluster, '--services', service)['services'][0]
    if result['taskDefinition'] != expected or result['runningCount'] < 1 or result['pendingCount'] != 0:
        raise SystemExit(f'{service} did not reach the requested release (possible rollback)')
url = os.environ[f'{stage}_URL'].rstrip('/')
# Exercise the frontend and backend health endpoint through the environment URL.
for path in ('/', '/healthz'):
    for attempt in range(12):
        try:
            with urllib.request.urlopen(url + path, timeout=15) as response:
                if response.status != 200:
                    raise ValueError('Non-200 health response')
            break
        except Exception:
            if attempt == 11:
                raise
            time.sleep(10)
print(f'{stage} verified for {release["commit"]}')
