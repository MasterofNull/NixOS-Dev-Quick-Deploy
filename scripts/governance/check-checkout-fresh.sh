#!/usr/bin/env bash
# check-checkout-fresh.sh — verify that the working tree is up-to-date with origin
# before rebuilding. Prevents the common error of rebuilding stale code after
# GitHub merges while the local clone was not pulled.
#
# Exit codes:
#   0 — checkout is current or ALLOW_STALE_CHECKOUT=1 is set
#   3 — checkout is behind origin (blocking error on main branch)
#   other — fetch failed (exits 0 with warning, never blocks offline systems)
#
# Usage:
#   scripts/governance/check-checkout-fresh.sh
#   # Or skip the check:
#   ALLOW_STALE_CHECKOUT=1 nrs
#
set -euo pipefail

REPO="${REPO:-$(git rev-parse --show-toplevel 2>/dev/null || pwd)}"
cd "$REPO"

# Allow override to skip the check
if [[ "${ALLOW_STALE_CHECKOUT:-0}" == "1" ]]; then
  echo "[WARN] Checkout freshness check skipped (ALLOW_STALE_CHECKOUT=1)" >&2
  exit 0
fi

# Fetch origin with a timeout to avoid blocking on network issues
if ! timeout 15s git fetch --quiet origin 2>/dev/null; then
  # Fetch failed or timed out — warn but don't block (offline systems can rebuild locally)
  echo "[WARN] Could not reach origin (offline?). Proceeding with local checkout." >&2
  exit 0
fi

CURRENT_BRANCH="$(git rev-parse --abbrev-ref HEAD 2>/dev/null || echo 'unknown')"
COMMITS_BEHIND=0

if [[ "$CURRENT_BRANCH" == "main" ]]; then
  # main branch — strict check
  COMMITS_BEHIND=$(git rev-list --count HEAD..origin/main 2>/dev/null || echo 0)

  if [[ $COMMITS_BEHIND -gt 0 ]]; then
    echo ""
    echo "╔════════════════════════════════════════════════════════════════╗"
    echo "║  ERROR: checkout is $COMMITS_BEHIND commit(s) behind origin/main  ║"
    echo "╚════════════════════════════════════════════════════════════════╝"
    echo ""
    echo "  Your working tree does not have recent changes from GitHub."
    echo "  Run this to update:"
    echo ""
    echo "    git -C '$REPO' pull --ff-only origin main"
    echo ""
    echo "  Then retry the rebuild:"
    echo ""
    echo "    ${CURRENT_COMMAND:-nrs}"
    echo ""
    exit 3
  fi
else
  # Not on main — warn if ahead/behind but don't block
  UPSTREAM="origin/$(git for-each-ref --format='%(upstream:short)' $(git symbolic-ref -q HEAD) 2>/dev/null || echo 'main')"
  if [[ "$UPSTREAM" != "origin/" ]] 2>/dev/null; then
    COMMITS_BEHIND=$(git rev-list --count "HEAD..$UPSTREAM" 2>/dev/null || echo 0)
    if [[ $COMMITS_BEHIND -gt 0 ]]; then
      echo "[WARN] Branch '$CURRENT_BRANCH' is $COMMITS_BEHIND commit(s) behind upstream" >&2
    fi
  fi
fi

exit 0
