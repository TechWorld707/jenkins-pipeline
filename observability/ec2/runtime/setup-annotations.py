"""Install a local Grafana annotation writer without exposing API credentials."""
import base64
import json
import os
import subprocess
import time
import urllib.request
from pathlib import Path


def main():
    root = Path('/srv/webtech-observability')
    credentials_path = root / 'credentials.json'
    credentials = json.loads(credentials_path.read_text())
    admin = 'Basic ' + base64.b64encode(('admin:' + credentials['grafana_admin_password']).encode()).decode()

    def api(path, payload=None):
        request = urllib.request.Request('http://127.0.0.1:3000' + path,
                                         data=None if payload is None else json.dumps(payload).encode(),
                                         headers={'Authorization': admin, 'Content-Type': 'application/json'})
        with urllib.request.urlopen(request, timeout=15) as response:
            return json.load(response)

    for attempt in range(30):
        try:
            api('/api/health')
            break
        except (OSError, ValueError):
            if attempt == 29:
                raise
            time.sleep(5)
    if not credentials.get('grafana_annotation_token'):
        name = 'webtech-deployment-annotations'
        accounts = api('/api/serviceaccounts/search?query=' + name)['serviceAccounts']
        matching = [account for account in accounts if account['name'] == name]
        account = matching[0] if matching else api('/api/serviceaccounts', {'name': name, 'role': 'Editor'})
        token = api('/api/serviceaccounts/' + str(account['id']) + '/tokens',
                    {'name': 'ec2-annotation-sync-' + str(int(time.time())), 'secondsToLive': 0})['key']
        credentials['grafana_annotation_token'] = token
        credentials_path.write_text(json.dumps(credentials))
        credentials_path.chmod(0o600)
        subprocess.run(['aws', 'secretsmanager', 'put-secret-value', '--region', 'eu-west-2',
                        '--secret-id', os.environ['CREDENTIALS_SECRET_ARN'],
                        '--secret-string', 'file://' + str(credentials_path)],
                       stdout=subprocess.DEVNULL, check=True)
    env_file = root / 'annotations.env'
    env_file.write_text('GRAFANA_URL=http://127.0.0.1:3000\nGRAFANA_TOKEN=' + credentials['grafana_annotation_token'] +
                        '\nANNOTATION_STATE=' + str(root / 'annotation-state.json') + '\n')
    env_file.chmod(0o600)
    Path('/etc/systemd/system/webtech-annotations.service').write_text('''[Unit]
Description=Sync production deployment records into Grafana
After=webtech-monitoring.service
[Service]
Type=oneshot
WorkingDirectory=/srv/webtech-observability
EnvironmentFile=/srv/webtech-observability/annotations.env
ExecStart=/usr/bin/python3 /srv/webtech-observability/sync-annotations.py
TimeoutStartSec=60
''')
    Path('/etc/systemd/system/webtech-annotations.timer').write_text('''[Unit]
Description=Sync deployment annotations every minute
[Timer]
OnBootSec=5min
OnUnitActiveSec=60s
[Install]
WantedBy=timers.target
''')
    subprocess.run(['systemctl', 'daemon-reload'], check=True)
    subprocess.run(['systemctl', 'enable', '--now', 'webtech-annotations.timer'], check=True)
    subprocess.run(['systemctl', 'start', 'webtech-annotations.service'], check=True)
    print('Deployment annotation sync installed; credentials remain server-side.')


if __name__ == '__main__':
    main()
