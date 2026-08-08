#!/usr/bin/env bash
# Tier0 extension: PM-tracker projection is valid on every commit.
# The rule "keep the gantt/kanban updated on every commit" is satisfied by CONSTRUCTION — status is
# PROJECTED live from ground truth by aq-pm-tracker (git + freeze records + activation grants + blockers),
# never a hand-maintained artifact that can rot. So the only per-commit obligation is: every plan's
# editorial manifest (<plan-dir>/tracker.json) stays VALID and projects. This gate enforces that (a broken
# or gamed manifest fails the commit). Missing-tracker-for-an-active-plan is a freshness-class WARN, never
# a hard block (Rule 19 gate-hygiene: block a regression the change introduces, not cosmetic absence).
set -euo pipefail

MODE="${1:---pre-commit}"
REPO_ROOT="$(git rev-parse --show-toplevel)"
cd "${REPO_ROOT}"

TRACKER="scripts/ai/aq-pm-tracker"
if [[ ! -x "${TRACKER}" ]] && ! python3 -c "import sys" 2>/dev/null; then
  echo "[tier0.d/check-pm-tracker] SKIP: projector unavailable"
  exit 0
fi

fail=0
shopt -s nullglob
manifests=(.agents/plans/*/tracker.json)
if [[ ${#manifests[@]} -eq 0 ]]; then
  echo "[tier0.d/check-pm-tracker] PASS: no plan trackers yet (nothing to project)"
  exit 0
fi

for m in "${manifests[@]}"; do
  plan_dir="$(dirname "${m}")"
  if out="$(python3 "${TRACKER}" "${plan_dir}" --check 2>&1)"; then
    :
  else
    echo "[tier0.d/check-pm-tracker] FAIL: ${plan_dir}/tracker.json does not validate/project:"
    echo "${out}" | sed 's/^/    /'
    fail=1
  fi
done

# Freshness-class WARN (never a hard block): a plan dir with staged changes this commit but no tracker.json.
if [[ "${MODE}" == "--pre-commit" ]]; then
  while IFS= read -r changed; do
    [[ -z "${changed}" ]] && continue
    case "${changed}" in
      .agents/plans/*/*)
        pd="$(echo "${changed}" | cut -d/ -f1-3)"
        [[ -f "${pd}/tracker.json" ]] || echo "[tier0.d/check-pm-tracker] WARN: ${pd} has changes but no tracker.json (consider adding one so its progress projects)"
        ;;
    esac
  done < <(git diff --cached --name-only 2>/dev/null | sort -u) 2>/dev/null || true
fi

if [[ "${fail}" -eq 0 ]]; then
  echo "[tier0.d/check-pm-tracker] PASS: ${#manifests[@]} plan tracker(s) valid + projecting from ground truth"
fi
exit "${fail}"
