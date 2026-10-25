"""Jenkins orchestration. AWS authentication comes from the agent's IAM identity."""
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
    elif mode == 'staging-config':
        required = ['STAGING_CLUSTER', 'STAGING_FRONTEND_SERVICE', 'STAGING_BACKEND_SERVICE',
                    'STAGING_URL', 'STAGING_APPROVERS']
        missing = [key for key in required if not os.environ.get(key, '').strip()]
        if missing:
            raise SystemExit('Configure staging deployment settings: ' + ', '.join(missing))
        if not os.environ['STAGING_URL'].startswith('https://'):
            raise SystemExit('STAGING_URL must use HTTPS')
    elif mode == 'build':
        build()
    else:
        raise SystemExit('Unknown mode')


if __name__ == '__main__':
    signal.signal(signal.SIGTERM, interrupted)
    main()
