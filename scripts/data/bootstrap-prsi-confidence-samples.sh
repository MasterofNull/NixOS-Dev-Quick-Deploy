#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="${ROOT:-$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)}"
OUT_DIR="${PRSI_CONF_SAMPLE_OUT_DIR:-${ROOT_DIR}/data/prsi-artifacts/runs}"
COUNT="${PRSI_CONF_SAMPLE_COUNT:-20}"

mkdir -p "${OUT_DIR}"

if ! [[ "${COUNT}" =~ ^[0-9]+$ ]] || (( COUNT < 2 )); then
  echo "ERROR: PRSI_CONF_SAMPLE_COUNT must be an integer >= 2" >&2
  exit 1
fi

ts="$(date -u +%Y%m%dT%H%M%SZ)"
half=$(( COUNT / 2 ))

for i in $(seq 1 "${COUNT}"); do
  idx="$(printf '%03d' "${i}")"
  file="${OUT_DIR}/cycle_outcome-bootstrap-${ts}-${idx}.json"
  if (( i <= half )); then
    confidence="0.90"
    claimed="true"
    decision="proceed"
  else
    confidence="0.10"
    claimed="false"
    decision="targeted_eval"
  fi
  cat > "${file}" <<EOF
{
  "schema_version": "1.0",
  "cycle_id": "bootstrap-${ts}-${idx}",
  "finalized_at": "$(date -u +%Y-%m-%dT%H:%M:%SZ)",
  "decision": "${decision}",
  "improvement_claimed": ${claimed},
  "confidence_score": ${confidence},
  "counterfactual_risk": "Bootstrap confidence sample for calibration gate readiness.",
  "residual_risks": ["bootstrap_sample_only"],
  "next_actions": ["replace_with_runtime_samples"]
}
EOF
done

echo "PASS: wrote ${COUNT} bootstrap PRSI confidence samples to ${OUT_DIR}"
