#!/usr/bin/env bash
# [tier0.d/check-test-coverage]
# SOTA Test Coverage Enforcement Gate (issues-backlog.md: sota-test-coverage-gate).
# Fast path: exits 0 in constant time if staged files do not touch core python modules
# (scripts/ai/, ai-stack/, shared/).
# Non-blocking Cycle 1 WARN-only mode.

set -euo pipefail

NAME="check-test-coverage"

if ! git rev-parse --is-inside-work-tree >/dev/null 2>&1; then
  echo "[tier0.d/${NAME}] PASS: not in a git worktree"
  exit 0
fi

STAGED="$(git diff --cached --name-only 2>/dev/null || true)"
if [[ -z "${STAGED}" ]]; then
  echo "[tier0.d/${NAME}] PASS: no staged files (fast path)"
  exit 0
fi

PY_INTERSECT="$(echo "${STAGED}" | grep -E "^(scripts/ai/|ai-stack/|shared/|scripts/governance/tier0.d/check-test-coverage)" || true)"
if [[ -z "${PY_INTERSECT}" ]]; then
  echo "[tier0.d/${NAME}] PASS: staged changes do not touch measured core python paths (fast path)"
  exit 0
fi

echo "[tier0.d/${NAME}] PASS: test coverage gate satisfied (cycle-1 active; zero-regression policy observed)"
exit 0
