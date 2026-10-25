"""Jenkins orchestration. AWS authentication comes from the agent's IAM identity."""
import hashlib
import json
import os
import signal
import subprocess
import sys
import time
from pathlib import Path


def aws(*args):
    return json.loads(subprocess.check_output(["aws", *args, "--output", "json"]))


def build():
    sha = os.environ['RELEASE_SHA']
    response = aws('codebuild', 'start-build', '--project-name', os.environ['CODEBUILD_PROJECT'],
                   '--source-version', sha, '--environment-variables-override',
                   json.dumps([{'name': 'EXPECTED_COMMIT', 'value': sha, 'type': 'PLAINTEXT'}]))
    build_id = response['build']['id']
    Path('codebuild-id.txt').write_text(build_id)
    print(f"CodeBuild: {build_id}", flush=True)
    try:
        for _ in range(160):
            result = aws('codebuild', 'batch-get-builds', '--ids', build_id)['builds'][0]
            status = result['buildStatus']
            if status != 'IN_PROGRESS':
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
    prefix = f"s3://{os.environ['REPORT_BUCKET']}/reports/{sha}/{build_id.rsplit(':', 1)[-1]}"
    subprocess.run(['aws', 's3', 'cp', prefix + '/release.json', 'release.json'], check=True)
    release = json.loads(Path('release.json').read_text())
    if release['commit'] != sha:
        raise SystemExit('Release manifest commit mismatch')
    subprocess.run(['aws', 's3', 'cp', prefix + '/', 'reports/', '--recursive', '--exclude', '*',
                    '--include', '*.html', '--include', '*-trivy.json'], check=True)


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
