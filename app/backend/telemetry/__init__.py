"""Production-only telemetry. No exporters or changed pool defaults in other environments."""
import json
import logging
import os
import re
import time
import traceback
import uuid
from datetime import datetime, timezone

UTC = timezone.utc  # noqa: UP017 - also support Python 3.10 validation hosts

ENABLED = os.getenv('OBSERVABILITY_ENABLED') == 'true'
logger = logging.getLogger('webtech.events')


def record(event, **fields):
    if not ENABLED:
        return
    from opentelemetry import trace
    context = trace.get_current_span().get_span_context()
    payload = dict(timestamp=datetime.now(UTC).isoformat(), service='backend',
                   environment='production', version=os.getenv('RELEASE_SHA', 'unknown'),
                   level='ERROR' if 'error_type' in fields else 'INFO', message=event,
                   event=event, **fields)
    if context.is_valid:
        payload['trace_id'] = format(context.trace_id, '032x')
    logger.info(json.dumps(payload))


def failure(event, exc):
    # Exception text, SQL parameters, local variables and source lines can contain PII.
    frames = traceback.extract_tb(exc.__traceback__)
    record(event, error_type=type(exc).__name__,
           stack=[{'file': os.path.basename(f.filename), 'line': f.lineno,
                   'function': f.name} for f in frames])


def configure():
    from opentelemetry import metrics, trace
    from opentelemetry.exporter.otlp.proto.http.metric_exporter import (
        OTLPMetricExporter,
    )
    from opentelemetry.exporter.otlp.proto.http.trace_exporter import OTLPSpanExporter
    from opentelemetry.sdk.metrics import MeterProvider
    from opentelemetry.sdk.metrics.export import PeriodicExportingMetricReader
    from opentelemetry.sdk.metrics.view import (
        DropAggregation,
        ExplicitBucketHistogramAggregation,
        View,
    )
    from opentelemetry.sdk.resources import Resource
    from opentelemetry.sdk.trace import ReadableSpan, TracerProvider
    from opentelemetry.sdk.trace.export import BatchSpanProcessor, SpanExporter

    handler = logging.StreamHandler()
    handler.setFormatter(logging.Formatter('%(message)s'))
    logger.handlers = [handler]
    logger.propagate = False
    logger.setLevel(logging.INFO)
    logging.getLogger('uvicorn.access').disabled = True

    class RuntimeFormatter(logging.Formatter):
        def format(self, entry):
            payload = {'timestamp': datetime.now(UTC).isoformat(), 'service': 'backend',
                       'environment': 'production', 'level': entry.levelname,
                       'event': 'runtime.log', 'logger': entry.name}
            if entry.exc_info:
                payload['error_type'] = entry.exc_info[0].__name__
                payload['stack'] = [{'file': os.path.basename(f.filename), 'line': f.lineno,
                                     'function': f.name} for f in traceback.extract_tb(entry.exc_info[2])]
            return json.dumps(payload)
    runtime_handler = logging.StreamHandler()
    runtime_handler.setFormatter(RuntimeFormatter())
    for name in ('uvicorn', 'uvicorn.error', 'sqlalchemy', ''):
        runtime_logger = logging.getLogger(name)
        runtime_logger.handlers = [runtime_handler]
        runtime_logger.propagate = False
    resource = Resource.create({'service.name': 'webtech-backend',
                                'deployment.environment': 'production',
                                'service.instance.id': uuid.uuid4().hex,
                                'service.version': os.getenv('RELEASE_SHA', 'unknown')})

    class SafeExporter(SpanExporter):
        def __init__(self):
            self.delegate = OTLPSpanExporter(timeout=3)

        def export(self, spans):
            allowed = {'http.method', 'http.status_code', 'http.route',
                       'http.request.method', 'http.response.status_code',
                       'db.system', 'db.operation', 'db.name', 'pool.outcome',
                       'pipeline_run_id', 'synthetic'}
            safe = []
            for span in spans:
                # No SQL text, URLs, headers, exception messages or instrumentation events.
                safe.append(ReadableSpan(
                    name=span.attributes.get('http.route', 'http.request') if '/' in span.name else span.name,
                    context=span.context, parent=span.parent,
                    resource=span.resource, attributes={k: v for k, v in span.attributes.items()
                                                        if k in allowed},
                    events=(), links=(), kind=span.kind,
                    status=__import__('opentelemetry.trace', fromlist=['Status']).Status(span.status.status_code),
                    start_time=span.start_time, end_time=span.end_time))
            return self.delegate.export(safe)

        def shutdown(self):
            self.delegate.shutdown()

    provider = TracerProvider(resource=resource)
    provider.add_span_processor(BatchSpanProcessor(SafeExporter(), max_queue_size=2048))
    trace.set_tracer_provider(provider)
    metric_resource = Resource({k: v for k, v in resource.attributes.items() if k != 'service.version'})
    metrics.set_meter_provider(MeterProvider(resource=metric_resource, views=[
        View(instrument_name='http.server.*', aggregation=DropAggregation()),
        View(instrument_name='webtech.http.request.duration', aggregation=ExplicitBucketHistogramAggregation(
            boundaries=(0.005, 0.01, 0.025, 0.05, 0.1, 0.25, 0.5, 1, 2.5, 5, 10, 30))),
        View(instrument_name='webtech.db.pool.acquire.duration', aggregation=ExplicitBucketHistogramAggregation(
            boundaries=(0.001, 0.005, 0.01, 0.05, 0.1, 0.5, 1, 2, 5, 10)))], metric_readers=[
        PeriodicExportingMetricReader(OTLPMetricExporter(timeout=3), export_interval_millis=30000)]))
    return metrics.get_meter('webtech'), trace.get_tracer('webtech')


def pool_class(meter, tracer):
    from sqlalchemy.pool import QueuePool
    wait = meter.create_histogram('webtech.db.pool.acquire.duration', unit='s')
    timeouts = meter.create_counter('webtech.db.pool.timeouts')
    timeouts.add(0)
    acquiring = meter.create_up_down_counter('webtech.db.pool.acquiring')

    class MeasuredPool(QueuePool):
        def _do_get(self):
            start = time.monotonic()
            acquiring.add(1)
            # This boundary includes waiting before SQLAlchemy's checkout event.
            with tracer.start_as_current_span('database.acquire', record_exception=False,
                                               set_status_on_exception=False) as span:
                outcome = 'success'
                try:
                    return super()._do_get()
                except Exception as exc:
                    from opentelemetry.trace import Status, StatusCode
                    from sqlalchemy.exc import TimeoutError
                    outcome = 'timeout' if isinstance(exc, TimeoutError) else 'error'
                    if outcome == 'timeout':
                        timeouts.add(1)
                    span.set_status(Status(StatusCode.ERROR))
                    failure('database.acquire.failed', exc)
                    raise
                finally:
                    acquiring.add(-1)
                    span.set_attribute('pool.outcome', outcome)
                    wait.record(time.monotonic() - start, {'outcome': outcome})
    return MeasuredPool


def instrument(app, engine, meter):
    from opentelemetry import metrics
    from opentelemetry.instrumentation.fastapi import FastAPIInstrumentor
    from opentelemetry.instrumentation.sqlalchemy import SQLAlchemyInstrumentor
    SQLAlchemyInstrumentor().instrument(engine=engine, enable_commenter=False)
    # Custom request metrics are the canonical dashboard source; do not also
    # scrape a Prometheus endpoint or add another HTTP metrics middleware.
    total = meter.create_counter('webtech.http.requests')
    duration = meter.create_histogram('webtech.http.request.duration', unit='s')
    active = meter.create_up_down_counter('webtech.http.active_requests')
    for name, callback in [('in_use', engine.pool.checkedout), ('idle', engine.pool.checkedin)]:
        meter.create_observable_gauge('webtech.db.pool.' + name,
                                      callbacks=[lambda options, f=callback: [metrics.Observation(f())]])

    @app.middleware('http')
    async def request_record(request, call_next):
        start = time.monotonic()
        supplied_id = request.headers.get('x-request-id', '')
        request_id = supplied_id if re.fullmatch('[0-9a-f]{32}', supplied_id) else uuid.uuid4().hex
        active.add(1)
        status = 500
        try:
            response = await call_next(request)
            status = response.status_code
            response.headers['X-Request-ID'] = request_id
            from opentelemetry import trace
            context = trace.get_current_span().get_span_context()
            if context.is_valid:
                response.headers['X-Trace-ID'] = format(context.trace_id, '032x')
            return response
        except Exception as exc:
            failure('request.failed', exc)
            raise
        finally:
            elapsed = time.monotonic() - start
            route = getattr(request.scope.get('route'), 'path', 'unmatched')
            labels = {'route': route, 'method': request.method if request.method in
                      {'GET', 'POST', 'HEAD', 'OPTIONS', 'PUT', 'DELETE', 'PATCH'} else 'OTHER',
                      'status': str(status)}
            total.add(1, labels)
            duration.record(elapsed, labels)
            active.add(-1)
            record('request.completed', request_id=request_id, duration_ms=round(elapsed * 1000), **labels)

    # OpenTelemetry must be outside the request logger so its active server span
    # exists while logs are emitted and response correlation headers are set.
    FastAPIInstrumentor.instrument_app(app, excluded_urls='healthz')
