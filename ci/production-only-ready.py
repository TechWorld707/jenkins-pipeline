"""Validate the independent production-only release; no staging evidence is fabricated."""
import hashlib
import importlib.util
import json
import os
from pathlib import Path

SPEC = importlib.util.spec_from_file_location('shared_release', Path(__file__).with_name('jenkins-release.py'))
RELEASE = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(RELEASE)


def check_ready():
    manifest = Path('release.json').read_bytes()
    expected = os.environ.get('PRODUCTION_RELEASE_HASH', '')
    if not expected or hashlib.sha256(manifest).hexdigest() != expected:
        raise SystemExit('Release manifest changed after build verification')
    release = json.loads(manifest)
    sha = os.environ.get('RELEASE_SHA', '')
    if not sha or release.get('commit') != sha:
        raise SystemExit('Release manifest commit mismatch')
    # Reuse the immutable ECR digest checks and archived HIGH/CRITICAL scan gate.
    RELEASE.verify_reused_release(release, sha)


if __name__ == '__main__':
    check_ready()
