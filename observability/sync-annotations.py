"""Copy safe production deployment events into Grafana's supported annotations API."""
import json
import os
import subprocess
import time
import urllib.request
from pathlib import Path


def main():
    url = os.environ['GRAFANA_URL'].rstrip('/')
    if not url.startswith('https://') and not url.startswith('http://127.0.0.1:'):
        raise SystemExit('Grafana must use HTTPS except local validation')
    state_path = Path(os.getenv('ANNOTATION_STATE', 'annotation-state.json'))
    state = json.loads(state_path.read_text()) if state_path.exists() else {}
    # First run reads the last hour. Re-reading a small window handles eventual delivery.
    start = max(0, state.get('last_timestamp', int(time.time() * 1000)) - 3600000)
    response = json.loads(subprocess.check_output([
        'aws', 'logs', 'filter-log-events', '--region', 'eu-west-2',
        '--log-group-name', '/webtech/production/pipeline-events', '--start-time', str(start),
        '--filter-pattern', '{ $.stage = "production.deploy" }', '--output', 'json'], timeout=30))
    delivered = set(state.get('event_ids', []))
    watermark = state.get('last_timestamp', start)
    for event in sorted(response.get('events', []), key=lambda item: item['timestamp']):
        record = json.loads(event['message'])
        if record['event_id'] in delivered:
            continue
        payload = {'dashboardUID': 'webtech-production', 'time': event['timestamp'],
                   'tags': ['production', 'deployment', record['outcome']],
                   'text': 'Commit ' + record.get('commit_sha', 'unknown') + ': ' + record['outcome']}
        request = urllib.request.Request(url + '/api/annotations', data=json.dumps(payload).encode(),
            headers={'Authorization': 'Bearer ' + os.environ['GRAFANA_TOKEN'], 'Content-Type': 'application/json'})
        with urllib.request.urlopen(request, timeout=10) as result:
            if result.status not in {200, 201}:
                raise RuntimeError('Annotation rejected')
        delivered.add(record['event_id'])
        watermark = max(watermark, event['timestamp'])
        state_path.write_text(json.dumps({'last_timestamp': watermark, 'event_ids': sorted(delivered)}))


if __name__ == '__main__':
    main()
