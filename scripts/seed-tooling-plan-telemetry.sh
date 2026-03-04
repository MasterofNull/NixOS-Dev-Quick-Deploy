#!/usr/bin/env bash
set -euo pipefail

# Submit lightweight analysis-only aider tasks to ensure task tooling telemetry emits.

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
# shellcheck source=../config/service-endpoints.sh
source "${SCRIPT_DIR}/../config/service-endpoints.sh"

WORKSPACE="${SEED_TOOLING_WORKSPACE:-$(cd "${SCRIPT_DIR}/.." && pwd)}"
TASKS="${SEED_TOOLING_TASKS:-4}"
AIDER_KEY="${AIDER_WRAPPER_API_KEY:-}"
AIDER_KEY_FILE="${AIDER_WRAPPER_API_KEY_FILE:-/run/secrets/aider_wrapper_api_key}"

if [[ -z "${AIDER_KEY}" && -r "${AIDER_KEY_FILE}" ]]; then
  AIDER_KEY="$(tr -d '[:space:]' < "${AIDER_KEY_FILE}")"
fi

headers=(-H "Content-Type: application/json")
if [[ -n "${AIDER_KEY}" ]]; then
  headers+=(-H "X-API-Key: ${AIDER_KEY}")
fi

ok=0
fail=0

for i in $(seq 1 "${TASKS}"); do
  payload="$(jq -cn --arg p "analysis only task ${i}: summarize PRSI gate status in one sentence, no edits" --arg f 'docs/SYSTEM-IMPROVEMENT-PLAN-2026-03.md' --arg ws "${WORKSPACE}" '{prompt:$p,files:[$f],workspace:$ws}')"
  if curl -fsS --max-time 20 --connect-timeout 5 -X POST "${AIDER_WRAPPER_URL%/}/tasks" "${headers[@]}" -d "${payload}" >/tmp/seed-tooling-submit.json; then
    task_id="$(jq -r '.task_id // empty' /tmp/seed-tooling-submit.json)"
    if [[ -z "${task_id}" ]]; then
      fail=$((fail + 1))
      continue
    fi
    terminal=false
    for _ in $(seq 1 60); do
      status_json="$(curl -fsS --max-time 8 --connect-timeout 3 "${AIDER_WRAPPER_URL%/}/tasks/${task_id}/status" "${headers[@]}" || true)"
      status="$(jq -r '.status // "unknown"' <<<"${status_json}")"
      if [[ "${status}" == "success" ]]; then
        ok=$((ok + 1))
        terminal=true
        break
      fi
      if [[ "${status}" == "error" || "${status}" == "canceled" ]]; then
        fail=$((fail + 1))
        terminal=true
        break
      fi
      sleep 1
    done
    if [[ "${terminal}" == false ]]; then
      fail=$((fail + 1))
    fi
  else
    fail=$((fail + 1))
  fi
done

echo "seed-tooling-plan-telemetry: ok=${ok} fail=${fail}"
if (( ok == 0 )); then
  exit 1
fi
