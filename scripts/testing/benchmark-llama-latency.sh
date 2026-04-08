#!/usr/bin/env bash
# ---------------------------------------------------------------------------
# benchmark-llama-latency.sh — Measure llama-cpp response latency metrics
#
# Tests:
#   - Time-to-first-token (TTFT)
#   - Tokens per second (TPS)
#   - End-to-end request latency
#   - Latency under varying prompt sizes
#
# Usage:
#   scripts/testing/benchmark-llama-latency.sh [--host HOST] [--port PORT] [--iterations N]
#
# Environment:
#   LLAMA_CPP_HOST  (default: 127.0.0.1)
#   LLAMA_CPP_PORT  (default: 8080)
# ---------------------------------------------------------------------------
set -euo pipefail

HOST="${LLAMA_CPP_HOST:-127.0.0.1}"
PORT="${LLAMA_CPP_PORT:-8080}"
ITERATIONS="${ITERATIONS:-5}"
BASE_URL="http://${HOST}:${PORT}"

# Parse arguments
while [[ $# -gt 0 ]]; do
  case $1 in
    --host) HOST="$2"; shift 2;;
    --port) PORT="$2"; shift 2;;
    --iterations) ITERATIONS="$2"; shift 2;;
    --help) echo "Usage: $0 [--host HOST] [--port PORT] [--iterations N]"; exit 0;;
    *) echo "Unknown option: $1"; exit 1;;
  esac
done

# Color output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
CYAN='\033[0;36m'
NC='\033[0m'

log_info() { echo -e "${CYAN}[INFO]${NC} $*"; }
log_ok() { echo -e "${GREEN}[OK]${NC} $*"; }
log_warn() { echo -e "${YELLOW}[WARN]${NC} $*"; }
log_error() { echo -e "${RED}[ERROR]${NC} $*" >&2; }

# Check if llama-cpp is running
log_info "Checking llama-cpp health at ${BASE_URL}/health..."
if ! curl -sf "${BASE_URL}/health" > /dev/null 2>&1; then
  log_error "llama-cpp is not reachable at ${BASE_URL}"
  log_error "Ensure llama-cpp server is running: systemctl status llama-cpp"
  exit 1
fi
log_ok "llama-cpp is healthy"

# Test prompts of varying sizes
declare -A TEST_PROMPTS
TEST_PROMPTS=(
  ["short"]="What is 2+2?"
  ["medium"]="Explain the difference between supervised and unsupervised learning in machine learning."
  ["long"]="Write a Python function that implements binary search, then explain its time and space complexity. Include error handling for edge cases like empty arrays or invalid input."
)

# Results storage
declare -a TTFT_RESULTS=()
declare -a TPS_RESULTS=()
declare -a E2E_RESULTS=()

# Run benchmark
log_info "Running latency benchmark (${ITERATIONS} iterations per prompt size)..."
echo ""

for prompt_size in "${!TEST_PROMPTS[@]}"; do
  prompt="${TEST_PROMPTS[$prompt_size]}"
  log_info "Benchmarking: ${prompt_size} prompt (${#prompt} chars)"
  
  prompt_ttft=()
  prompt_tps=()
  prompt_e2e=()
  
  for ((i=1; i<=ITERATIONS; i++)); do
    # Measure end-to-end latency
    start_time=$(date +%s%N)
    
    response=$(curl -s -w "\n%{http_code}" "${BASE_URL}/v1/completions" \
      -H "Content-Type: application/json" \
      -d "{
        \"prompt\": \"${prompt}\",
        \"max_tokens\": 50,
        \"temperature\": 0.1,
        \"stream\": false
      }" 2>/dev/null) || {
      log_warn "Request failed for ${prompt_size} prompt iteration ${i}"
      continue
    }
    
    end_time=$(date +%s%N)
    http_code=$(echo "$response" | tail -n1)
    body=$(echo "$response" | head -n-1)
    
    if [[ "$http_code" != "200" ]]; then
      log_warn "HTTP ${http_code} for ${prompt_size} prompt iteration ${i}"
      continue
    fi
    
    # Calculate end-to-end latency in ms
    e2e_ms=$(( (end_time - start_time) / 1000000 ))
    prompt_e2e+=("$e2e_ms")
    
    # Extract tokens generated
    tokens_generated=$(echo "$body" | python3 -c "import sys,json; d=json.load(sys.stdin); print(len(d.get('choices',[{}])[0].get('text','').split()))" 2>/dev/null || echo "0")
    
    # Calculate TPS
    if [[ "$e2e_ms" -gt 0 && "$tokens_generated" -gt 0 ]]; then
      tps=$(echo "scale=2; $tokens_generated / ($e2e_ms / 1000)" | bc 2>/dev/null || echo "0")
      prompt_tps+=("$tps")
    fi
    
    # Note: TTFT requires streaming mode, estimate from E2E
    # For non-streaming, TTFT ≈ E2E (server processes all before returning)
    prompt_ttft+=("$e2e_ms")
    
    printf "  Iteration %d: E2E=%dms, Tokens=%s, TPS=%s\n" "$i" "$e2e_ms" "$tokens_generated" "${tps:-0}"
  done
  
  # Calculate averages
  if [[ ${#prompt_e2e[@]} -gt 0 ]]; then
    avg_e2e=$(echo "${prompt_e2e[@]}" | tr ' ' '\n' | awk '{sum+=$1} END {printf "%.0f", sum/NR}')
    avg_ttft=$(echo "${prompt_ttft[@]}" | tr ' ' '\n' | awk '{sum+=$1} END {printf "%.0f", sum/NR}')
    avg_tps=$(echo "${prompt_tps[@]}" | tr ' ' '\n' | awk '{sum+=$1} END {printf "%.2f", sum/NR}')
    
    TTFT_RESULTS+=("${prompt_size}:${avg_ttft}")
    TPS_RESULTS+=("${prompt_size}:${avg_tps}")
    E2E_RESULTS+=("${prompt_size}:${avg_e2e}")
    
    echo -e "  ${GREEN}Average${NC}: E2E=${avg_e2e}ms, TTFT≈${avg_ttft}ms, TPS=${avg_tps}"
  fi
  echo ""
done

# Summary
echo "================================================================"
log_info "Benchmark Summary"
echo "================================================================"
printf "%-10s | %-10s | %-10s | %-10s\n" "Size" "E2E (ms)" "TTFT (ms)" "TPS"
echo "-----------|------------|------------|-----------"

for result in "${E2E_RESULTS[@]}"; do
  size="${result%%:*}"
  e2e="${result##*:}"
  
  ttft="${TTFT_RESULTS[@]// /$'\n'}"
  ttft_val=$(echo "$ttft" | grep "^${size}:" | cut -d: -f2)
  
  tps="${TPS_RESULTS[@]// /$'\n'}"
  tps_val=$(echo "$tps" | grep "^${size}:" | cut -d: -f2)
  
  printf "%-10s | %-10s | %-10s | %-10s\n" "$size" "$e2e" "${ttft_val:-N/A}" "${tps_val:-N/A}"
done

echo ""
log_ok "Benchmark complete"

# Health assessment
avg_all_e2e=$(echo "${E2E_RESULTS[@]}" | tr ' ' '\n' | cut -d: -f2 | awk '{sum+=$1} END {printf "%.0f", sum/NR}')

echo ""
if [[ "$avg_all_e2e" -lt 1000 ]]; then
  log_ok "Latency is excellent (avg ${avg_all_e2e}ms)"
elif [[ "$avg_all_e2e" -lt 3000 ]]; then
  log_info "Latency is acceptable (avg ${avg_all_e2e}ms)"
else
  log_warn "Latency is high (avg ${avg_all_e2e}ms) - consider optimizing model or hardware"
fi

exit 0
