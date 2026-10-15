#!/usr/bin/env bash
# Merge-commit parity: CI tests the PR MERGE commit (HEAD + base), local tests the branch.
# Builds a temp worktree of HEAD merged (no-commit) with <base>, runs the CI manifest checks
# there plus the ci-manifest-coverage tier0.d check, then removes the worktree.
# Usage: ci-merge-parity.sh [--base origin/main] [--all]   (default scope: --changed)
# Env: CI_MERGE_PARITY_SKIP=1 skips ONLY this merge step (prints WARN; checks on the branch still run elsewhere).
set -euo pipefail
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
BASE="origin/main"; SCOPE="--changed"
while [[ $# -gt 0 ]]; do
  case "$1" in --base) BASE="$2"; shift ;; --all) SCOPE="--all" ;; *) echo "unknown arg: $1" >&2; exit 2 ;; esac
  shift
done
if [[ "${CI_MERGE_PARITY_SKIP:-}" == "1" ]]; then
  echo "WARN: CI_MERGE_PARITY_SKIP=1 -> merge-commit parity NOT checked (CI tests the merge commit)" >&2; exit 0
fi
cd "${ROOT}"
if [[ "${BASE}" == */* ]] && git remote | grep -qx "${BASE%%/*}"; then
  git fetch --quiet "${BASE%%/*}" "${BASE#*/}" 2>/dev/null \
    || echo "WARN: git fetch ${BASE%%/*} ${BASE#*/} failed; merging against a possibly STALE local ${BASE}" >&2
else
  echo "WARN: cannot fetch base ${BASE} (no such remote); merging against local ref, possibly STALE" >&2
fi
git rev-parse --verify --quiet "${BASE}" >/dev/null || { echo "FAIL: base ref ${BASE} not found (git fetch origin)" >&2; exit 1; }
echo "BASE=${BASE} $(git rev-parse --short "${BASE}") ($(git log -1 --format=%cI "${BASE}"))"
echo "ci-merge-parity: testing committed HEAD $(git rev-parse --short HEAD); uncommitted changes NOT included"
[[ -z "$(git status --porcelain)" ]] || echo "WARN: working tree has uncommitted changes; they are NOT tested here" >&2
WT="$(mktemp -d "${TMPDIR:-/tmp}/ci-merge-parity-XXXXXX")"
cleanup() { git worktree remove --force "${WT}" >/dev/null 2>&1 || true; git worktree prune >/dev/null 2>&1 || true; }
trap cleanup EXIT
git worktree add --detach -q "${WT}" HEAD
if ! git -C "${WT}" -c user.name=ci-parity -c user.email=ci-parity@localhost merge --no-commit --no-ff -q "${BASE}" >/dev/null 2>&1; then
  git -C "${WT}" merge --abort >/dev/null 2>&1 || true
  echo "FAIL: merging ${BASE} into HEAD conflicts; CI would test an unmergeable PR. Update the branch first (git rebase ${BASE} or git merge ${BASE})." >&2
  exit 1
fi
echo "ci-merge-parity: running ${SCOPE} manifest checks on HEAD+${BASE} merge tree"
rc=0
# Select checks by the PR's own diff (what CI path filters see), not main's delta in the merge.
if [[ "${SCOPE}" == "--changed" ]] && pr_files="$(git diff --name-only "${BASE}...HEAD" 2>/dev/null)"; then
  export CI_CHECKS_CHANGED_FILES="${pr_files}"
fi
(cd "${WT}" && ./scripts/governance/run-ci-checks.sh "${SCOPE}" --base "${BASE}") || rc=1
if [[ -f "${WT}/scripts/governance/tier0.d/check-ci-manifest-coverage.sh" ]]; then
  (cd "${WT}" && bash scripts/governance/tier0.d/check-ci-manifest-coverage.sh) || rc=1
fi
[[ ${rc} -eq 0 ]] || echo "ci-merge-parity: FAIL (a check fails on the merge commit CI will test)" >&2
exit ${rc}
