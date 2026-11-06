#!/usr/bin/env bash
set -euo pipefail
repo_root=$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")/../.." && pwd)
instance_id=${1:-$(terraform -chdir="$repo_root/infra/terraform/monitoring" output -raw instance_id)}
local_port=${2:-13000}
if [[ ! "$instance_id" =~ ^i-[a-f0-9]+$ ]] || [[ ! "$local_port" =~ ^[0-9]+$ ]] || ((local_port < 1024 || local_port > 65535)); then
  echo 'Usage: bash observability/ec2/open-grafana.sh [instance-id] [local-port:1024-65535]' >&2
  exit 1
fi
if ! command -v session-manager-plugin >/dev/null && [[ -x "$HOME/.local/bin/session-manager-plugin" ]]; then
  export PATH="$HOME/.local/bin:$PATH"
fi
if ! command -v session-manager-plugin >/dev/null; then
  echo 'Install the AWS Session Manager plugin first:' >&2
  echo 'https://docs.aws.amazon.com/systems-manager/latest/userguide/install-plugin-debian-and-ubuntu.html' >&2
  exit 1
fi
echo "Open http://127.0.0.1:$local_port and keep this terminal open. Press Ctrl+C to close the tunnel."
exec aws ssm start-session --region eu-west-2 --target "$instance_id" \
  --document-name AWS-StartPortForwardingSession \
  --parameters "{\"portNumber\":[\"3000\"],\"localPortNumber\":[\"$local_port\"]}"
