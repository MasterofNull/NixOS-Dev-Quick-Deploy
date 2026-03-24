#!/usr/bin/env bash
# Reconcile hosted GitHub code scanning by exporting, removing stale analyses, and exporting again.
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
APPLY=false
SHOW_SUMMARY=true

usage() {
  cat <<'EOF'
Usage: scripts/security/reconcile-github-code-scanning.sh [options]

Reconcile hosted GitHub code scanning after a workflow run by:
1. exporting the current backlog snapshot,
2. deleting stale deletable analyses whose categories no longer exist,
3. exporting a fresh snapshot again,
4. printing summary and delta output.

Options:
  --apply       Delete stale analyses instead of dry-run only
  --no-summary  Skip summary and delta output
  -h, --help    Show this help text
EOF
}

while [[ $# -gt 0 ]]; do
  case "$1" in
    --apply)
      APPLY=true
      shift
      ;;
    --no-summary)
      SHOW_SUMMARY=false
      shift
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

require_cmd() {
  command -v "$1" >/dev/null 2>&1 || {
    echo "Missing required command: $1" >&2
    exit 2
  }
}

require_cmd bash

echo "Exporting pre-reconciliation snapshot"
bash "${ROOT_DIR}/scripts/security/export-github-code-scanning-alerts.sh"

cleanup_args=()
if [[ "${APPLY}" == true ]]; then
  cleanup_args+=(--apply)
fi

echo "Reconciling stale analyses"
bash "${ROOT_DIR}/scripts/security/cleanup-stale-code-scanning-analyses.sh" "${cleanup_args[@]}"

echo "Exporting post-reconciliation snapshot"
bash "${ROOT_DIR}/scripts/security/export-github-code-scanning-alerts.sh"

if [[ "${SHOW_SUMMARY}" == true ]]; then
  bash "${ROOT_DIR}/scripts/security/summarize-github-code-scanning-alerts.sh"
  bash "${ROOT_DIR}/scripts/security/compare-github-code-scanning-alerts.sh"
fi
