"""Bounded, best-effort production/shared delivery events; no command text or errors exported."""
import json
import os
import subprocess
import sys
import time
import uuid
from datetime import datetime, timezone
from pathlib import Path


def emit(stage, outcome, **fields):
    if os.getenv('PRODUCTION_OBSERVABILITY_ENABLED', '').lower() != 'true':
        return
    event = {'schema_version': 1, 'timestamp': datetime.now(timezone.utc).isoformat(),  # noqa: UP017 - Jenkins may use Python 3.10
                 'event_id': uuid.uuid4().hex, 'service': 'delivery',
                 'environment': fields.pop('environment', 'shared'), 'stage': stage,
                 'outcome': outcome, 'pipeline_run_id': os.getenv('PIPELINE_RUN_ID', os.getenv('BUILD_TAG', 'unknown')),
                 'commit_sha': os.getenv('RELEASE_SHA', os.getenv('EXPECTED_COMMIT', 'unknown')),
                 'codebuild_id': os.getenv('CODEBUILD_BUILD_ID', '')}
    event.update(fields)
    data = json.dumps(event, separators=(',', ':'))
    print(data, flush=True)
    try:
        with Path('production-telemetry.jsonl').open('a') as output:
            output.write(data + '\n')
    except OSError:
        pass
    if deliver(event):
        try:
            with Path('production-telemetry.sent').open('a') as output:
                output.write(event['event_id'] + '\n')
        except OSError:
            pass
        return True
    return False


def deliver(event):
    group = os.getenv('PRODUCTION_EVENT_LOG_GROUP')
    if not group:
        return False
    # One stable stream per run; CloudWatch no longer requires sequence tokens.
    import hashlib
    stream = hashlib.sha256(event['pipeline_run_id'].encode()).hexdigest()
    try:
        common = ['--region', 'eu-west-2', '--cli-connect-timeout', '2', '--cli-read-timeout', '3']
        subprocess.run(['aws', 'logs', 'create-log-stream', '--log-group-name', group,
                        '--log-stream-name', stream, *common], stdout=subprocess.DEVNULL,
                       stderr=subprocess.DEVNULL, timeout=6, check=False)
        subprocess.run(['aws', 'logs', 'put-log-events', '--log-group-name', group,
                        '--log-stream-name', stream, '--log-events', json.dumps([
                            {'timestamp': int(datetime.fromisoformat(event['timestamp']).timestamp() * 1000),
                             'message': json.dumps(event, separators=(',', ':'))}]), *common],
                       stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, timeout=6, check=True)
        return True
    except (OSError, subprocess.SubprocessError):
        print(json.dumps({'event': 'telemetry.export.failed', 'service': 'delivery'}), file=sys.stderr)
        return False


if __name__ == '__main__':
    if sys.argv[1] == 'flush':
        sent_file = Path('production-telemetry.sent')
        sent = set(sent_file.read_text().splitlines()) if sent_file.exists() else set()
        spool = Path('production-telemetry.jsonl')
        if spool.exists():
            for line in spool.read_text().splitlines():
                event = json.loads(line)
                if event['event_id'] not in sent and deliver(event):
                    with sent_file.open('a') as output:
                        output.write(event['event_id'] + '\n')
        raise SystemExit(0)
    if sys.argv[1] == 'run':
        stage = sys.argv[2]
        emit(stage, 'started')
        start = time.monotonic()
        result = subprocess.run(sys.argv[3:], check=False)
        emit(stage, 'succeeded' if result.returncode == 0 else 'failed',
             exit_code=result.returncode, duration_ms=round((time.monotonic() - start) * 1000))
        raise SystemExit(result.returncode)
    fields = {}
    if sys.argv[1] == 'production.approval':
        if os.getenv('PRODUCTION_APPROVAL_STARTED'):
            fields['wait_seconds'] = round(time.time() - float(os.environ['PRODUCTION_APPROVAL_STARTED']))
        if os.getenv('PRODUCTION_APPROVER'):
            fields['approved_by'] = os.environ['PRODUCTION_APPROVER']
    if sys.argv[1].startswith('production.') or sys.argv[1] == 'pipeline.finished':
        manifest = Path('release.json')
        if manifest.exists():
            try:
                import hashlib
                fields['release_manifest_sha256'] = hashlib.sha256(manifest.read_bytes()).hexdigest()
                fields['image_digests'] = json.loads(manifest.read_text())['images']
            except (OSError, KeyError, ValueError):
                pass
    emit(sys.argv[1], sys.argv[2], environment='production' if sys.argv[1].startswith('production') else 'shared', **fields)
