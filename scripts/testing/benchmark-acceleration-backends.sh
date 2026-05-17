#!/usr/bin/env bash
# benchmark-acceleration-backends.sh — Backend benchmark harness (Phase 57)
#
# Measures startup time, tokens/sec, peak RSS, and GPU reset events for each
# available acceleration backend.  Designed to be called by Stage 5 of
# scripts/governance/rocm-promotion-gate.sh, but also useful standalone.
#
# Usage:
#   scripts/testing/benchmark-acceleration-backends.sh \
#     [--backends vulkan,rocm,cpu] \
#     [--model PATH] \
#     [--output config/backend-benchmark-results.json] \
#     [--runs N] \
#     [--ctx-size N] \
#     [--prompt TEXT] \
#     [--quiet] \
#     [--use-existing-server HOST:PORT]
#
# --use-existing-server HOST:PORT
#   Skip server startup (and model file access) entirely; measure tps against
#   the already-running server at HOST:PORT.  On DynamicUser-locked systems
#   (e.g. NixOS llama-cpp.service) where the model file is inaccessible from
#   the invoking shell, use: --use-existing-server 127.0.0.1:8080
#   The backend label will be "existing-server" unless --backends is also set
#   to a single label (e.g. --backends vulkan).
#
# Output:
#   JSON file with per-backend results including median tok/s, startup ms,
#   peak RSS MB, and GPU reset count.
#
# Exit codes:
#   0   At least one backend benchmarked successfully
#   1   All backends failed or no model found
#   2   Usage error

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "${SCRIPT_DIR}/../.." && pwd)"

# ---------------------------------------------------------------------------
# Argument parsing
# ---------------------------------------------------------------------------
BACKENDS=""
MODEL_PATH=""
OUTPUT_FILE="${REPO_ROOT}/config/backend-benchmark-results.json"
RUNS=3
CTX_SIZE=512
PROMPT="Explain the difference between Vulkan and ROCm in two sentences."
QUIET=0
LLAMA_BIN="${LLAMA_BIN:-llama-server}"
BASE_PORT="${BENCHMARK_BASE_PORT:-18080}"
EXISTING_SERVER=""   # HOST:PORT of an already-running server (skips startup)

while [[ $# -gt 0 ]]; do
  case "$1" in
    --backends)            BACKENDS="${2:?}"; shift ;;
    --model)               MODEL_PATH="${2:?}"; shift ;;
    --output)              OUTPUT_FILE="${2:?}"; shift ;;
    --runs)                RUNS="${2:?}"; shift ;;
    --ctx-size)            CTX_SIZE="${2:?}"; shift ;;
    --prompt)              PROMPT="${2:?}"; shift ;;
    --quiet)               QUIET=1 ;;
    --llama-bin)           LLAMA_BIN="${2:?}"; shift ;;
    --use-existing-server) EXISTING_SERVER="${2:?}"; shift ;;
    --help|-h)
      printf 'Usage: %s [--backends B] [--model PATH] [--output FILE] [--runs N] [--quiet] [--use-existing-server HOST:PORT]\n' "$0"
      exit 0 ;;
    *) printf '%s: unknown argument: %s\n' "$0" "$1" >&2; exit 2 ;;
  esac
  shift
done

log() {
  [[ $QUIET -eq 1 ]] || printf '[benchmark-backends] %s\n' "$*" >&2
}

# ---------------------------------------------------------------------------
# Resolve model path (skipped when --use-existing-server is set)
# ---------------------------------------------------------------------------
if [[ -z "${EXISTING_SERVER}" ]]; then
  if [[ -z "${MODEL_PATH}" ]]; then
    # Resolution order:
    # 1. BENCHMARK_MODEL_PATH (injected by NixOS module — resolves DynamicUser boundary)
    # 2. LLAMA_CPP_MODEL_PATH (alias)
    # 3. Symlink fallback (works if running as the service user)
    MODEL_PATH="${BENCHMARK_MODEL_PATH:-${LLAMA_CPP_MODEL_PATH:-}}"
  fi
  if [[ -z "${MODEL_PATH}" ]]; then
    MODEL_PATH="$(readlink -f /var/lib/llama-cpp/model.gguf 2>/dev/null || true)"
  fi
  if [[ -z "${MODEL_PATH}" ]]; then
    log "No model path provided."
    log "Set BENCHMARK_MODEL_PATH (injected by NixOS ai-stack module after rebuild),"
    log "or pass --model PATH explicitly, or use --use-existing-server HOST:PORT."
    printf '{"error":"no_model","results":{}}\n' > "${OUTPUT_FILE}"
    exit 1
  fi
  if [[ ! -f "${MODEL_PATH}" ]]; then
    log "Model file not found: ${MODEL_PATH}"
    exit 1
  fi
fi

# ---------------------------------------------------------------------------
# Resolve backend list
# ---------------------------------------------------------------------------
MATRIX_FILE="${REPO_ROOT}/config/hardware-capability-matrix.json"

auto_detect_backends() {
  local available=()
  # CPU is always available
  available+=("cpu")
  # Vulkan: check for vulkaninfo or ICD file
  if command -v vulkaninfo >/dev/null 2>&1 || \
     ls /run/opengl-driver/share/vulkan/icd.d/*.json >/dev/null 2>&1; then
    available+=("vulkan")
  fi
  # ROCm: check for rocminfo
  if command -v rocminfo >/dev/null 2>&1 && rocminfo >/dev/null 2>&1; then
    available+=("rocm")
  fi
  # CUDA: check for nvidia-smi
  if command -v nvidia-smi >/dev/null 2>&1; then
    available+=("cuda")
  fi
  printf '%s\n' "${available[@]}" | paste -sd ',' 2>/dev/null || echo "cpu"
}

if [[ -z "${BACKENDS}" ]]; then
  BACKENDS="$(auto_detect_backends)"
fi
log "backends=${BACKENDS} model=${MODEL_PATH} runs=${RUNS}"

# ---------------------------------------------------------------------------
# Per-backend environment
# ---------------------------------------------------------------------------
backend_env() {
  local backend="$1"
  case "${backend}" in
    vulkan)
      local icd=""
      if [[ -f /run/opengl-driver/share/vulkan/icd.d/radeon_icd.x86_64.json ]]; then
        icd="/run/opengl-driver/share/vulkan/icd.d/radeon_icd.x86_64.json"
      elif [[ -f /run/opengl-driver/share/vulkan/icd.d/intel_icd.x86_64.json ]]; then
        icd="/run/opengl-driver/share/vulkan/icd.d/intel_icd.x86_64.json"
      fi
      if [[ -n "${icd}" ]]; then
        printf 'VK_ICD_FILENAMES=%s VK_DRIVER_FILES=%s' "${icd}" "${icd}"
      fi
      ;;
    rocm)
      local gfx=""
      if [[ -f "${MATRIX_FILE}" ]] && command -v jq >/dev/null 2>&1; then
        local rocm_target
        rocm_target="$(rocminfo 2>/dev/null | grep -Eo 'gfx[0-9a-z]+' | head -1 || true)"
        if [[ -n "${rocm_target}" ]]; then
          gfx="$(jq -r ".rocm_compatibility_matrix[\"${rocm_target}\"].validated_gfx_override // empty" "${MATRIX_FILE}" 2>/dev/null || true)"
        fi
      fi
      if [[ -n "${gfx}" && "${gfx}" != "null" ]]; then
        printf 'HSA_OVERRIDE_GFX_VERSION=%s' "${gfx}"
      fi
      ;;
    *)
      printf ''
      ;;
  esac
}

backend_gpu_layers() {
  local backend="$1"
  case "${backend}" in
    cpu) echo "0" ;;
    *)   echo "99" ;;
  esac
}

# ---------------------------------------------------------------------------
# GPU reset counter
# ---------------------------------------------------------------------------
count_gpu_resets_since() {
  local since_epoch="$1"
  if ! command -v journalctl >/dev/null 2>&1; then echo "0"; return; fi
  local since_iso
  since_iso="$(date -u -d "@${since_epoch}" '+%Y-%m-%d %H:%M:%S' 2>/dev/null \
    || date -u -r "${since_epoch}" '+%Y-%m-%d %H:%M:%S' 2>/dev/null \
    || echo '2000-01-01 00:00:00')"
  # grep -c exits 1 when count is 0; capture into variable to avoid triggering pipefail
  local count
  count="$(journalctl -k --since "${since_iso}" 2>/dev/null \
    | grep -cE 'amdgpu.*GPU reset|amdgpu.*ring.*timeout|ErrorDeviceLost' \
    2>/dev/null)" || count="0"
  printf '%s' "${count}"
}

# ---------------------------------------------------------------------------
# Benchmark one backend
# ---------------------------------------------------------------------------
benchmark_backend() {
  local backend="$1"
  local port=$(( BASE_PORT + RANDOM % 1000 ))
  local env_str
  env_str="$(backend_env "${backend}")"
  local gpu_layers
  gpu_layers="$(backend_gpu_layers "${backend}")"

  log "  benchmarking backend=${backend} port=${port} gpu_layers=${gpu_layers}"

  local start_epoch
  start_epoch="$(date -u +%s)"

  # Build command
  local cmd=()
  if [[ -n "${env_str}" ]]; then
    # Split env_str into key=value pairs safely
    while IFS= read -r kv; do
      [[ -n "${kv}" ]] && cmd+=("${kv}")
    done < <(printf '%s\n' "${env_str}")
    cmd=("env" "${cmd[@]}")
  fi
  cmd+=("${LLAMA_BIN}"
    "--model" "${MODEL_PATH}"
    "--port" "${port}"
    "--n-gpu-layers" "${gpu_layers}"
    "--ctx-size" "${CTX_SIZE}"
    "--log-disable")

  # Start server
  local pid=""
  "${cmd[@]}" > "/tmp/bench-${backend}.log" 2>&1 &
  pid=$!

  # Wait for /health
  local waited=0
  local startup_ms=0
  local ready=0
  while (( waited < 120 )); do
    if curl -sf "http://127.0.0.1:${port}/health" >/dev/null 2>&1; then
      startup_ms=$(( waited * 1000 ))
      ready=1
      break
    fi
    sleep 1
    (( waited++ )) || true
  done

  if [[ "${ready}" -eq 0 ]]; then
    kill "${pid}" 2>/dev/null || true
    wait "${pid}" 2>/dev/null || true
    printf '{"backend":"%s","error":"did_not_start","startup_ms":null,"tokens_per_sec":[],"median_tokens_per_sec":0,"peak_rss_mb":null,"gpu_resets":null}' "${backend}"
    return
  fi

  # Run benchmark prompt N times
  local tps_values=()
  for run in $(seq 1 "${RUNS}"); do
    local t_before t_after
    t_before="$(date +%s%3N)"
    local response
    response="$(curl -sf --max-time 300 \
      "http://127.0.0.1:${port}/completion" \
      -H 'Content-Type: application/json' \
      -d "{\"prompt\":\"${PROMPT}\",\"n_predict\":64,\"stream\":false}" 2>/dev/null || echo '{}')"
    t_after="$(date +%s%3N)"
    local elapsed_ms=$(( t_after - t_before ))
    local n_predicted
    n_predicted="$(printf '%s' "${response}" | python3 -c "import sys,json; d=json.load(sys.stdin); print(d.get('tokens_predicted', d.get('n_predicted', 0)))" 2>/dev/null || echo 0)"
    local tps=0
    if (( elapsed_ms > 0 && n_predicted > 0 )); then
      tps=$(( n_predicted * 1000 / elapsed_ms ))
    fi
    tps_values+=("${tps}")
    log "    run ${run}/${RUNS}: n_predicted=${n_predicted} elapsed=${elapsed_ms}ms tps=${tps}"
  done

  # Measure peak RSS
  local peak_rss=0
  if [[ -n "${pid}" ]] && [[ -f "/proc/${pid}/status" ]]; then
    peak_rss="$(awk '/VmRSS:/{print int($2/1024)}' "/proc/${pid}/status" 2>/dev/null || echo 0)"
  fi

  # Count GPU resets during this benchmark
  local resets
  resets="$(count_gpu_resets_since "${start_epoch}")"

  kill "${pid}" 2>/dev/null || true
  wait "${pid}" 2>/dev/null || true

  # Compute median
  local median
  local -a sorted
  mapfile -t sorted < <(printf '%d\n' "${tps_values[@]}" | sort -n)
  local count="${#sorted[@]}"
  if (( count % 2 == 1 )); then
    median="${sorted[$(( count / 2 ))]}"
  else
    median=$(( (sorted[$(( count / 2 - 1 ))] + sorted[$(( count / 2 ))]) / 2 ))
  fi

  local tps_json
  tps_json="[$(printf '%d,' "${tps_values[@]}" | sed 's/,$//')]"

  printf '{"backend":"%s","startup_ms":%d,"tokens_per_sec":%s,"median_tokens_per_sec":%d,"peak_rss_mb":%d,"gpu_resets":%s}' \
    "${backend}" \
    "${startup_ms}" \
    "${tps_json}" \
    "${median}" \
    "${peak_rss}" \
    "${resets}"
}

# ---------------------------------------------------------------------------
# Benchmark against an already-running server (--use-existing-server mode)
# No server startup; no model file access required.
# ---------------------------------------------------------------------------
benchmark_existing_server() {
  local backend_label="$1"
  local host_port="$2"
  local url_base="http://${host_port}"

  log "  benchmarking existing server=${host_port} label=${backend_label}"

  # Verify the server is actually up
  if ! curl -sf --max-time 5 "${url_base}/health" >/dev/null 2>&1; then
    printf '{"backend":"%s","error":"server_not_reachable","startup_ms":null,"tokens_per_sec":[],"median_tokens_per_sec":0,"peak_rss_mb":null,"gpu_resets":null}' \
      "${backend_label}"
    return
  fi

  local start_epoch
  start_epoch="$(date -u +%s)"
  local tps_values=()

  for run in $(seq 1 "${RUNS}"); do
    local t_before t_after
    t_before="$(date +%s%3N)"
    local response
    response="$(curl -sf --max-time 300 \
      "${url_base}/completion" \
      -H 'Content-Type: application/json' \
      -d "{\"prompt\":\"${PROMPT}\",\"n_predict\":64,\"stream\":false}" 2>/dev/null || echo '{}')"
    t_after="$(date +%s%3N)"
    local elapsed_ms=$(( t_after - t_before ))
    local n_predicted
    n_predicted="$(printf '%s' "${response}" | python3 -c "import sys,json; d=json.load(sys.stdin); print(d.get('tokens_predicted', d.get('n_predicted', 0)))" 2>/dev/null || echo 0)"
    local tps=0
    if (( elapsed_ms > 0 && n_predicted > 0 )); then
      tps=$(( n_predicted * 1000 / elapsed_ms ))
    fi
    tps_values+=("${tps}")
    log "    run ${run}/${RUNS}: n_predicted=${n_predicted} elapsed=${elapsed_ms}ms tps=${tps}"
  done

  local resets
  resets="$(count_gpu_resets_since "${start_epoch}")"

  local -a sorted
  mapfile -t sorted < <(printf '%d\n' "${tps_values[@]}" | sort -n)
  local count="${#sorted[@]}"
  local median
  if (( count % 2 == 1 )); then
    median="${sorted[$(( count / 2 ))]}"
  else
    median=$(( (sorted[$(( count / 2 - 1 ))] + sorted[$(( count / 2 ))]) / 2 ))
  fi

  local tps_json
  tps_json="[$(printf '%d,' "${tps_values[@]}" | sed 's/,$//')]"

  # startup_ms=0 and peak_rss_mb=null — server was already running
  printf '{"backend":"%s","startup_ms":0,"note":"existing-server","tokens_per_sec":%s,"median_tokens_per_sec":%d,"peak_rss_mb":null,"gpu_resets":%s}' \
    "${backend_label}" \
    "${tps_json}" \
    "${median}" \
    "${resets}"
}

# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------
NOW_ISO="$(date -u +%Y-%m-%dT%H:%M:%SZ)"
HOSTNAME_VALUE="${HOSTNAME:-$(hostname -s 2>/dev/null || echo unknown)}"

declare -a RESULT_PARTS=()
SUCCESS_COUNT=0

# --use-existing-server path: no server startup, no model file needed
if [[ -n "${EXISTING_SERVER}" ]]; then
  # If --backends was also given (e.g. --backends vulkan), use it as the label.
  # Otherwise fall back to "existing-server".
  existing_label="${BACKENDS:-existing-server}"
  existing_label="${existing_label//,*/}"  # take first entry only
  existing_label="${existing_label// /}"
  log "existing-server mode: ${EXISTING_SERVER} label=${existing_label} runs=${RUNS}"
  result="$(benchmark_existing_server "${existing_label}" "${EXISTING_SERVER}")"
  if [[ "${result}" != *'"error"'* ]]; then
    (( SUCCESS_COUNT++ )) || true
  fi
  RESULT_PARTS+=("\"${existing_label}\":${result}")
else
  if ! command -v "${LLAMA_BIN}" >/dev/null 2>&1; then
    log "${LLAMA_BIN} not in PATH — cannot benchmark"
    printf '{"error":"llama_server_not_found","results":{}}\n' > "${OUTPUT_FILE}"
    exit 1
  fi

  IFS=',' read -ra BACKEND_LIST <<< "${BACKENDS}"

  for backend in "${BACKEND_LIST[@]}"; do
    backend="${backend// /}"  # trim whitespace
    [[ -z "${backend}" ]] && continue
    log "Backend: ${backend}"
    result="$(benchmark_backend "${backend}")"
    if [[ "${result}" != *'"error"'* ]]; then
      (( SUCCESS_COUNT++ )) || true
    fi
    RESULT_PARTS+=("\"${backend}\":${result}")
  done
fi

RESULTS_JSON="$(printf '%s,' "${RESULT_PARTS[@]}" | sed 's/,$//')"

MODEL_LABEL="${MODEL_PATH:-${EXISTING_SERVER}}"
python3 -c "
import json, sys
results = json.loads('{' + sys.argv[1] + '}')
output = {
    'schema_version': '1.0.0',
    'timestamp': '${NOW_ISO}',
    'host': '${HOSTNAME_VALUE}',
    'model': '${MODEL_LABEL}',
    'runs': ${RUNS},
    'results': results
}
print(json.dumps(output, indent=2))
" "${RESULTS_JSON}" > "${OUTPUT_FILE}" 2>/dev/null || {
  printf '{"timestamp":"%s","host":"%s","results":{%s}}\n' \
    "${NOW_ISO}" "${HOSTNAME_VALUE}" "${RESULTS_JSON}" > "${OUTPUT_FILE}"
}

log "Results written to ${OUTPUT_FILE}"

if [[ $SUCCESS_COUNT -eq 0 ]]; then
  log "All backends failed"
  exit 1
fi

TOTAL_BACKENDS="${#RESULT_PARTS[@]}"
log "Done: ${SUCCESS_COUNT}/${TOTAL_BACKENDS} backends benchmarked"
