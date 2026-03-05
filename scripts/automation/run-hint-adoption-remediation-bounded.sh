#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="${ROOT:-$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)}"
TARGET_PCT="${HINT_REMEDIATION_TARGET_ADOPTION_PCT:-70}"
RUNS_PER_PASS="${HINT_REMEDIATION_RUNS_PER_PASS:-4}"
MAX_TOTAL_RUNS="${HINT_REMEDIATION_MAX_TOTAL_RUNS:-16}"
MAX_PASSES="${HINT_REMEDIATION_MAX_PASSES:-6}"
POLL_MAX_SECONDS="${HINT_REMEDIATION_POLL_MAX_SECONDS:-90}"
SLEEP_SECONDS="${HINT_REMEDIATION_SLEEP_SECONDS:-2}"
WORKSPACE="${HINT_REMEDIATION_WORKSPACE:-${ROOT_DIR}}"
FILE_REL="${HINT_REMEDIATION_FILE:-.cache/ai-hint-remediation/notes.md}"
PROMPT_POOL="${HINT_REMEDIATION_PROMPT_POOL:-nixos_service_modules;mkif_mkforce;hybrid_routing;qdrant_config;hint_feedback_loop;intent_contract}"

# shellcheck source=../config/service-endpoints.sh
source "${ROOT_DIR}/config/service-endpoints.sh"

report_json() {
  "${ROOT_DIR}/scripts/ai/aq-report" --since=7d --format=json
}

adoption_pct() {
  jq -r '.hint_adoption.adoption_pct // 0'
}

total_injected() {
  jq -r '.hint_adoption.total // 0'
}

total_accepted() {
  jq -r '.hint_adoption.accepted // 0'
}

need_runs_for_target() {
  local total="${1}"
  local accepted="${2}"
  local target="${3}"
  if (( total <= 0 )); then
    printf '%s\n' 1
    return
  fi
  python3 - "$total" "$accepted" "$target" <<'PY'
import math, sys
t = max(0, int(sys.argv[1]))
a = max(0, int(sys.argv[2]))
target = max(0.0, min(100.0, float(sys.argv[3])))
if target <= 0:
    print(0)
    raise SystemExit
if t <= 0:
    print(1)
    raise SystemExit
cur = (a / t) * 100.0
if cur >= target:
    print(0)
    raise SystemExit
x = target / 100.0
den = 1.0 - x
if den <= 0:
    print(0)
    raise SystemExit
n = math.ceil(max(0.0, (x * t - a) / den))
print(max(1, n))
PY
}

load_aider_key() {
  local key="${AIDER_WRAPPER_API_KEY:-}"
  local key_file="${AIDER_WRAPPER_API_KEY_FILE:-/run/secrets/aider_wrapper_api_key}"
  if [[ -z "${key}" && -r "${key_file}" ]]; then
    key="$(tr -d '[:space:]' < "${key_file}")"
  fi
  printf '%s\n' "${key}"
}

submit_task() {
  local payload="${1}"
  local key="${2}"
  local -a hdr=(-H "Content-Type: application/json")
  if [[ -n "${key}" ]]; then
    hdr+=(-H "X-API-Key: ${key}")
  fi
  curl -fsS --max-time 20 --connect-timeout 5 \
    -X POST "${AIDER_WRAPPER_URL%/}/tasks" "${hdr[@]}" -d "${payload}"
}

task_status() {
  local task_id="${1}"
  local key="${2}"
  local -a hdr=()
  if [[ -n "${key}" ]]; then
    hdr+=(-H "X-API-Key: ${key}")
  fi
  curl -fsS --max-time 10 --connect-timeout 4 \
    "${AIDER_WRAPPER_URL%/}/tasks/${task_id}/status" "${hdr[@]}"
}

mkdir -p "${WORKSPACE}/$(dirname "${FILE_REL}")"
if [[ ! -f "${WORKSPACE}/${FILE_REL}" ]]; then
  cat > "${WORKSPACE}/${FILE_REL}" <<EOF
# Hint Adoption Remediation Notes

This file is used for bounded hint-adoption remediation probes.
EOF
fi

IFS=';' read -r -a PROMPT_TOPICS <<< "${PROMPT_POOL}"
if (( ${#PROMPT_TOPICS[@]} == 0 )); then
  PROMPT_TOPICS=("mkif_mkforce")
fi

key="$(load_aider_key)"
started_total=0
ok_total=0
fail_total=0
pass=0

start_pct="$(report_json | adoption_pct)"
start_total="$(report_json | total_injected)"
start_acc="$(report_json | total_accepted)"
echo "[hint-remediation] start adoption=${start_pct}% accepted=${start_acc}/${start_total} target=${TARGET_PCT}%"

while (( pass < MAX_PASSES )) && (( started_total < MAX_TOTAL_RUNS )); do
  current_json="$(report_json)"
  cur_pct="$(printf '%s\n' "${current_json}" | adoption_pct)"
  cur_total="$(printf '%s\n' "${current_json}" | total_injected)"
  cur_acc="$(printf '%s\n' "${current_json}" | total_accepted)"
  awk "BEGIN{exit !(${cur_pct} >= ${TARGET_PCT})}" && break

  needed="$(need_runs_for_target "${cur_total}" "${cur_acc}" "${TARGET_PCT}")"
  remaining=$(( MAX_TOTAL_RUNS - started_total ))
  runs_this_pass="${RUNS_PER_PASS}"
  if (( needed > 0 && runs_this_pass > needed )); then
    runs_this_pass="${needed}"
  fi
  if (( runs_this_pass > remaining )); then
    runs_this_pass="${remaining}"
  fi
  if (( runs_this_pass <= 0 )); then
    break
  fi

  echo "[hint-remediation] pass=$((pass+1)) current=${cur_pct}% accepted=${cur_acc}/${cur_total} runs_this_pass=${runs_this_pass}"

  for idx in $(seq 1 "${runs_this_pass}"); do
    run_id=$(( started_total + idx ))
    topic_idx=$(( (run_id - 1) % ${#PROMPT_TOPICS[@]} ))
    topic="${PROMPT_TOPICS[$topic_idx]}"
    case "${topic}" in
      nixos_service_modules)
        topic_prompt="append one bullet that shows a concise NixOS systemd service module option pattern"
        ;;
      mkif_mkforce)
        topic_prompt="append one bullet that explains lib.mkIf vs lib.mkForce in one sentence"
        ;;
      hybrid_routing)
        topic_prompt="append one bullet that explains how the hybrid coordinator chooses local vs remote"
        ;;
      qdrant_config)
        topic_prompt="append one bullet with one Qdrant config best practice for AI stack retrieval"
        ;;
      hint_feedback_loop)
        topic_prompt="append one bullet explaining how /hints/feedback improves future hint quality"
        ;;
      intent_contract)
        topic_prompt="append one bullet summarizing intent_contract fields required by workflow/run/start"
        ;;
      *)
        topic_prompt="append one concise NixOS/AI-stack operations bullet"
        ;;
    esac
    prompt="Update ${FILE_REL}: ${topic_prompt} for hint optimization pass ${run_id}. Keep it to one sentence and save the file."
    payload="$(jq -cn --arg p "${prompt}" --arg f "${FILE_REL}" --arg ws "${WORKSPACE}" '{prompt:$p,files:[$f],workspace:$ws}')"

    task_resp="$(submit_task "${payload}" "${key}" || true)"
    task_id="$(jq -r '.task_id // empty' <<<"${task_resp}")"
    if [[ -z "${task_id}" ]]; then
      fail_total=$((fail_total + 1))
      continue
    fi
    started_total=$((started_total + 1))

    terminal=false
    poll_start="$(date +%s)"
    while true; do
      status_json="$(task_status "${task_id}" "${key}" || true)"
      status="$(jq -r '.status // "unknown"' <<<"${status_json}")"
      if [[ "${status}" == "success" ]]; then
        ok_total=$((ok_total + 1))
        terminal=true
        break
      fi
      if [[ "${status}" == "error" || "${status}" == "canceled" ]]; then
        fail_total=$((fail_total + 1))
        terminal=true
        break
      fi
      now="$(date +%s)"
      if (( now - poll_start >= POLL_MAX_SECONDS )); then
        fail_total=$((fail_total + 1))
        terminal=true
        break
      fi
      sleep 1
    done
    if [[ "${terminal}" == false ]]; then
      fail_total=$((fail_total + 1))
    fi
    if (( started_total >= MAX_TOTAL_RUNS )); then
      break
    fi
  done
  pass=$((pass + 1))
  sleep "${SLEEP_SECONDS}"
done

final_json="$(report_json)"
final_pct="$(printf '%s\n' "${final_json}" | adoption_pct)"
final_total="$(printf '%s\n' "${final_json}" | total_injected)"
final_acc="$(printf '%s\n' "${final_json}" | total_accepted)"
echo "[hint-remediation] done passes=${pass} started=${started_total} ok=${ok_total} fail=${fail_total} final=${final_pct}% accepted=${final_acc}/${final_total}"
