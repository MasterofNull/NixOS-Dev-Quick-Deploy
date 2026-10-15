#!/usr/bin/env bash
# Prints a prominent WARN when the PRIMARY checkout (the one nrs/nixos-quick-deploy build from)
# is not on branch main. Silent when fine. Always exits 0 (session helpers must never fail on it).
# Usage: primary-checkout-warn.sh [any-path-inside-the-repo-or-a-worktree]
set -uo pipefail
start="${1:-.}"
common="$(git -c safe.directory='*' -C "$start" rev-parse --path-format=absolute --git-common-dir 2>/dev/null)" || exit 0
primary="$(dirname "$common")"
[[ -d "$primary/.git" ]] || exit 0
br="$(git -c safe.directory='*' -C "$primary" symbolic-ref -q --short HEAD 2>/dev/null || echo DETACHED)"
[[ "$br" == "main" ]] && exit 0
cat <<MSG
################################################################################
WARN: primary checkout is on '$br', NOT main:  $primary
  Merged work is not in that tree. Deploys from it (nrs, nrb, nixos-quick-deploy.sh) are
  BLOCKED by scripts/governance/check-deploy-source.sh unless AQ_DEPLOY_ALLOW_BRANCH=1.
  Fix: git -C '$primary' switch main && git -C '$primary' pull --ff-only origin main
################################################################################
MSG
exit 0
