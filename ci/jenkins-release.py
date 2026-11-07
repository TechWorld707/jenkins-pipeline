"""Jenkins orchestration. AWS authentication comes from the agent's IAM identity."""
import hashlib
import json
import os
import re
import signal
import subprocess
import sys
import time
from pathlib import Path

from telemetry.events import emit


def aws(*args):
    return json.loads(subprocess.check_output(["aws", *args, "--output", "json"]))


def download_release(build_id, sha):
    prefix = f"s3://{os.environ['REPORT_BUCKET']}/reports/{sha}/{build_id.rsplit(':', 1)[-1]}"
    subprocess.run(['aws', 's3', 'cp', prefix + '/release.json', 'release.json'], check=True)
    release = json.loads(Path('release.json').read_text())
    if release['commit'] != sha:
        raise SystemExit('Release manifest commit mismatch')
    subprocess.run(['aws', 's3', 'cp', prefix + '/', 'reports/', '--recursive', '--exclude', '*',
                    '--include', '*.html', '--include', '*-trivy.json'], check=True)

    return release


def verify_reused_release(release, sha):
    if release.get('commit') != sha:
        raise SystemExit('Existing release commit mismatch')
    if set(release.get('images', {})) != {'frontend', 'backend'}:
        raise SystemExit('Existing release must contain both immutable images')
    account = aws('sts', 'get-caller-identity')['Account']
    region = os.environ.get('AWS_DEFAULT_REGION', 'eu-west-2')
    pattern = (rf'{re.escape(account)}\.dkr\.ecr\.{re.escape(region)}\.amazonaws\.com/'
               r'(?P<repo>[a-z0-9][a-z0-9._/-]*)@(?P<digest>sha256:[0-9a-f]{64})')
    for component in ('frontend', 'backend'):
        match = re.fullmatch(pattern, release['images'][component])
        if not match:
            raise SystemExit('Existing release image must use this AWS account/region and an immutable digest')
        image = aws('ecr', 'describe-images', '--repository-name', match['repo'],
                    '--image-ids', f'imageTag={sha}')
        details = image.get('imageDetails', [])
        if len(details) != 1 or details[0].get('imageDigest') != match['digest']:
            raise SystemExit('Existing release digest no longer matches the immutable ECR tag')
        # Reapply the same HIGH/CRITICAL gate to the archived JSON, failing closed
        # for missing, malformed or blocking reports. This does not refresh the scan DB.
        subprocess.run([sys.executable, 'ci/image-report.py', component, sha], check=True)


def reuse_release(sha):
    project = os.environ['CODEBUILD_PROJECT']
    ids = aws('codebuild', 'list-builds-for-project', '--project-name', project,
              '--sort-order', 'DESCENDING', '--max-items', '30').get('ids', [])
    if not ids:
        return False
    builds = aws('codebuild', 'batch-get-builds', '--ids', *ids)['builds']
    by_id = {item['id']: item for item in builds}
    for build_id in ids:
        item = by_id.get(build_id, {})
        if (item.get('projectName') != project or item.get('buildStatus') != 'SUCCEEDED'
                or item.get('resolvedSourceVersion') != sha):
            continue
        emit('codebuild.reuse', 'started', codebuild_id=build_id)
        release = download_release(build_id, sha)
        verify_reused_release(release, sha)
        Path('codebuild-id.txt').write_text(build_id)
        emit('codebuild.reuse', 'succeeded', codebuild_id=build_id)
        print(f'Reusing verified release {build_id} for {sha}; archived scans are reused, not refreshed.', flush=True)
        return True
    return False


def build():
    sha = os.environ['RELEASE_SHA']
    if reuse_release(sha):
        return
    overrides = [{'name': 'EXPECTED_COMMIT', 'value': sha, 'type': 'PLAINTEXT'}]
    if os.getenv('PRODUCTION_OBSERVABILITY_ENABLED', '').lower() == 'true':
        overrides.extend({'name': name, 'value': value, 'type': 'PLAINTEXT'} for name, value in {
            'PRODUCTION_OBSERVABILITY_ENABLED': 'true',
            'PIPELINE_RUN_ID': os.getenv('BUILD_TAG', 'unknown'),
            'PRODUCTION_EVENT_LOG_GROUP': '/webtech/production/pipeline-events'
        }.items())
    emit('codebuild', 'started')
    response = aws('codebuild', 'start-build', '--project-name', os.environ['CODEBUILD_PROJECT'],
                   '--source-version', sha, '--environment-variables-override',
                   json.dumps(overrides))
    build_id = response['build']['id']
    Path('codebuild-id.txt').write_text(build_id)
    emit('codebuild.accepted', 'succeeded', codebuild_id=build_id)
    print(f"CodeBuild: {build_id}", flush=True)
    try:
        for _ in range(160):
            result = aws('codebuild', 'batch-get-builds', '--ids', build_id)['builds'][0]
            status = result['buildStatus']
            if status != 'IN_PROGRESS':
                emit('codebuild', status.lower(), codebuild_id=build_id)
                if status != 'SUCCEEDED':
                    raise SystemExit(f"CodeBuild {status}. See CloudWatch logs: {result.get('logs', {}).get('deepLink', build_id)}")
                break
            time.sleep(15)
        else:
            raise SystemExit('CodeBuild wait timed out')
    finally:
        # On Jenkins cancellation or failure, stop the remote build when still running.
        result = aws('codebuild', 'batch-get-builds', '--ids', build_id)['builds'][0]
        if result['buildStatus'] == 'IN_PROGRESS':
            aws('codebuild', 'stop-build', '--id', build_id)
    if result.get('resolvedSourceVersion') != sha:
        raise SystemExit('CodeBuild built a different commit')
    download_release(build_id, sha)


def interrupted(signum, frame):
    raise SystemExit('Jenkins interrupted the pipeline')

def main():
    mode = sys.argv[1]
    if mode == 'config':
        required = ['CODEBUILD_PROJECT', 'REPORT_BUCKET', 'RELEASE_SHA']
        missing = [key for key in required if not os.environ.get(key, '').strip()]
        if missing:
            raise SystemExit('Configure Jenkins build settings: ' + ', '.join(missing))
        print(f"CodeBuild project: {os.environ['CODEBUILD_PROJECT']}", flush=True)
        print(f"Report bucket: {os.environ['REPORT_BUCKET']}", flush=True)
    elif mode in {'staging-config', 'production-config'}:
        stage = mode.split('-')[0].upper()
        required = [f'{stage}_{key}' for key in ['CLUSTER', 'FRONTEND_SERVICE', 'BACKEND_SERVICE',
                                                'URL', 'APPROVERS']]
        missing = [key for key in required if not os.environ.get(key, '').strip()]
        if missing:
            raise SystemExit(f'Configure {stage.lower()} deployment settings: ' + ', '.join(missing))
        if not any(user.strip() for user in os.environ[f'{stage}_APPROVERS'].split(',')):
            raise SystemExit(f'{stage}_APPROVERS must name at least one Jenkins user or group')
        if not os.environ[f'{stage}_URL'].startswith('https://'):
            raise SystemExit(f'{stage}_URL must use HTTPS')
        if stage == 'PRODUCTION':
            if os.environ['PRODUCTION_CLUSTER'] == os.environ.get('STAGING_CLUSTER'):
                raise SystemExit('Production must use a separate ECS cluster from staging')
            if os.environ['PRODUCTION_URL'].rstrip('/') == os.environ.get('STAGING_URL', '').rstrip('/'):
                raise SystemExit('Production must use a separate URL from staging')
    elif mode == 'production-ready':
        if os.environ.get('STAGING_DEPLOYMENT_STATUS') != 'VERIFIED':
            raise SystemExit('Production requires successful staging verification in this run')
        manifest = Path('release.json').read_bytes()
        if hashlib.sha256(manifest).hexdigest() != os.environ.get('STAGING_RELEASE_HASH'):
            raise SystemExit('Release manifest changed after staging verification')
        if json.loads(manifest)['commit'] != os.environ['RELEASE_SHA']:
            raise SystemExit('Release manifest commit mismatch')
    elif mode == 'build':
        build()
    else:
        raise SystemExit('Unknown mode')


if __name__ == '__main__':
    signal.signal(signal.SIGTERM, interrupted)
    main()
