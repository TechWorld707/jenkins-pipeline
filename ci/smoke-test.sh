#!/usr/bin/env bash
set -euo pipefail
base_url="${1:?Usage: ci/smoke-test.sh https://environment-url}"
for endpoint in / /healthz /api/health/db; do
  curl --fail --silent --show-error --retry 12 --retry-all-errors \
    --retry-delay 5 --connect-timeout 10 --max-time 20 "${base_url%/}${endpoint}" > /dev/null
done
