"""External bounded checks. Writes require explicit opt-in and a cleanup reference."""
import argparse
import json
import os
import time
import urllib.request
import uuid
from http.client import HTTPException
from urllib.parse import urlsplit

from telemetry.events import emit


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--url', required=True)
    parser.add_argument('--submit-once', action='store_true')
    parser.add_argument('--cleanup-reference', help='Approved cleanup procedure/ticket before creating synthetic data')
    args = parser.parse_args()
    parsed = urlsplit(args.url)
    if parsed.scheme != 'https' or parsed.username or parsed.password or parsed.query or parsed.fragment:
        parser.error('Use the production HTTPS origin without credentials, query or fragment')
    if args.submit_once and not args.cleanup_reference:
        parser.error('--submit-once requires --cleanup-reference')
    os.environ['PRODUCTION_OBSERVABILITY_ENABLED'] = 'true'
    trace = uuid.uuid4().hex
    headers = {'traceparent': f'00-{trace}-{uuid.uuid4().hex[:16]}-01',
               'User-Agent': 'webtech-production-synthetic/1'}
    probes = [(path, None, 200) for path in ('/', '/healthz', '/api/health/db')]
    if args.submit_once:
        probes.append(('/api/enquiries', json.dumps({'name': 'Observability Synthetic',
                                                     'email': 'synthetic@example.com'}).encode(), 201))
    failed = False
    for route, body, expected in probes:
        start = time.monotonic()
        outcome = 'failed'
        status = None
        try:
            request = urllib.request.Request(args.url.rstrip('/') + route, data=body,
                                            headers=dict(headers, **{'Content-Type': 'application/json'}))
            with urllib.request.urlopen(request, timeout=10) as response:
                status = response.status
                payload = response.read(65536)
                if status != expected:
                    raise ValueError('unexpected status')
                if body is not None and 'received' not in json.loads(payload).get('message', '').lower():
                    raise ValueError('unexpected response')
            outcome = 'succeeded'
        except (OSError, ValueError, HTTPException):
            failed = True
        emit('production.synthetic', outcome, environment='production', route=route,
             status=status, trace_id=trace, duration_ms=round((time.monotonic() - start) * 1000))
    raise SystemExit(1 if failed else 0)


if __name__ == '__main__':
    main()
