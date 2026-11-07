"""Production-only adapter: explicitly disable inherited telemetry when unchecked."""
import copy
import importlib.util
import json
import os
from pathlib import Path

SPEC = importlib.util.spec_from_file_location('shared_deploy', Path(__file__).with_name('deploy-ecs.py'))
DEPLOY = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(DEPLOY)
AWS = DEPLOY.aws


def without_telemetry(task):
    task = copy.deepcopy(task)
    containers = task['containerDefinitions']
    task['containerDefinitions'] = [c for c in containers if c['name'] != 'telemetry-collector']
    for container in task['containerDefinitions']:
        if container['name'] not in {'backend', 'frontend'}:
            continue
        environment = container.setdefault('environment', [])
        environment[:] = [e for e in environment if not (
            e['name'].startswith('OTEL_') or e['name'] == 'OBSERVABILITY_ENABLED')]
        environment.append({'name': 'OBSERVABILITY_ENABLED', 'value': 'false'})
        if 'dependsOn' in container:
            container['dependsOn'] = [d for d in container['dependsOn']
                                      if d['containerName'] != 'telemetry-collector']
    return task


def aws(*args):
    if (args[:2] == ('ecs', 'register-task-definition')
            and os.getenv('PRODUCTION_OBSERVABILITY_ENABLED', '').lower() != 'true'):
        arguments = list(args)
        index = arguments.index('--cli-input-json') + 1
        arguments[index] = json.dumps(without_telemetry(json.loads(arguments[index])))
        return AWS(*arguments)
    return AWS(*args)


def main():
    # The shared helper still enforces manual approval, exact digests, health checks,
    # rollback evidence and scaling activation; its source is unchanged.
    DEPLOY.aws = aws
    DEPLOY.main('PRODUCTION')


if __name__ == '__main__':
    main()
