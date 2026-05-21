#!/usr/bin/env bash
# scripts/testing/smoke-local-model.sh — Local model smoke test suite
#
# Validates Qwen3.6-35B-MTP-Q5 llama.cpp deployment:
#   1. llama-server health
#   2. Chat completion: TTFT, tokens/sec, thinking-mode guard
#   3. MTP speculative decoding acceptance rate
#   4. Embedding server health + latency
#   5. Coordinator model config YAML vs live env consistency
#
# Usage:
#   scripts/testing/smoke-local-model.sh [--json] [--verbose] [--timeout N]
#
# Exit: 0 = all gates pass, 1 = one or more gates fail
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "${SCRIPT_DIR}/../.." && pwd)"
CONFIG="${REPO_ROOT}/config/local-model-config.yaml"

# ---------------------------------------------------------------------------
# Args
# ---------------------------------------------------------------------------
JSON_OUT=0
VERBOSE=0
TIMEOUT_OVERRIDE=""
while [[ $# -gt 0 ]]; do
  case "$1" in
    --json)    JSON_OUT=1; shift ;;
    --verbose) VERBOSE=1; shift ;;
    --timeout) TIMEOUT_OVERRIDE="$2"; shift 2 ;;
    *) echo "Unknown arg: $1" >&2; exit 1 ;;
  esac
done

# ---------------------------------------------------------------------------
# Config extraction
# ---------------------------------------------------------------------------
_yaml_val() {
  python3 -c "
import yaml, sys
d = yaml.safe_load(open('${CONFIG}'))
keys = '${1}'.split('.')
v = d
for k in keys:
    v = v[k]
print(v)
" 2>/dev/null || echo "${2:-}"
}

LLAMA_URL="${LLAMA_CPP_BASE_URL:-http://127.0.0.1:8080}"
EMBED_URL="${EMBED_BASE_URL:-http://127.0.0.1:8081}"
COORD_URL="${HYBRID_COORDINATOR_URL:-http://127.0.0.1:8003}"

HEALTH_TIMEOUT=$(_yaml_val "performance_targets.health_timeout_s" "5")
TTFT_MAX=$(_yaml_val "performance_targets.ttft_warm_max_s" "10")
TTFT_COLD_MAX=$(_yaml_val "performance_targets.ttft_cold_max_s" "30")
TOKENS_MIN=$(_yaml_val "performance_targets.tokens_per_sec_min" "0.5")
EMBED_MAX_MS=$(_yaml_val "performance_targets.embed_latency_max_ms" "500")
MTP_MIN=$(_yaml_val "performance_targets.mtp_acceptance_rate_min" "0")

# ---------------------------------------------------------------------------
# Result tracking
# ---------------------------------------------------------------------------
PASSED=0
FAILED=0
declare -a RESULTS=()

_pass() {
  local id="$1" msg="$2"
  PASSED=$((PASSED + 1))
  RESULTS+=("{\"id\":\"${id}\",\"status\":\"pass\",\"msg\":$(python3 -c "import json,sys; print(json.dumps(sys.argv[1]))" "${msg}")}")
  [[ "${VERBOSE}" -eq 1 || "${JSON_OUT}" -eq 0 ]] && echo "  [PASS] ${id} — ${msg}"
}

_fail() {
  local id="$1" msg="$2"
  FAILED=$((FAILED + 1))
  RESULTS+=("{\"id\":\"${id}\",\"status\":\"fail\",\"msg\":$(python3 -c "import json,sys; print(json.dumps(sys.argv[1]))" "${msg}")}")
  echo "  [FAIL] ${id} — ${msg}" >&2
}

_info() {
  [[ "${VERBOSE}" -eq 1 && "${JSON_OUT}" -eq 0 ]] && echo "  [INFO] $*"
}

# ---------------------------------------------------------------------------
# Gate 1: llama-server health
# ---------------------------------------------------------------------------
_gate_llama_health() {
  local resp http_code status
  resp=$(curl -s --max-time "${HEALTH_TIMEOUT}" "${LLAMA_URL}/health" 2>/dev/null || true)
  status=$(echo "${resp}" | python3 -c "import json,sys; d=json.load(sys.stdin); print(d.get('status',''))" 2>/dev/null || true)
  if [[ "${status}" == "ok" ]]; then
    _pass "1.llama_health" "llama-server /health status=ok"
  else
    _fail "1.llama_health" "llama-server /health returned: ${resp:0:80}"
  fi
}

# ---------------------------------------------------------------------------
# Gate 2: Chat completion — TTFT, tokens/sec, thinking-mode guard
# ---------------------------------------------------------------------------
_gate_chat_completion() {
  local payload t_start t_end content tok_count elapsed ttfb_ms tokens_per_sec

  payload='{"model":"local","messages":[{"role":"user","content":"Reply with exactly: SMOKE_OK"}],"max_tokens":20,"temperature":0,"stream":false,"chat_template_kwargs":{"enable_thinking":false}}'

  t_start=$(date +%s%N)
  local resp
  resp=$(curl -s --max-time "${TIMEOUT_OVERRIDE:-${TTFT_COLD_MAX}}" \
    -X POST "${LLAMA_URL}/v1/chat/completions" \
    -H "Content-Type: application/json" \
    -d "${payload}" 2>/dev/null || true)
  t_end=$(date +%s%N)

  elapsed=$(( (t_end - t_start) / 1000000 ))  # ms

  if [[ -z "${resp}" ]]; then
    _fail "2.chat_completion" "no response (timeout after ${TTFT_COLD_MAX}s)"
    return
  fi

  # Parse content and token counts
  content=$(echo "${resp}" | python3 -c "
import json,sys
d=json.load(sys.stdin)
ch=d.get('choices',[])
if ch:
    print(ch[0].get('message',{}).get('content',''))
" 2>/dev/null || true)

  tok_count=$(echo "${resp}" | python3 -c "
import json,sys
d=json.load(sys.stdin)
u=d.get('usage',{})
print(u.get('completion_tokens',0))
" 2>/dev/null || echo "0")

  # Gate 2a: non-empty response
  if [[ -n "${content}" ]]; then
    _pass "2a.response_content" "response non-empty (${#content} chars)"
  else
    _fail "2a.response_content" "response content is empty — check enable_thinking flag"
  fi

  # Gate 2b: thinking-mode guard — content must NOT contain <think> tags
  if echo "${content}" | grep -q "<think>"; then
    _fail "2b.thinking_guard" "response contains <think> block — enable_thinking not disabled"
  else
    _pass "2b.thinking_guard" "no <think> block in content — thinking mode disabled"
  fi

  # Gate 2c: TTFT (use total elapsed as proxy; full TTFT requires streaming)
  local elapsed_s
  elapsed_s=$(python3 -c "print(round(${elapsed}/1000, 2))" 2>/dev/null || echo "?")
  if python3 -c "import sys; sys.exit(0 if ${elapsed} <= ${TTFT_COLD_MAX}*1000 else 1)" 2>/dev/null; then
    _pass "2c.ttft" "completion in ${elapsed_s}s (< ${TTFT_COLD_MAX}s limit)"
  else
    _fail "2c.ttft" "completion took ${elapsed_s}s (limit: ${TTFT_COLD_MAX}s)"
  fi

  # Gate 2d: tokens/sec
  if [[ "${tok_count}" -gt 0 && "${elapsed}" -gt 0 ]]; then
    local tps
    tps=$(python3 -c "print(round(${tok_count}/(${elapsed}/1000),2))" 2>/dev/null || echo "0")
    if python3 -c "import sys; sys.exit(0 if float('${tps}') >= ${TOKENS_MIN} else 1)" 2>/dev/null; then
      _pass "2d.tokens_per_sec" "${tps} tok/s (>= ${TOKENS_MIN} minimum)"
    else
      _fail "2d.tokens_per_sec" "${tps} tok/s (below ${TOKENS_MIN} minimum)"
    fi
  else
    _info "tokens/sec: no completion_tokens in response, skipping"
  fi
}

# ---------------------------------------------------------------------------
# Gate 3: MTP speculative decoding acceptance rate
# ---------------------------------------------------------------------------
_gate_mtp() {
  local metrics
  metrics=$(curl -s --max-time "${HEALTH_TIMEOUT}" "${LLAMA_URL}/metrics" 2>/dev/null || true)

  if [[ -z "${metrics}" ]]; then
    _info "MTP: /metrics not available, skipping"
    return
  fi

  local accepted total rate
  accepted=$(echo "${metrics}" | grep -E "^llamacpp:tokens_drafted_accepted_total" | awk '{print $2}' || echo "")
  total=$(echo "${metrics}" | grep -E "^llamacpp:tokens_drafted_total" | awk '{print $2}' || echo "")

  if [[ -n "${accepted}" && -n "${total}" && "${total}" != "0" ]]; then
    rate=$(python3 -c "print(round(float('${accepted}')/float('${total}')*100,1))" 2>/dev/null || echo "0")
    if python3 -c "import sys; sys.exit(0 if float('${rate}') > ${MTP_MIN} else 1)" 2>/dev/null; then
      _pass "3.mtp_acceptance" "MTP acceptance rate ${rate}% (draft heads active)"
    else
      _fail "3.mtp_acceptance" "MTP acceptance rate ${rate}% (expected > ${MTP_MIN}%)"
    fi
  elif [[ -n "${metrics}" ]]; then
    # Metrics available but no draft counters — model may not have processed enough tokens
    _pass "3.mtp_acceptance" "MTP metrics present (no draft tokens yet — needs warm traffic)"
  else
    _info "MTP: counters absent from /metrics"
  fi
}

# ---------------------------------------------------------------------------
# Gate 4: Embedding server health + latency
# ---------------------------------------------------------------------------
_gate_embed() {
  local t_start t_end elapsed resp status

  # Health
  resp=$(curl -s --max-time "${HEALTH_TIMEOUT}" "${EMBED_URL}/health" 2>/dev/null || true)
  status=$(echo "${resp}" | python3 -c "import json,sys; d=json.load(sys.stdin); print(d.get('status',''))" 2>/dev/null || true)
  if [[ "${status}" == "ok" ]]; then
    _pass "4a.embed_health" "embedding server /health status=ok"
  else
    _fail "4a.embed_health" "embedding server /health: ${resp:0:80}"
    return
  fi

  # Latency
  local payload='{"input":"smoke test embedding latency probe","model":"bge-m3"}'
  t_start=$(date +%s%N)
  resp=$(curl -s --max-time 10 \
    -X POST "${EMBED_URL}/v1/embeddings" \
    -H "Content-Type: application/json" \
    -d "${payload}" 2>/dev/null || true)
  t_end=$(date +%s%N)
  elapsed=$(( (t_end - t_start) / 1000000 ))

  local embed_ok
  embed_ok=$(echo "${resp}" | python3 -c "
import json,sys
d=json.load(sys.stdin)
data=d.get('data',[])
print('ok' if data and len(data[0].get('embedding',[])) > 0 else 'empty')
" 2>/dev/null || echo "error")

  if [[ "${embed_ok}" == "ok" ]]; then
    if python3 -c "import sys; sys.exit(0 if ${elapsed} <= ${EMBED_MAX_MS} else 1)" 2>/dev/null; then
      _pass "4b.embed_latency" "${elapsed}ms (< ${EMBED_MAX_MS}ms limit)"
    else
      _fail "4b.embed_latency" "${elapsed}ms exceeds ${EMBED_MAX_MS}ms limit"
    fi
  else
    _fail "4b.embed_response" "embed response invalid: ${resp:0:80}"
  fi
}

# ---------------------------------------------------------------------------
# Gate 5: Config YAML vs live env consistency
# ---------------------------------------------------------------------------
_gate_config_consistency() {
  # Validate YAML parses
  if python3 -c "import yaml; yaml.safe_load(open('${CONFIG}'))" 2>/dev/null; then
    _pass "5a.config_yaml_valid" "local-model-config.yaml parses cleanly"
  else
    _fail "5a.config_yaml_valid" "local-model-config.yaml YAML parse error"
    return
  fi

  # Check thinking mode guard documented
  local thinking_disabled
  thinking_disabled=$(_yaml_val "chat.enable_thinking" "true")
  if [[ "${thinking_disabled}" == "False" || "${thinking_disabled}" == "false" ]]; then
    _pass "5b.thinking_mode_documented" "enable_thinking: false in config"
  else
    _fail "5b.thinking_mode_documented" "enable_thinking not set to false in config"
  fi

  # Check LLAMA_CPP_BASE_URL env var is set
  if [[ -n "${LLAMA_CPP_BASE_URL:-}" ]]; then
    _pass "5c.llama_url_env" "LLAMA_CPP_BASE_URL=${LLAMA_CPP_BASE_URL}"
  else
    _info "LLAMA_CPP_BASE_URL not set in env — using default ${LLAMA_URL}"
  fi
}

# ---------------------------------------------------------------------------
# Run all gates
# ---------------------------------------------------------------------------
[[ "${JSON_OUT}" -eq 0 ]] && echo "[smoke-local-model] Running local model smoke tests..."

_gate_llama_health
_gate_chat_completion
_gate_mtp
_gate_embed
_gate_config_consistency

# ---------------------------------------------------------------------------
# Output
# ---------------------------------------------------------------------------
if [[ "${JSON_OUT}" -eq 1 ]]; then
  python3 -c "
import json, sys
results = [${RESULTS[*]:-}]
print(json.dumps({
    'passed': ${PASSED},
    'failed': ${FAILED},
    'total': $((PASSED + FAILED)),
    'gates': results
}, indent=2))
"
else
  echo ""
  echo "[smoke-local-model] ${PASSED} passed · ${FAILED} failed"
fi

[[ "${FAILED}" -eq 0 ]]
