#!/usr/bin/env bash
# Run path-aware CI-sensitive checks for changed files.
# Usage: ./scripts/governance/run-focused-ci-checks.sh [--pre-commit|--pre-deploy]

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "${SCRIPT_DIR}/../.." && pwd)"
cd "${REPO_ROOT}"

MODE="${1:---pre-commit}"

collect_changed_files() {
  if [[ "${MODE}" == "--pre-commit" ]]; then
    git diff --cached --name-only --diff-filter=ACM 2>/dev/null || true
    return 0
  fi

  {
    git diff --name-only --diff-filter=ACM origin/main...HEAD 2>/dev/null || true
    git diff --name-only --diff-filter=ACM 2>/dev/null || true
  } | awk 'NF && !seen[$0]++'
}

has_changed_path() {
  local target="$1"
  local file
  while IFS= read -r file; do
    [[ "${file}" == "${target}" ]] && return 0
  done < <(collect_changed_files)
  return 1
}

any_changed_path() {
  local target
  for target in "$@"; do
    if has_changed_path "${target}"; then
      return 0
    fi
  done
  return 1
}

run_check() {
  local description="$1"
  shift
  echo "[focused-ci] RUN: ${description}"
  "$@"
  echo "[focused-ci] PASS: ${description}"
}

ran_any=0

if has_changed_path "ai-stack/mcp-servers/hybrid-coordinator/route_handler.py"; then
  ran_any=1
  run_check \
    "hybrid coordinator route handler optimizations regression" \
    python -m pytest ai-stack/mcp-servers/hybrid-coordinator/test_route_handler_optimizations.py
fi

if any_changed_path \
  "dashboard/backend/api/main.py" \
  "dashboard/backend/api/services/ai_insights.py" \
  "scripts/testing/test-dashboard-insights-report-cache.py"
then
  ran_any=1
  run_check \
    "dashboard insights cache regression" \
    python scripts/testing/test-dashboard-insights-report-cache.py
fi

if any_changed_path \
  "config/package-count-baseline.json" \
  "scripts/data/generate-package-counts.sh" \
  "scripts/testing/check-package-count-drift.sh" \
  "flake.nix"
then
  ran_any=1
  run_check \
    "package count drift guard" \
    ./scripts/testing/check-package-count-drift.sh --flake-ref path:.
fi

if [[ "${ran_any}" -eq 0 ]]; then
  echo "[focused-ci] SKIP: no CI-sensitive changed paths detected"
fi
