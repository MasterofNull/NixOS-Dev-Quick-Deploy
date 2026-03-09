#!/usr/bin/env bash
set -euo pipefail

REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
BOOTSTRAP_TOOL="${REPO_ROOT}/scripts/ai/aq-context-bootstrap"
WORKFLOW_SMOKE="${REPO_ROOT}/scripts/testing/test-real-world-workflows.sh"

usage() {
  cat <<'EOF'
scripts/ai/ai-stack-feature-scenario.sh

Legacy compatibility shim over current feature-planning and workflow smoke tooling.

Usage:
  scripts/ai/ai-stack-feature-scenario.sh [--task "implement feature"] [--format text|json]
  scripts/ai/ai-stack-feature-scenario.sh --smoke
  scripts/ai/ai-stack-feature-scenario.sh --help

Options:
  --task TEXT     Bootstrap a feature-development scenario for the given task.
  --format VALUE  Output format for bootstrap mode: text or json. Default: text.
  --smoke         Run the supported real-world workflow smoke test.
EOF
}

task=""
fmt="text"
smoke="false"

while [[ $# -gt 0 ]]; do
  case "$1" in
    --task)
      [[ $# -ge 2 ]] || { echo "--task requires a value" >&2; exit 1; }
      task="$2"
      shift 2
      ;;
    --format)
      [[ $# -ge 2 ]] || { echo "--format requires a value" >&2; exit 1; }
      fmt="$2"
      shift 2
      ;;
    --smoke)
      smoke="true"
      shift
      ;;
    -h|--help|help)
      usage
      exit 0
      ;;
    *)
      echo "Unknown argument: $1" >&2
      usage >&2
      exit 1
      ;;
  esac
done

if [[ "$smoke" == "true" ]]; then
  exec "$WORKFLOW_SMOKE"
fi

if [[ -z "$task" ]]; then
  task="resume the next validated AI stack feature slice"
fi

exec python3 "$BOOTSTRAP_TOOL" \
  --task "$task" \
  --scope feature-development \
  --context-application ai-stack \
  --format "$fmt"
