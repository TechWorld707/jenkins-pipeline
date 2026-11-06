"""Protect the private-CA input contract without admitting credentials into CI variables."""
import json
import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

SCRIPT = Path(__file__).resolve().parents[1] / '.github/scripts/production_telemetry_inputs.py'


class PrivateTelemetryInputsTest(unittest.TestCase):
    def invoke(self, config):
        with tempfile.TemporaryDirectory() as work:
            root = Path(work) / 'infra/terraform/environments/production'
            root.mkdir(parents=True)
            result = subprocess.run([sys.executable, str(SCRIPT)], cwd=work,
                                    env={**os.environ, 'STACK': 'production',
                                         'PRODUCTION_TELEMETRY_JSON': json.dumps(config),
                                         'PRODUCTION_MONITORING_RUNTIME_EXPECTED': 'false'},
                                    capture_output=True, text=True, check=False)
            output = root / 'observability.auto.tfvars.json'
            return result.returncode, json.loads(output.read_text()) if output.exists() else None

    def test_private_ca_boolean_is_preserved(self):
        config = dict(metrics_url='https://10.20.1.20/api/v1/write', tempo_url='https://10.20.1.20',
                      auth_secret_arn='arn:aws:secretsmanager:eu-west-2:671662643382:secret:test',
                      use_private_ca=True)
        code, output = self.invoke(config)
        self.assertEqual(code, 0)
        self.assertIs(output['production_telemetry']['use_private_ca'], True)

    def test_string_boolean_and_secret_values_are_rejected(self):
        config = dict(metrics_url='https://example.com/api/v1/write', tempo_url='https://example.com',
                      auth_secret_arn='arn:aws:secretsmanager:eu-west-2:671662643382:secret:test')
        for extra in ({'use_private_ca': 'true'}, {'metrics_authorization': 'secret'}):
            with self.subTest(extra=tuple(extra)):
                code, output = self.invoke(dict(config, **extra))
                self.assertNotEqual(code, 0)
                self.assertIsNone(output)
