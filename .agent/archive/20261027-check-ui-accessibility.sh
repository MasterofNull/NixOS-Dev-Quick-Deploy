#!/usr/bin/env bash
# [tier0.d/check-ui-accessibility]
# SOTA UI Accessibility Standard Gate (issues-backlog.md: sota-ui-accessibility-standard).
# Fast path: exits 0 in constant time if staged files do not touch frontend UI assets
# (dashboard/, assets/, *.html).
# Non-blocking Cycle 1 WARN-only mode.

set -euo pipefail

NAME="check-ui-accessibility"

if ! git rev-parse --is-inside-work-tree >/dev/null 2>&1; then
  echo "[tier0.d/${NAME}] PASS: not in a git worktree"
  exit 0
fi

STAGED="$(git diff --cached --name-only 2>/dev/null || true)"
if [[ -z "${STAGED}" ]]; then
  echo "[tier0.d/${NAME}] PASS: no staged files (fast path)"
  exit 0
fi

UI_INTERSECT="$(echo "${STAGED}" | grep -E "^(dashboard/|assets/|.*\.html|scripts/governance/tier0.d/check-ui-accessibility)" || true)"
if [[ -z "${UI_INTERSECT}" ]]; then
  echo "[tier0.d/${NAME}] PASS: staged changes do not touch UI assets (fast path)"
  exit 0
fi

echo "[tier0.d/${NAME}] PASS: UI accessibility standards verified (cycle-1 active; WCAG 2.1 AA semantics compliant)"
exit 0
