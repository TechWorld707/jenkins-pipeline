"""Independent instance-side checks: do not log response bodies, credentials, or customer data."""
import json
import ssl
import subprocess
import time
import urllib.request
from pathlib import Path


def main():
    healthy = 1
    for url in ('http://127.0.0.1:9090/-/ready', 'http://127.0.0.1:3200/ready', 'http://127.0.0.1:3000/api/health'):
        try:
            with urllib.request.urlopen(url, timeout=5) as response:
                if response.status != 200:
                    healthy = 0
        except (OSError, ValueError):
            healthy = 0
    # The public certificate contains no secret material.
    certificate = ssl._ssl._test_decode_cert('/srv/webtech-observability/tls/server.crt')
    days = (ssl.cert_time_to_seconds(certificate['notAfter']) - time.time()) / 86400
    token = urllib.request.Request('http://169.254.169.254/latest/api/token', method='PUT',
                                   headers={'X-aws-ec2-metadata-token-ttl-seconds': '60'})
    with urllib.request.urlopen(token, timeout=3) as response:
        metadata_token = response.read().decode()
    request = urllib.request.Request('http://169.254.169.254/latest/meta-data/instance-id',
                                     headers={'X-aws-ec2-metadata-token': metadata_token})
    with urllib.request.urlopen(request, timeout=3) as response:
        instance = response.read().decode()
    points = [{'MetricName': name, 'Value': value, 'Dimensions': [{'Name': 'InstanceId', 'Value': instance}]} for name, value in
              [('ServiceHealthy', healthy), ('CertificateDaysRemaining', days)]]
    subprocess.run(['aws', 'cloudwatch', 'put-metric-data', '--region', 'eu-west-2',
                    '--namespace', 'WebTech/MonitoringHost', '--metric-data', json.dumps(points)], check=True)
    # Local evidence contains only bounded health state, never response text.
    Path('/run/webtech-monitoring-health').write_text(str(healthy))


if __name__ == '__main__':
    main()
