"""Real PostgreSQL + FastAPI OTLP smoke test. Run only against a disposable database."""
# Configure telemetry and the disposable-database guard before application imports.
import json
import os
import sys
import threading
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

if os.environ.get('OBSERVABILITY_DISPOSABLE_DATABASE') != 'true':
    raise SystemExit('Set OBSERVABILITY_DISPOSABLE_DATABASE=true only for a disposable local database')

payloads = []


class Receiver(BaseHTTPRequestHandler):
    def do_POST(self):
        payloads.append((self.path, self.rfile.read(int(self.headers['Content-Length']))))
        self.send_response(200)
        self.end_headers()

    def log_message(self, *args):
        pass


server = ThreadingHTTPServer(('127.0.0.1', 0), Receiver)
threading.Thread(target=server.serve_forever, daemon=True).start()
os.environ.update(OBSERVABILITY_ENABLED='true', OTEL_TRACES_SAMPLER='always_on',
                  OTEL_EXPORTER_OTLP_ENDPOINT=f'http://127.0.0.1:{server.server_port}')
# Telemetry environment must be configured before application imports.
from fastapi.testclient import TestClient
from opentelemetry import metrics, trace
from opentelemetry.proto.collector.trace.v1.trace_service_pb2 import (
    ExportTraceServiceRequest,
)

from app.backend.main import app

with TestClient(app) as client:
    assert client.get('/api/health/db').status_code == 200
    response = client.post('/api/enquiries', json={'name': 'Synthetic Private Value', 'email': 'synthetic@example.com'})
    assert response.status_code == 201, response.text
    assert len(response.headers['X-Trace-ID']) == 32

trace.get_tracer_provider().force_flush()
metrics.get_meter_provider().force_flush()
traces = [ExportTraceServiceRequest.FromString(data) for path, data in payloads if path == '/v1/traces']
spans = [span for export in traces for resource in export.resource_spans for scope in resource.scope_spans for span in scope.spans]
assert any(span.name == 'database.acquire' for span in spans)
assert any(any(attribute.key == 'db.system' for attribute in span.attributes) for span in spans)
assert any(path == '/v1/metrics' for path, _ in payloads)
for _, data in payloads:
    assert b'synthetic@example.com' not in data
    assert b'Synthetic Private Value' not in data
    assert b'INSERT INTO' not in data
print(json.dumps({'validation': 'passed', 'spans_received': len(spans), 'metrics_received': True}))
trace.get_tracer_provider().shutdown()
metrics.get_meter_provider().shutdown()
server.shutdown()
