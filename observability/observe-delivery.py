"""Run every minute outside Jenkins: read-only job reconciliation without raw logs/secrets."""
import base64
import json
import os
import sys
import time
import urllib.request
from http.client import HTTPException
from pathlib import Path
from urllib.parse import urlsplit

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'ci'))
from telemetry.events import emit


def get(url, authorization):
    parsed = urlsplit(url)
    if parsed.scheme != 'https' and parsed.hostname not in {'localhost', '127.0.0.1'}:
        raise ValueError('Observer APIs require HTTPS except loopback')
    request = urllib.request.Request(url, headers={'Authorization': authorization,
                                                  'Accept': 'application/json',
                                                  'User-Agent': 'webtech-delivery-observer'})
    with urllib.request.urlopen(request, timeout=10) as response:
        return json.load(response)


def main():
    os.environ['PRODUCTION_OBSERVABILITY_ENABLED'] = 'true'
    os.environ.setdefault('PRODUCTION_EVENT_LOG_GROUP', '/webtech/production/pipeline-events')
    state_path = Path(os.getenv('OBSERVER_STATE', 'observer-state.json'))
    state = json.loads(state_path.read_text()) if state_path.exists() else {}

    def changed(key, outcome, **fields):
        if state.get(key) != outcome and emit(key, outcome, **fields):
            state[key] = outcome

    healthy = True
    try:
        token = base64.b64encode((os.environ['JENKINS_USER'] + ':' + os.environ['JENKINS_TOKEN']).encode()).decode()
        job = os.environ['JENKINS_JOB_URL'].rstrip('/')
        payload = get(job + '/api/json?tree=builds[number,building,result,timestamp,duration,url]{0,30}', 'Basic ' + token)
        for build in payload.get('builds', []):
            overdue = build['building'] and time.time() * 1000 - build['timestamp'] > 185 * 60 * 1000
            changed('observer.jenkins.' + str(build['number']),
                    ('overdue' if overdue else 'running') if build['building'] else str(build['result']).lower(),
                    source='jenkins', build_number=build['number'], duration_ms=build['duration'],
                    evidence_url=build['url'])
        emit('production.observer.jenkins', 'succeeded', environment='production')
    except (OSError, ValueError, KeyError, TypeError, HTTPException) as exc:
        healthy = False
        emit('production.observer.jenkins', 'failed', environment='production', error_type=type(exc).__name__)
    try:
        repo = os.environ['GITHUB_REPOSITORY']
        auth = 'Bearer ' + os.environ['GITHUB_OBSERVER_TOKEN']
        runs = get(f'https://api.github.com/repos/{repo}/actions/runs?branch=main&per_page=20', auth)
        for run in runs.get('workflow_runs', []):
            jobs = get(f'https://api.github.com/repos/{repo}/actions/runs/{run["id"]}/jobs?per_page=100', auth)
            for job in jobs.get('jobs', []):
                name = job['name'].lower()
                if 'staging' in name:
                    continue
                changed('observer.github.' + str(job['id']), job.get('conclusion') or job['status'],
                        source='github', environment='production' if 'production' in name else 'shared',
                        workflow_run_id=run['id'], job_id=job['id'], commit_sha=run['head_sha'],
                        evidence_url=job['html_url'], job_name=job['name'])
        emit('production.observer.github', 'succeeded', environment='production')
    except (OSError, ValueError, KeyError, TypeError, HTTPException) as exc:
        healthy = False
        emit('production.observer.github', 'failed', environment='production', error_type=type(exc).__name__)
    state_path.write_text(json.dumps(state))
    raise SystemExit(0 if healthy else 1)


if __name__ == '__main__':
    main()
