"""Failure-path validation for production telemetry and isolated pool instrumentation."""
import contextlib
import importlib.util
import io
import json
import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]


class DeliveryEventsTest(unittest.TestCase):
    def test_source_identifiers_override_defaults(self):
        from telemetry.events import emit
        with tempfile.TemporaryDirectory() as temp, patch.dict(os.environ,
                {'PRODUCTION_OBSERVABILITY_ENABLED': 'true'}, clear=True), \
                patch('telemetry.events.deliver', return_value=False), \
                patch('telemetry.events.Path', side_effect=lambda name: Path(temp) / name), \
                contextlib.redirect_stdout(io.StringIO()) as output:
            emit('codebuild.accepted', 'succeeded', codebuild_id='builder:123', commit_sha='a' * 40)
        payload = json.loads(output.getvalue())
        self.assertEqual(payload['codebuild_id'], 'builder:123')
        self.assertEqual(payload['commit_sha'], 'a' * 40)

    def test_disabled_emitter_does_not_write_or_contact_aws(self):
        from telemetry.events import emit
        with patch.dict(os.environ, {}, clear=True), patch('subprocess.run') as run, \
                patch('pathlib.Path.open') as write:
            emit('test', 'failed')
        run.assert_not_called()
        write.assert_not_called()

    def test_aws_export_failure_does_not_hide_stage_failure(self):
        script = ROOT / 'ci/telemetry/events.py'
        with tempfile.TemporaryDirectory() as work:
            result = subprocess.run([sys.executable, str(script), 'run', 'scan-gate',
                                     sys.executable, '-c', 'raise SystemExit(7)'], cwd=work,
                                    env=dict(os.environ, PRODUCTION_OBSERVABILITY_ENABLED='true'),
                                    text=True, capture_output=True, check=False)
            self.assertEqual(result.returncode, 7)
            events = [json.loads(line) for line in (Path(work) / 'production-telemetry.jsonl').read_text().splitlines()]
            self.assertEqual([event['outcome'] for event in events], ['started', 'failed'])
            self.assertNotIn('raise SystemExit', result.stdout)


class ApplicationTelemetryTest(unittest.TestCase):
    def test_instrumented_http_exports_redacted_otlp(self):
        code = r'''
import os, threading
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
payloads = []
class Receiver(BaseHTTPRequestHandler):
    def do_POST(self):
        payloads.append(self.rfile.read(int(self.headers['Content-Length'])))
        self.send_response(200)
        self.end_headers()
    def log_message(self, *args): pass
server = ThreadingHTTPServer(('127.0.0.1', 0), Receiver)
threading.Thread(target=server.serve_forever, daemon=True).start()
os.environ.update(OBSERVABILITY_ENABLED='true', OTEL_TRACES_SAMPLER='always_on',
                  DATABASE_URL='postgresql+psycopg://unused:unused@localhost/unused',
                  OTEL_EXPORTER_OTLP_ENDPOINT=f'http://127.0.0.1:{server.server_port}')
from app.backend.main import app
from fastapi.testclient import TestClient
client = TestClient(app)  # No lifespan: this test does not connect to PostgreSQL.
result = client.get('/customer-private-value?email=customer@example.invalid')
assert result.status_code == 404
assert len(result.headers['X-Trace-ID']) == 32
from opentelemetry import trace, metrics
trace.get_tracer_provider().force_flush()
metrics.get_meter_provider().force_flush()
assert payloads
assert all(b'customer@example' not in payload and b'customer-private-value' not in payload for payload in payloads)
trace.get_tracer_provider().shutdown()
metrics.get_meter_provider().shutdown()
server.shutdown()
'''
        result = subprocess.run([sys.executable, '-c', code], cwd=ROOT, capture_output=True, text=True, timeout=30, check=False)
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        self.assertNotIn('customer@example', result.stdout)

    def load_module(self):
        spec = importlib.util.spec_from_file_location('application_telemetry', ROOT / 'app/backend/telemetry/__init__.py')
        module = importlib.util.module_from_spec(spec)
        with patch.dict(os.environ, {'OBSERVABILITY_ENABLED': 'true'}):
            spec.loader.exec_module(module)
        return module

    def test_pool_timeout_measures_wait_without_exposing_sql(self):
        from opentelemetry import trace
        from opentelemetry.sdk.metrics import MeterProvider
        from opentelemetry.sdk.metrics.export import InMemoryMetricReader
        from sqlalchemy import create_engine
        from sqlalchemy.exc import TimeoutError
        reader = InMemoryMetricReader()
        meter = MeterProvider(metric_readers=[reader]).get_meter('test')
        module = self.load_module()
        engine = create_engine('sqlite://', poolclass=module.pool_class(meter, trace.get_tracer('test')),
                               pool_size=1, max_overflow=0, pool_timeout=0.02)
        with engine.connect(), self.assertRaises(TimeoutError):
            engine.connect()
        points = {metric.name: metric.data.data_points
                  for resource in reader.get_metrics_data().resource_metrics
                  for scope in resource.scope_metrics for metric in scope.metrics}
        self.assertEqual(points['webtech.db.pool.timeouts'][0].value, 1)
        self.assertTrue(any(point.attributes['outcome'] == 'timeout' and point.sum >= .02
                            for point in points['webtech.db.pool.acquire.duration']))
        self.assertEqual(points['webtech.db.pool.acquiring'][0].value, 0)
        engine.dispose()

    def test_exception_record_omits_message_customer_data_and_source(self):
        module = self.load_module()
        with patch.object(module.logger, 'info') as output:
            try:
                raise ValueError('password=secret customer@example.com')
            except ValueError as exc:
                module.failure('database.failed', exc)
        payload = json.loads(output.call_args.args[0])
        self.assertEqual(payload['error_type'], 'ValueError')
        self.assertTrue(payload['stack'])
        self.assertNotIn('secret', output.call_args.args[0])
        self.assertNotIn('customer@', output.call_args.args[0])

    def test_staging_has_no_telemetry_side_effects(self):
        spec = importlib.util.spec_from_file_location('disabled_telemetry', ROOT / 'app/backend/telemetry/__init__.py')
        module = importlib.util.module_from_spec(spec)
        with patch.dict(os.environ, {'OBSERVABILITY_ENABLED': 'false'}):
            spec.loader.exec_module(module)
        with patch.object(module.logger, 'info') as log:
            module.record('request.completed')
        log.assert_not_called()


if __name__ == '__main__':
    unittest.main()
