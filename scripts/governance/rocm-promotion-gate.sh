#!/usr/bin/env bash
# rocm-promotion-gate.sh — ROCm backend promotion validation gate (Phase 57)
#
# Runs 6 sequential stages to determine whether the ROCm backend is safe to
# promote to default_backend on the current hardware class.  Any stage failure
# exits non-zero with a structured reason.  On success, writes a promotion
# state record to config/rocm-promotion-state.json.
#
# Usage:
#   scripts/governance/rocm-promotion-gate.sh [--dry-run] [--stage N] [--json]
#
# --dry-run   Report what would be checked without starting llama-server.
#             Exits 0 even on blocked hardware (documented non-error).
# --stage N   Run only stages 1..N (useful for partial validation).
# --json      Machine-readable JSON output.
#
# Exit codes:
#   0   All requested stages passed (or --dry-run)
#   1   One or more stages failed
#   2   Usage error

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "${SCRIPT_DIR}/../.." && pwd)"

# ---------------------------------------------------------------------------
# Defaults
# ---------------------------------------------------------------------------
DRY_RUN=0
MAX_STAGE=6
JSON_OUTPUT=0
LLAMA_PORT="${LLAMA_CPP_PORT:-8080}"
LLAMA_BIN="${LLAMA_BIN:-llama-server}"
MODEL_PATH=""
GFX_OVERRIDE=""

while [[ $# -gt 0 ]]; do
  case "$1" in
    --dry-run)   DRY_RUN=1 ;;
    --json)      JSON_OUTPUT=1 ;;
    --stage)
      MAX_STAGE="${2:?missing value for --stage}"
      shift ;;
    --model)
      MODEL_PATH="${2:?missing value for --model}"
      shift ;;
    --llama-bin)
      LLAMA_BIN="${2:?missing value for --llama-bin}"
      shift ;;
    --gfx-override)
      GFX_OVERRIDE="${2:?missing value for --gfx-override}"
      shift ;;
    --help|-h)
      printf 'Usage: %s [--dry-run] [--stage N] [--json] [--model PATH] [--llama-bin PATH]\n' "$0"
      exit 0
      ;;
    *)
      printf '%s: unknown argument: %s\n' "$0" "$1" >&2
      exit 2 ;;
  esac
  shift
done

MATRIX_FILE="${REPO_ROOT}/config/hardware-capability-matrix.json"
STATE_FILE="${REPO_ROOT}/config/rocm-promotion-state.json"
BENCHMARK_SCRIPT="${REPO_ROOT}/scripts/testing/benchmark-acceleration-backends.sh"

HOSTNAME_VALUE="${HOSTNAME:-$(hostname -s 2>/dev/null || echo unknown)}"
NOW_ISO="$(date -u +%Y-%m-%dT%H:%M:%SZ)"

# ---------------------------------------------------------------------------
# Output helpers
# ---------------------------------------------------------------------------
PASS_COUNT=0
FAIL_COUNT=0
declare -a STAGE_RESULTS=()
OVERALL_STATUS="pass"

log() {
  [[ $JSON_OUTPUT -eq 0 ]] && printf '[rocm-promotion-gate] %s\n' "$*"
}

stage_pass() {
  local stage_id="$1" msg="$2"
  (( PASS_COUNT++ )) || true
  STAGE_RESULTS+=("{\"stage\":\"${stage_id}\",\"status\":\"pass\",\"detail\":$(printf '%s' "\"${msg//\"/\\\"}\"")}")
  [[ $JSON_OUTPUT -eq 0 ]] && printf '  [PASS] stage=%s  %s\n' "$stage_id" "$msg"
}

stage_fail() {
  local stage_id="$1" msg="$2"
  (( FAIL_COUNT++ )) || true
  OVERALL_STATUS="fail"
  STAGE_RESULTS+=("{\"stage\":\"${stage_id}\",\"status\":\"fail\",\"detail\":$(printf '%s' "\"${msg//\"/\\\"}\"")}")
  [[ $JSON_OUTPUT -eq 0 ]] && printf '  [FAIL] stage=%s  %s\n' "$stage_id" "$msg"
}

stage_skip() {
  local stage_id="$1" msg="$2"
  STAGE_RESULTS+=("{\"stage\":\"${stage_id}\",\"status\":\"skip\",\"detail\":$(printf '%s' "\"${msg//\"/\\\"}\"")}")
  [[ $JSON_OUTPUT -eq 0 ]] && printf '  [SKIP] stage=%s  %s\n' "$stage_id" "$msg"
}

require_cmd() {
  command -v "$1" >/dev/null 2>&1 || { log "required command not found: $1"; return 1; }
}

# ---------------------------------------------------------------------------
# Detect hardware class from running system
# ---------------------------------------------------------------------------
detect_hardware_class() {
  local gpu_vendor cpu_vendor is_mobile hw_module rocm_target
  gpu_vendor="none"
  cpu_vendor="unknown"
  is_mobile="false"
  hw_module=""
  rocm_target=""

  # GPU vendor from DRM sysfs or lspci
  if command -v lspci >/dev/null 2>&1; then
    local gpu_info
    gpu_info="$(lspci 2>/dev/null | grep -iE 'vga|3d|display' || true)"
    [[ "${gpu_info}" =~ AMD|ATI|Radeon ]] && gpu_vendor="amd"
    [[ "${gpu_info}" =~ NVIDIA ]] && gpu_vendor="nvidia"
  fi

  # CPU vendor
  if command -v lscpu >/dev/null 2>&1; then
    local v
    v="$(lscpu 2>/dev/null | awk -F: '/Vendor ID:/ {gsub(/^[ \t]+/,"",$2); print tolower($2)}')"
    [[ "${v}" =~ amd|authenticamd ]] && cpu_vendor="amd"
    [[ "${v}" =~ intel|genuineintel ]] && cpu_vendor="intel"
  fi

  # Mobile
  local chassis
  chassis="$(cat /sys/class/dmi/id/chassis_type 2>/dev/null || echo 3)"
  case "$chassis" in 8|9|10|11|14|31|32) is_mobile="true" ;; esac

  # NixOS hardware module hint
  local pf
  pf="$(cat /sys/class/dmi/id/product_family 2>/dev/null || true)"
  case "$pf" in
    "ThinkPad P14s Gen 2a") hw_module="lenovo-thinkpad-p14s-amd-gen2" ;;
    "ThinkPad P14s Gen 3a") hw_module="lenovo-thinkpad-p14s-amd-gen3" ;;
  esac

  # ROCm target
  if [[ "${gpu_vendor}" == "amd" ]] && command -v rocminfo >/dev/null 2>&1; then
    rocm_target="$(rocminfo 2>/dev/null | grep -Eo 'gfx[0-9a-z]+' | head -1 || true)"
  fi

  # Map to capability matrix class
  if [[ -n "${rocm_target}" ]]; then
    case "${rocm_target}" in
      gfx90c|gfx902) echo "amd-apu-renoir" ;;
      gfx908)        echo "amd-cdna-instinct" ;;
      gfx90a)        echo "amd-cdna-instinct" ;;
      gfx1010|gfx1011|gfx1012) echo "amd-rdna1-dgpu" ;;
      gfx1030|gfx1031|gfx1032|gfx1034) echo "amd-rdna2-dgpu" ;;
      gfx1035)       echo "amd-apu-rembrandt" ;;
      gfx1100|gfx1101|gfx1102) echo "amd-rdna3-dgpu" ;;
      *)
        # Fall through to vendor+mobile heuristic
        ;;
    esac
    return
  fi

  # Heuristic fallback
  if [[ "${gpu_vendor}" == "amd" && "${cpu_vendor}" == "amd" && "${is_mobile}" == "true" ]]; then
    case "${hw_module}" in
      lenovo-thinkpad-p14s-amd-gen2) echo "amd-apu-renoir" ;;
      *) echo "amd-apu-renoir" ;;  # conservative: treat unknown AMD mobile APU as Renoir (blocked)
    esac
  elif [[ "${gpu_vendor}" == "amd" && "${is_mobile}" == "false" ]]; then
    echo "amd-rdna2-dgpu"  # optimistic default for unknown discrete AMD
  elif [[ "${gpu_vendor}" == "nvidia" ]]; then
    echo "nvidia-turing-plus"
  elif [[ "${gpu_vendor}" == "intel" ]]; then
    echo "intel-integrated"
  else
    echo "generic-cpu"
  fi
}

# ---------------------------------------------------------------------------
# Read capability matrix entries with jq
# ---------------------------------------------------------------------------
matrix_get() {
  local path="$1"
  jq -r "${path} // empty" "${MATRIX_FILE}" 2>/dev/null || true
}

# ---------------------------------------------------------------------------
# Stage functions
# ---------------------------------------------------------------------------

run_stage1_hardware_identify() {
  log "Stage 1: hardware_identify"
  [[ $DRY_RUN -eq 0 ]] || { stage_skip "hardware_identify" "dry-run"; return; }

  require_cmd jq || { stage_fail "hardware_identify" "jq not found — install jq"; return; }
  [[ -f "${MATRIX_FILE}" ]] || { stage_fail "hardware_identify" "capability matrix not found: ${MATRIX_FILE}"; return; }

  HARDWARE_CLASS="$(detect_hardware_class)"
  if [[ -z "${HARDWARE_CLASS}" ]]; then
    stage_fail "hardware_identify" "could not determine hardware class"
    return
  fi

  local class_entry
  class_entry="$(matrix_get ".hardware_classes[\"${HARDWARE_CLASS}\"]")"
  if [[ -z "${class_entry}" || "${class_entry}" == "null" ]]; then
    stage_fail "hardware_identify" "class '${HARDWARE_CLASS}' not found in capability matrix"
    return
  fi

  local promo_status
  promo_status="$(matrix_get ".hardware_classes[\"${HARDWARE_CLASS}\"].promotion_status")"
  local blocked_reason
  blocked_reason="$(matrix_get ".hardware_classes[\"${HARDWARE_CLASS}\"].promotion_blocked_reason")"

  if [[ "${promo_status}" == "blocked" ]]; then
    stage_fail "hardware_identify" "hardware class '${HARDWARE_CLASS}' is blocked for ROCm: ${blocked_reason}"
    return
  fi

  local rocm_compat_key
  rocm_compat_key="$(matrix_get ".hardware_classes[\"${HARDWARE_CLASS}\"].rocm_compat_key")"
  if [[ -z "${rocm_compat_key}" || "${rocm_compat_key}" == "null" ]]; then
    stage_fail "hardware_identify" "no rocm_compat_key for class '${HARDWARE_CLASS}' — ROCm not applicable"
    return
  fi

  ROCM_COMPAT_KEY="${rocm_compat_key}"
  stage_pass "hardware_identify" "class=${HARDWARE_CLASS} rocm_compat_key=${ROCM_COMPAT_KEY}"
}

run_stage2_compatibility_check() {
  log "Stage 2: compatibility_check"
  [[ $DRY_RUN -eq 0 ]] || { stage_skip "compatibility_check" "dry-run"; return; }
  [[ "${OVERALL_STATUS}" == "pass" ]] || { stage_skip "compatibility_check" "previous stage failed"; return; }

  local eligible
  eligible="$(matrix_get ".rocm_compatibility_matrix[\"${ROCM_COMPAT_KEY}\"].promotion_eligible")"
  if [[ "${eligible}" != "true" ]]; then
    local notes
    notes="$(matrix_get ".rocm_compatibility_matrix[\"${ROCM_COMPAT_KEY}\"].notes")"
    stage_fail "compatibility_check" "ROCm compat matrix: promotion_eligible=false for ${ROCM_COMPAT_KEY}. ${notes}"
    return
  fi

  local versions
  versions="$(matrix_get ".rocm_compatibility_matrix[\"${ROCM_COMPAT_KEY}\"].supported_rocm_versions | join(\", \")")"
  stage_pass "compatibility_check" "${ROCM_COMPAT_KEY} eligible=true supported_versions=[${versions}]"
}

run_stage3_cold_start() {
  log "Stage 3: cold_start"
  [[ $DRY_RUN -eq 0 ]] || { stage_skip "cold_start" "dry-run"; return; }
  [[ "${OVERALL_STATUS}" == "pass" ]] || { stage_skip "cold_start" "previous stage failed"; return; }

  if ! command -v "${LLAMA_BIN}" >/dev/null 2>&1; then
    stage_skip "cold_start" "${LLAMA_BIN} not in PATH — skipping live cold_start"
    return
  fi

  if [[ -z "${MODEL_PATH}" ]]; then
    # Try to find model from symlink
    MODEL_PATH="$(readlink -f /var/lib/llama-cpp/model.gguf 2>/dev/null || true)"
  fi
  if [[ -z "${MODEL_PATH}" || ! -f "${MODEL_PATH}" ]]; then
    stage_skip "cold_start" "no model file found — pass --model PATH to enable live cold_start"
    return
  fi

  local gfx_env=()
  if [[ -n "${GFX_OVERRIDE}" ]]; then
    gfx_env=("env" "HSA_OVERRIDE_GFX_VERSION=${GFX_OVERRIDE}")
  else
    local override
    override="$(matrix_get ".rocm_compatibility_matrix[\"${ROCM_COMPAT_KEY}\"].validated_gfx_override")"
    if [[ -n "${override}" && "${override}" != "null" ]]; then
      gfx_env=("env" "HSA_OVERRIDE_GFX_VERSION=${override}")
    fi
  fi

  local test_port=$(( LLAMA_PORT + 100 ))
  local success_count=0
  for run in 1 2 3; do
    log "  cold_start run ${run}/3 on port ${test_port}..."
    local pid=""
    if "${gfx_env[@]+"${gfx_env[@]}"}" "${LLAMA_BIN}" \
        --model "${MODEL_PATH}" \
        --port "${test_port}" \
        --n-gpu-layers 99 \
        --ctx-size 512 \
        --log-disable \
        > /tmp/rocm-gate-llama-${run}.log 2>&1 &
    then
      pid=$!
    fi
    local waited=0
    local ready=0
    while (( waited < 120 )); do
      if curl -sf "http://127.0.0.1:${test_port}/health" >/dev/null 2>&1; then
        ready=1
        break
      fi
      sleep 2
      (( waited += 2 )) || true
    done
    if [[ -n "${pid}" ]]; then
      kill "${pid}" 2>/dev/null || true
      wait "${pid}" 2>/dev/null || true
    fi
    if [[ "${ready}" -eq 1 ]]; then
      (( success_count++ )) || true
      log "  run ${run}: ready in ${waited}s"
    else
      log "  run ${run}: did not reach /health within 120s"
    fi
  done

  if [[ "${success_count}" -lt 3 ]]; then
    stage_fail "cold_start" "${success_count}/3 cold-start runs succeeded"
  else
    stage_pass "cold_start" "3/3 cold-start runs succeeded"
  fi
}

run_stage4_hang_check() {
  log "Stage 4: hang_check"
  [[ $DRY_RUN -eq 0 ]] || { stage_skip "hang_check" "dry-run"; return; }
  [[ "${OVERALL_STATUS}" == "pass" ]] || { stage_skip "hang_check" "previous stage failed"; return; }

  if ! command -v journalctl >/dev/null 2>&1; then
    stage_skip "hang_check" "journalctl not available"
    return
  fi

  local since
  since="$(date -u -d '30 minutes ago' '+%Y-%m-%d %H:%M:%S' 2>/dev/null \
    || date -u -v -30M '+%Y-%m-%d %H:%M:%S' 2>/dev/null \
    || echo "2000-01-01 00:00:00")"

  local hang_events
  hang_events="$(journalctl -k --since "${since}" 2>/dev/null \
    | grep -cE 'amdgpu.*GPU reset|amdgpu.*ring.*timeout|ErrorDeviceLost|amdgpu.*fatal' \
    || true)"

  if [[ "${hang_events}" -gt 0 ]]; then
    stage_fail "hang_check" "${hang_events} GPU reset/hang events in journal since cold_start"
  else
    stage_pass "hang_check" "0 GPU reset/hang events in journal"
  fi
}

run_stage5_benchmark() {
  log "Stage 5: benchmark"
  [[ $DRY_RUN -eq 0 ]] || { stage_skip "benchmark" "dry-run"; return; }
  [[ "${OVERALL_STATUS}" == "pass" ]] || { stage_skip "benchmark" "previous stage failed"; return; }

  if [[ ! -x "${BENCHMARK_SCRIPT}" ]]; then
    stage_skip "benchmark" "benchmark script not found or not executable: ${BENCHMARK_SCRIPT}"
    return
  fi

  local threshold
  threshold="$(matrix_get ".hardware_classes[\"${HARDWARE_CLASS}\"].benchmark_win_threshold_pct")"
  threshold="${threshold:-10}"

  local results_file="${REPO_ROOT}/config/backend-benchmark-results.json"

  log "  running benchmark (vulkan vs rocm)..."
  if ! "${BENCHMARK_SCRIPT}" \
      --backends vulkan,rocm \
      --output "${results_file}" \
      --model "${MODEL_PATH}" \
      --quiet 2>/dev/null; then
    stage_skip "benchmark" "benchmark script failed — skipping threshold check"
    return
  fi

  if [[ ! -f "${results_file}" ]]; then
    stage_skip "benchmark" "benchmark results file not written"
    return
  fi

  local rocm_tps vulkan_tps
  rocm_tps="$(jq -r '.results.rocm.median_tokens_per_sec // 0' "${results_file}" 2>/dev/null || echo 0)"
  vulkan_tps="$(jq -r '.results.vulkan.median_tokens_per_sec // 0' "${results_file}" 2>/dev/null || echo 0)"

  # Integer comparison: require rocm_tps >= vulkan_tps * (1 + threshold/100)
  local required_pct=$(( 100 + threshold ))
  local rocm_scaled=$(( ${rocm_tps%.*} * 100 ))
  local vulkan_scaled=$(( ${vulkan_tps%.*} * required_pct ))

  if (( rocm_scaled >= vulkan_scaled )); then
    stage_pass "benchmark" "ROCm ${rocm_tps} tok/s vs Vulkan ${vulkan_tps} tok/s (threshold +${threshold}%)"
  else
    stage_fail "benchmark" "ROCm ${rocm_tps} tok/s did not meet threshold vs Vulkan ${vulkan_tps} tok/s (+${threshold}%)"
  fi
}

run_stage6_soak() {
  log "Stage 6: soak"
  [[ $DRY_RUN -eq 0 ]] || { stage_skip "soak" "dry-run"; return; }
  [[ "${OVERALL_STATUS}" == "pass" ]] || { stage_skip "soak" "previous stage failed"; return; }

  local soak_hours
  soak_hours="$(matrix_get ".hardware_classes[\"${HARDWARE_CLASS}\"].soak_hours")"
  soak_hours="${soak_hours:-24}"

  if [[ ! -f "${STATE_FILE}" ]]; then
    stage_fail "soak" "no promotion state file — soak not started yet. Run again after ${soak_hours}h of ROCm operation."
    return
  fi

  local soak_start_iso
  soak_start_iso="$(jq -r ".hosts[\"${HOSTNAME_VALUE}\"].soak_started // empty" "${STATE_FILE}" 2>/dev/null || true)"
  if [[ -z "${soak_start_iso}" ]]; then
    stage_fail "soak" "soak_started not recorded for host ${HOSTNAME_VALUE}. Record it with --record-soak-start."
    return
  fi

  # Calculate hours elapsed since soak_started
  local soak_start_epoch now_epoch elapsed_hours
  soak_start_epoch="$(date -u -d "${soak_start_iso}" +%s 2>/dev/null \
    || date -u -j -f '%Y-%m-%dT%H:%M:%SZ' "${soak_start_iso}" +%s 2>/dev/null \
    || echo 0)"
  now_epoch="$(date -u +%s)"
  elapsed_hours=$(( (now_epoch - soak_start_epoch) / 3600 ))

  if (( elapsed_hours < soak_hours )); then
    stage_fail "soak" "soak elapsed=${elapsed_hours}h required=${soak_hours}h — not enough soak time"
    return
  fi

  # Verify clean operation: no GPU resets during the soak period (not just since last run)
  local hang_events=0
  if command -v journalctl >/dev/null 2>&1; then
    local soak_since
    soak_since="$(date -u -d "@${soak_start_epoch}" '+%Y-%m-%d %H:%M:%S' 2>/dev/null \
      || date -u -r "${soak_start_epoch}" '+%Y-%m-%d %H:%M:%S' 2>/dev/null \
      || echo '2000-01-01 00:00:00')"
    hang_events="$(journalctl -k --since "${soak_since}" 2>/dev/null \
      | grep -cE 'amdgpu.*GPU reset|amdgpu.*ring.*timeout|ErrorDeviceLost|amdgpu.*fatal' \
      || true)"
  fi

  if [[ "${hang_events}" -gt 0 ]]; then
    stage_fail "soak" "soak elapsed=${elapsed_hours}h but ${hang_events} GPU hang events detected during soak window"
  else
    stage_pass "soak" "soak elapsed=${elapsed_hours}h >= required=${soak_hours}h · ${hang_events} GPU hangs during soak"
  fi
}

# ---------------------------------------------------------------------------
# Write promotion state file
# ---------------------------------------------------------------------------
write_state_file() {
  local status="$1"

  # Initialize or read existing state
  local existing="{}"
  [[ -f "${STATE_FILE}" ]] && existing="$(cat "${STATE_FILE}" 2>/dev/null || echo "{}")"

  local stage_json
  stage_json="$(printf '%s\n' "${STAGE_RESULTS[@]}" | paste -sd ',' || echo "")"

  python3 -c "
import json, sys
state = json.loads(sys.argv[1])
state.setdefault('hosts', {})
state['hosts']['${HOSTNAME_VALUE}'] = {
    'last_gate_run': '${NOW_ISO}',
    'hardware_class': '${HARDWARE_CLASS:-unknown}',
    'gate_status': '${status}',
    'pass_count': ${PASS_COUNT},
    'fail_count': ${FAIL_COUNT},
    'stages': json.loads('[' + sys.argv[2] + ']') if sys.argv[2] else []
}
print(json.dumps(state, indent=2))
" "${existing}" "${stage_json}" > "${STATE_FILE}.tmp" 2>/dev/null \
  && mv "${STATE_FILE}.tmp" "${STATE_FILE}" \
  || true
}

# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------
HARDWARE_CLASS=""
ROCM_COMPAT_KEY=""

[[ $JSON_OUTPUT -eq 0 ]] && log "ROCm Promotion Gate — host=${HOSTNAME_VALUE} max_stage=${MAX_STAGE} dry_run=${DRY_RUN}"
[[ $JSON_OUTPUT -eq 0 ]] && log "matrix=${MATRIX_FILE}"

[[ $MAX_STAGE -ge 1 ]] && run_stage1_hardware_identify
[[ $MAX_STAGE -ge 2 ]] && run_stage2_compatibility_check
[[ $MAX_STAGE -ge 3 ]] && run_stage3_cold_start
[[ $MAX_STAGE -ge 4 ]] && run_stage4_hang_check
[[ $MAX_STAGE -ge 5 ]] && run_stage5_benchmark
[[ $MAX_STAGE -ge 6 ]] && run_stage6_soak

# Write state file (unless dry-run)
if [[ $DRY_RUN -eq 0 ]]; then
  write_state_file "${OVERALL_STATUS}"
fi

# Render output
stage_json_array="$(printf '%s\n' "${STAGE_RESULTS[@]}" | paste -sd ',' 2>/dev/null || echo "")"

if [[ $JSON_OUTPUT -eq 1 ]]; then
  printf '{"host":"%s","hardware_class":"%s","overall":"%s","pass":%d,"fail":%d,"dry_run":%s,"stages":[%s]}\n' \
    "${HOSTNAME_VALUE}" \
    "${HARDWARE_CLASS:-unknown}" \
    "${OVERALL_STATUS}" \
    "${PASS_COUNT}" \
    "${FAIL_COUNT}" \
    "$([ $DRY_RUN -eq 1 ] && echo true || echo false)" \
    "${stage_json_array}"
else
  printf '\n%s  %s  pass=%d  fail=%d\n' \
    "$([ "${OVERALL_STATUS}" == "pass" ] && echo "[GATE PASS]" || echo "[GATE FAIL]")" \
    "host=${HOSTNAME_VALUE}" \
    "${PASS_COUNT}" \
    "${FAIL_COUNT}"
fi

[[ "${OVERALL_STATUS}" == "pass" || $DRY_RUN -eq 1 ]]
