#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="${ROOT:-$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)}"
TARGET_COVERAGE_PCT="${INTENT_REMEDIATION_TARGET_COVERAGE_PCT:-60}"
RUNS_PER_PASS="${INTENT_REMEDIATION_RUNS_PER_PASS:-8}"
MAX_TOTAL_RUNS="${INTENT_REMEDIATION_MAX_TOTAL_RUNS:-24}"
MAX_PASSES="${INTENT_REMEDIATION_MAX_PASSES:-6}"
SLEEP_SECONDS="${INTENT_REMEDIATION_SLEEP_SECONDS:-2}"

report_json() {
  "${ROOT_DIR}/scripts/aq-report" --since=7d --format=json
}

coverage_pct() {
  jq -r '.intent_contract_compliance.contract_coverage_pct // 0'
}

runs_started() {
  jq -r '.intent_contract.runs_started // 0'
}

total_started=0
passes=0

start_cov="$(report_json | coverage_pct)"
echo "[intent-remediation] start coverage=${start_cov}% target=${TARGET_COVERAGE_PCT}%"

while (( passes < MAX_PASSES )) && (( total_started < MAX_TOTAL_RUNS )); do
  current_cov="$(report_json | coverage_pct)"
  awk "BEGIN{exit !(${current_cov} >= ${TARGET_COVERAGE_PCT})}" && break

  remaining=$(( MAX_TOTAL_RUNS - total_started ))
  per_pass="${RUNS_PER_PASS}"
  if (( per_pass > remaining )); then
    per_pass="${remaining}"
  fi
  if (( per_pass <= 0 )); then
    break
  fi

  echo "[intent-remediation] pass=$((passes+1)) current=${current_cov}% runs_this_pass=${per_pass}"
  out="$(POST_DEPLOY_INTENT_MAX_PROBE_RUNS="${per_pass}" python3 "${ROOT_DIR}/scripts/aq-auto-remediate.py" --summary-out /tmp/aq-auto-remediate-bounded.json)"
  started="$(printf '%s\n' "${out}" | runs_started)"
  if ! [[ "${started}" =~ ^[0-9]+$ ]]; then
    started=0
  fi
  total_started=$(( total_started + started ))
  passes=$(( passes + 1 ))
  sleep "${SLEEP_SECONDS}"
done

final_cov="$(report_json | coverage_pct)"
echo "[intent-remediation] done passes=${passes} total_started=${total_started} final_coverage=${final_cov}%"
