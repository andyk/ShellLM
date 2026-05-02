#!/usr/bin/env bash
# Full Terminal Bench 2.0 evaluation with shelly agent.
set -euo pipefail

cd "$(dirname "$0")/.."
set -a; . .env; set +a

JOBS_DIR="${JOBS_DIR:-$(pwd)/.harbor-jobs}"
mkdir -p "$JOBS_DIR"

uvx harbor run \
  --agent-import-path harbor_shelly_agent:ShellyAgent \
  --environment-import-path harbor_shelly_environment:ShellmDockerEnvironment \
  --dataset terminal-bench@2.0 \
  --model anthropic/claude-opus-4-7 \
  --ak effort=max \
  --ak max_iterations=1000 \
  --ak docker_access=none \
  --ak inactivity_timeout=600 \
  --ae ANTHROPIC_API_KEY="$ANTHROPIC_API_KEY" \
  --ae SHELLM_NO_BANNER=1 \
  --mounts-json '[{"type":"bind","source":"/var/run/docker.sock","target":"/var/run/docker.sock"}]' \
  -o "$JOBS_DIR" \
  -n 4 \
  --max-retries 1 \
  --yes \
  "$@"
