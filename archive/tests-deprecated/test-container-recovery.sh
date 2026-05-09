#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
RUNTIME_ACT="${ROOT_DIR}/scripts/ai/aq-runtime-act"
SYSTEM_ACT="${ROOT_DIR}/scripts/ai/aq-system-act"

usage() {
  cat <<'EOF'
Usage: scripts/testing/test-container-recovery.sh [--execute] [--task "incident summary"]

Compatibility shim over declarative runtime recovery tooling.
- Default: preview the next bounded recovery action
- --execute: execute the selected bounded recovery action
EOF
}

execute=false
task="resume and recover the AI stack runtime after service disruption"

while [[ $# -gt 0 ]]; do
  case "$1" in
    --execute)
      execute=true
      shift
      ;;
    --task)
      [[ $# -ge 2 ]] || { echo "--task requires a value" >&2; exit 2; }
      task="$2"
      shift 2
      ;;
    -h|--help)
      usage
      exit 0
      ;;
    *)
      echo "Unknown option: $1" >&2
      usage >&2
      exit 2
      ;;
  esac
done

echo "scripts/testing/test-container-recovery.sh is a compatibility shim over aq-runtime-act and aq-system-act." >&2
if [[ "${execute}" == true ]]; then
  exec python3 "${RUNTIME_ACT}" --execute --brief
fi

exec python3 "${SYSTEM_ACT}" --task "${task}" --context-application ai-stack --format json
