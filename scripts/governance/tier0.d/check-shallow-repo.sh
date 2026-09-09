#!/usr/bin/env bash
# Tier0 extension: VISIBILITY check for a shallow clone.
#
# A shallow repo can't safely merge (see scripts/governance/check-mergeable.sh):
# git merge-base can't see truncated history, so a merge can produce a garbage
# disjoint merge. This check only WARNS — being shallow is an environmental /
# freshness-class condition, not a regression introduced by the staged change,
# so it must never block a normal commit (Rule 19 gate-hygiene). The hard block
# lives in .githooks/pre-merge-commit and the pre-commit MERGE_HEAD guard, which
# only trigger for an actual merge.
set -euo pipefail

REPO_ROOT="$(git rev-parse --show-toplevel)"
cd "${REPO_ROOT}"

if [[ "$(git rev-parse --is-shallow-repository)" == "true" ]]; then
  echo "[tier0.d/check-shallow-repo] WARN: this is a SHALLOW clone — merges are unsafe here (garbage disjoint merge risk). Remediation: git fetch --unshallow"
  exit 0
fi

echo "[tier0.d/check-shallow-repo] PASS: repo is not shallow"
