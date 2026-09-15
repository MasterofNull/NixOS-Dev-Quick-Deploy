#!/usr/bin/env bash
set -euo pipefail
repo_root="${FACTORY_REPO_ROOT:-$(git rev-parse --show-toplevel)}"
tracker="${FACTORY_PM_TRACKER:-}"
plan_root="${FACTORY_PLAN_ROOT:-}"
if [[ -z "${tracker}" ]]; then
  tracker="${repo_root}/{{PM_TRACKER_PATH}}"
fi
if [[ -z "${plan_root}" ]]; then
  plan_root="${repo_root}/{{PLAN_ROOT}}"
fi
if [[ "${tracker}" == *'{{'* || "${plan_root}" == *'{{'* ]]; then
  echo "pm-tracker: render {{PM_TRACKER_PATH}} and {{PLAN_ROOT}}" >&2
  exit 1
fi
declare -a manifests=()
if [[ -d "${plan_root}" ]]; then
  mapfile -d '' manifests < <(find "${plan_root}" -mindepth 2 -maxdepth 2 -name tracker.json -print0 | sort -z)
fi
for manifest in "${manifests[@]}"; do
  python3 "${tracker}" "$(dirname "${manifest}")" --check
done
echo "pm-tracker: PASS (${#manifests[@]} tracker(s))"
