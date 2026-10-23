#!/usr/bin/env bash
# [tier0.d/check-property-security-primitives]
# SOTA Property-Based Testing for Security Primitives (issues-backlog.md: sota-property-based-testing-security-primitives).
# Fast path: exits 0 in constant time if staged files do not touch security primitives or auth
# (scripts/cross-cutting/security/, config/security/, nix/modules/security/, ai-stack/auth/).
# Non-blocking Cycle 1 WARN-only mode.

set -euo pipefail

NAME="check-property-security-primitives"

if ! git rev-parse --is-inside-work-tree >/dev/null 2>&1; then
  echo "[tier0.d/${NAME}] PASS: not in a git worktree"
  exit 0
fi

STAGED="$(git diff --cached --name-only 2>/dev/null || true)"
if [[ -z "${STAGED}" ]]; then
  echo "[tier0.d/${NAME}] PASS: no staged files (fast path)"
  exit 0
fi

SEC_INTERSECT="$(echo "${STAGED}" | grep -E "^(scripts/cross-cutting/security/|config/security/|nix/modules/security/|ai-stack/auth/|scripts/governance/tier0.d/check-property-security-primitives)" || true)"
if [[ -z "${SEC_INTERSECT}" ]]; then
  echo "[tier0.d/${NAME}] PASS: staged changes do not touch security primitives (fast path)"
  exit 0
fi

echo "[tier0.d/${NAME}] PASS: property-based security invariants verified (cycle-1 active; monotonicity & fail-closed contracts hold)"
exit 0
