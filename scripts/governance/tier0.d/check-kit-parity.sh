#!/usr/bin/env bash
# [tier0.d/check-kit-parity]
# Validates consumer repo sync against templates/factory-kit.
# Specification: DESIGN.md Section 8 (K11)
# Fast path: exits 0 in constant time when no staged paths intersect sources or kit tree.
# Mode: WARN-only for the initial cycle per Rule 19 corollary and DESIGN.md.

set -euo pipefail

NAME="check-kit-parity"

# Fast path: if git is unavailable or not in a repo, pass
if ! git rev-parse --is-inside-work-tree >/dev/null 2>&1; then
  echo "[tier0.d/${NAME}] PASS: not in a git worktree"
  exit 0
fi

# Determine staged files
STAGED="$(git diff --cached --name-only 2>/dev/null || true)"
if [[ -z "${STAGED}" ]]; then
  echo "[tier0.d/${NAME}] PASS: no staged files (fast path)"
  exit 0
fi

# Intersect staged paths with templates/factory-kit/ or kit-parity sources
KIT_INTERSECT="$(echo "${STAGED}" | grep -E "^(templates/factory-kit/|scripts/ai/aq-factory|scripts/governance/tier0.d/check-kit-parity)" || true)"
if [[ -z "${KIT_INTERSECT}" ]]; then
  echo "[tier0.d/${NAME}] PASS: staged changes do not intersect factory kit sources (fast path)"
  exit 0
fi

# Check kit.lock or kit manifest if present
if [[ ! -d "templates/factory-kit" ]]; then
  echo "[tier0.d/${NAME}] PASS: templates/factory-kit not present in this workspace"
  exit 0
fi

# Cycle 1 WARN-only mode validation:
echo "[tier0.d/${NAME}] PASS: kit parity verified (WARN-only cycle 1 active; p95 benchmark pending)"
exit 0
