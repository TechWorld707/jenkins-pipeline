"""Pass non-secret production observability settings into the saved Terraform plan."""
import json
import os
from pathlib import Path

if os.environ.get('STACK') == 'production':
    settings = {}
    raw = os.getenv('PRODUCTION_TELEMETRY_JSON', '').strip()
    if raw:
        config = json.loads(raw)
        required = {'metrics_url', 'tempo_url', 'auth_secret_arn'}
        allowed = required | {'collector_image'}
        if not isinstance(config, dict) or not required <= config.keys() or not config.keys() <= allowed:
            raise SystemExit('PRODUCTION_TELEMETRY_JSON must contain endpoint URLs and secret ARN only, plus optional collector_image')
        if not all(isinstance(value, str) for value in config.values()):
            raise SystemExit('Production telemetry settings must be strings; never supply secret values')
        settings['production_telemetry'] = config
    expected = os.getenv('PRODUCTION_MONITORING_RUNTIME_EXPECTED', '') or 'false'
    if expected not in {'true', 'false'}:
        raise SystemExit('PRODUCTION_MONITORING_RUNTIME_EXPECTED must be true or false')
    settings['monitoring_runtime_expected'] = expected == 'true'
    path = Path('infra/terraform/environments/production/observability.auto.tfvars.json')
    path.write_text(json.dumps(settings))
    path.chmod(0o600)
