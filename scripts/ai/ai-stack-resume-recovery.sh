#!/usr/bin/env bash
set -euo pipefail

REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
SYSTEM_ACT="${REPO_ROOT}/scripts/ai/aq-system-act"
RUNTIME_ACT="${REPO_ROOT}/scripts/ai/aq-runtime-act"

usage() {
  cat <<'EOF'
scripts/ai/ai-stack-resume-recovery.sh

Legacy compatibility shim over current bounded runtime recovery tooling.

Usage:
  scripts/ai/ai-stack-resume-recovery.sh [--task "describe incident"] [--format json|text]
  scripts/ai/ai-stack-resume-recovery.sh --execute
  scripts/ai/ai-stack-resume-recovery.sh --help

Options:
  --task TEXT     Recovery or resume objective to classify and route.
  --format VALUE  Output format for plan mode: json or text. Default: json.
  --execute       Execute the selected bounded runtime action.
EOF
}

task="resume and recover the AI stack runtime after an incident"
fmt="json"
execute="false"

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
    --execute)
      execute="true"
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

if [[ "$execute" == "true" ]]; then
  exec python3 "$RUNTIME_ACT" --execute --brief
fi

exec python3 "$SYSTEM_ACT" \
  --task "$task" \
  --context-application ai-stack \
  --format "$fmt"
