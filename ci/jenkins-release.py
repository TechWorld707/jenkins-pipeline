"""Jenkins orchestration. AWS authentication comes from the agent's IAM identity."""
import json
import os
from pathlib import Path
import subprocess
import sys
import signal
import time
import urllib.request


def aws(*args):
    return json.loads(subprocess.check_output(["aws", *args, "--output", "json"]))


def github_gate():
    repo = os.environ["GITHUB_REPOSITORY"]
    sha = os.environ["RELEASE_SHA"]
    url = f"https://api.github.com/repos/{repo}/actions/workflows/security-scan.yml/runs?head_sha={sha}&event=push&per_page=10"
    for _ in range(120):
        req = urllib.request.Request(url, headers={"Authorization": f"Bearer {os.environ['GH_TOKEN']}",
                                                  "Accept": "application/vnd.github+json"})
        with urllib.request.urlopen(req, timeout=30) as response:
            runs = json.load(response)["workflow_runs"]
        runs = [r for r in runs if r['head_sha'] == sha and r['head_branch'] == 'main']
        if runs:
            run = max(runs, key=lambda r: r['id'])
            if run['status'] == 'completed':
                if run['conclusion'] != 'success':
                    raise SystemExit(f"GitHub workflow failed: {run['html_url']}")
                return
        time.sleep(15)
    raise SystemExit("Timed out waiting for successful main workflow for this exact SHA")


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

signal.signal(signal.SIGTERM, interrupted)

mode = sys.argv[1]
if mode == 'config':
    required = ['CODEBUILD_PROJECT', 'REPORT_BUCKET', 'PRODUCTION_APPROVERS']
    for stage in ['STAGING', 'PRODUCTION']:
        required += [f'{stage}_{name}' for name in ['CLUSTER', 'FRONTEND_SERVICE', 'BACKEND_SERVICE', 'URL']]
    missing = [key for key in required if not os.environ.get(key, '').strip()]
    if missing:
        raise SystemExit('Configure Jenkins parameters: ' + ', '.join(missing))
elif mode == 'github':
    github_gate()
elif mode == 'build':
    build()
else:
    raise SystemExit('Unknown mode')
