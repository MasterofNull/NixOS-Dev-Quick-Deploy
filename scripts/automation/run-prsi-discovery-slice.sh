#!/usr/bin/env bash
set -euo pipefail

# Dynamic recursive discovery slice (non-mutating):
# - Runs PRSI sync/list/cycle using isolated temp state paths.
# - Ensures the orchestrator loop remains executable in dry-run mode.
# - Emits a compact JSON summary artifact for local release evidence.

ROOT_DIR="${ROOT:-$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)}"
PYTHON_BIN="${PYTHON_BIN:-python3}"
OUT_PATH="${PRSI_DISCOVERY_SUMMARY_PATH:-${ROOT_DIR}/data/prsi-artifacts/prsi-discovery-latest.json}"
SINCE_WINDOW="${PRSI_DISCOVERY_SINCE:-7d}"
EXECUTE_LIMIT="${PRSI_DISCOVERY_EXECUTE_LIMIT:-1}"

mkdir -p "$(dirname "${OUT_PATH}")"

tmpdir="$(mktemp -d)"
trap 'rm -rf "${tmpdir}"' EXIT

QUEUE_PATH="${tmpdir}/action-queue.json"
STATE_PATH="${tmpdir}/runtime-state.json"
LOG_PATH="${tmpdir}/prsi-actions.jsonl"

run_json() {
  PRSI_ACTION_QUEUE_PATH="${QUEUE_PATH}" \
  PRSI_STATE_PATH="${STATE_PATH}" \
  PRSI_ACTIONS_LOG_PATH="${LOG_PATH}" \
  "${PYTHON_BIN}" "${ROOT_DIR}/scripts/automation/prsi-orchestrator.py" "$@"
}

run_json_last() {
  local out
  out="$(run_json "$@")"
  printf '%s\n' "${out}" | awk 'NF{line=$0} END{if (line == "") {exit 1} print line}'
}

sync_json="$(run_json_last sync --since="${SINCE_WINDOW}")"
cycle_json="$(run_json_last cycle --since="${SINCE_WINDOW}" --dry-run --execute-limit="${EXECUTE_LIMIT}")"
list_json="$(run_json_last list)"

printf '%s' "${sync_json}" | jq -e '.event == "sync"' >/dev/null
printf '%s' "${cycle_json}" | jq -e '.ok == true' >/dev/null
printf '%s' "${list_json}" | jq -e '.count >= 0 and (.actions | type == "array")' >/dev/null

jq -cn \
  --arg generated_at "$(date -u +"%Y-%m-%dT%H:%M:%SZ")" \
  --arg since "${SINCE_WINDOW}" \
  --argjson sync "${sync_json}" \
  --argjson cycle "${cycle_json}" \
  --argjson listing "${list_json}" \
  '{
    generated_at: $generated_at,
    since: $since,
    sync: $sync,
    cycle: $cycle,
    listing: {
      count: $listing.count,
      counts: $listing.counts
    }
  }' > "${OUT_PATH}"

echo "PASS: PRSI discovery slice validated (${OUT_PATH})"
