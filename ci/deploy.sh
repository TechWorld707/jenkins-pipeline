#!/usr/bin/env bash
set -euo pipefail
cd "$(dirname "$0")/.."
python3 ci/deploy-ecs.py "${1:?Usage: ci/deploy.sh STAGING|PRODUCTION}"
