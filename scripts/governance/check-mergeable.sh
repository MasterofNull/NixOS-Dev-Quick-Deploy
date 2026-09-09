#!/usr/bin/env bash
# Shallow-merge guard — reusable core.
#
# A shallow clone (`git rev-parse --is-shallow-repository` == true) truncates
# history, so `git merge-base` cannot find a common ancestor between branches
# that actually share one. Merging under that condition produces a garbage
# DISJOINT merge (git treats unrelated-looking branches as unrelated histories)
# that can corrupt trunk. This script blocks that scenario before it happens.
#
# Usage: check-mergeable.sh [<branch-to-merge>]
#   No arg   — only checks whether the current repo is shallow.
#   With arg — additionally verifies HEAD and <branch-to-merge> share a
#              merge-base (i.e. the merge would be a real, related-history merge).
set -euo pipefail

REPO_ROOT="$(git rev-parse --show-toplevel)"
cd "${REPO_ROOT}"

BRANCH="${1:-}"

if [[ "$(git rev-parse --is-shallow-repository)" == "true" ]]; then
  echo "[check-mergeable] FAIL: this is a SHALLOW clone — merge-base cannot see full history," >&2
  echo "[check-mergeable]       so a merge here can produce a garbage disjoint merge that corrupts trunk." >&2
  echo "[check-mergeable]       Remediation: git fetch --unshallow" >&2
  exit 1
fi

if [[ -n "${BRANCH}" ]]; then
  merge_base="$(git merge-base HEAD "${BRANCH}" 2>/dev/null || true)"
  if [[ -z "${merge_base}" ]]; then
    echo "[check-mergeable] FAIL: no common ancestor (unrelated histories) between HEAD and '${BRANCH}' — refusing merge" >&2
    echo "[check-mergeable]       If this repo was recently a shallow clone, run 'git fetch --unshallow' first and retry." >&2
    exit 1
  fi
  echo "[check-mergeable] OK: repo is not shallow; HEAD and '${BRANCH}' share merge-base ${merge_base}"
  exit 0
fi

echo "[check-mergeable] OK: repo is not shallow"
