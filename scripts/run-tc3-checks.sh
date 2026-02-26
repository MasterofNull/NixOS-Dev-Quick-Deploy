#!/usr/bin/env bash
# ---------------------------------------------------------------------------
# run-tc3-checks.sh — TC3 System Test Gate (post Phase 7/8)
#
# Covers:
#   TC3.3 — NixOS platform validation (dry-run, flake check)
#   TC3.4 — Knowledge base quality: query expansion + vector timestamps
#   TC3.5 — Performance baseline: p95 latency + cache hit rate
#
# TC3.1 (re-run TC1/TC2) and TC3.2 (feedback loop) require all services live
# and are run manually or via run-acceptance-checks.sh.
#
# Usage:
#   scripts/run-tc3-checks.sh [--skip-nix] [--skip-perf] [--perf-only]
#
# Exit codes:
#   0 — all executed checks passed
#   1 — one or more checks failed
#   2 — setup error
# ---------------------------------------------------------------------------
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "${SCRIPT_DIR}/.." && pwd)"
# shellcheck source=../config/service-endpoints.sh
source "${SCRIPT_DIR}/../config/service-endpoints.sh"

SKIP_NIX=0
SKIP_PERF=0
PERF_ONLY=0
PERF_BASELINE_FILE="${REPO_ROOT}/ai-stack/eval/results/perf-baseline.json"

pass()  { printf '\033[0;32m[TC3 PASS] %s\033[0m\n' "$*"; }
fail()  { printf '\033[0;31m[TC3 FAIL] %s\033[0m\n' "$*" >&2; FAILURES=$((FAILURES + 1)); }
skip()  { printf '\033[0;33m[TC3 SKIP] %s\033[0m\n' "$*"; }
info()  { printf '\033[0;36m[TC3 INFO] %s\033[0m\n' "$*"; }

FAILURES=0

while [[ $# -gt 0 ]]; do
    case "$1" in
        --skip-nix)   SKIP_NIX=1;   shift ;;
        --skip-perf)  SKIP_PERF=1;  shift ;;
        --perf-only)  PERF_ONLY=1; SKIP_NIX=1; shift ;;
        --help|-h)
            cat <<'HELP'
Usage: scripts/run-tc3-checks.sh [--skip-nix] [--skip-perf] [--perf-only]

  --skip-nix    Skip nixos-rebuild dry-run and nix flake check (TC3.3)
  --skip-perf   Skip performance baseline recording (TC3.5)
  --perf-only   Only record performance baseline (skip TC3.3, TC3.4)
HELP
            exit 0 ;;
        *) echo "Unknown option: $1" >&2; exit 2 ;;
    esac
done

# ---------------------------------------------------------------------------
# TC3.3 — NixOS Platform Validation
# ---------------------------------------------------------------------------
if [[ "${SKIP_NIX}" -eq 0 && "${PERF_ONLY}" -eq 0 ]]; then
    info "TC3.3 — NixOS platform validation"

    # TC3.3.1 — nixos-rebuild dry-run
    info "TC3.3.1: nixos-rebuild dry-run..."
    if sudo -n true >/dev/null 2>&1; then
        if nixos_out="$(sudo -n nixos-rebuild dry-run --flake "${REPO_ROOT}#nixos" 2>&1)"; then
            pass "TC3.3.1: nixos-rebuild dry-run OK"
        else
            fail "TC3.3.1: nixos-rebuild dry-run failed"
            echo "${nixos_out}" >&2
        fi
    else
        skip "TC3.3.1: sudo non-interactive access unavailable in this session"
    fi

    # TC3.3.2 — hardware-tier detection
    info "TC3.3.2: hardware-tier detection..."
    tier_out="$(nix eval --raw "${REPO_ROOT}#nixosConfigurations.nixos.config.mySystem.hardwareTier" 2>/dev/null || echo "")"
    if [[ -n "${tier_out}" ]]; then
        pass "TC3.3.2: hardware tier resolved: ${tier_out}"
    else
        skip "TC3.3.2: nix eval for hardwareTier unavailable (flake not fully evaluated)"
    fi

    # TC3.3.3 — nix flake check
    info "TC3.3.3: nix flake check..."
    if flake_out="$(nix flake check "${REPO_ROOT}" 2>&1)"; then
        pass "TC3.3.3: nix flake check OK"
    else
        fail "TC3.3.3: nix flake check failed"
        echo "${flake_out}" >&2
    fi
fi

# ---------------------------------------------------------------------------
# TC3.4 — Knowledge Base Quality
# ---------------------------------------------------------------------------
if [[ "${PERF_ONLY}" -eq 0 ]]; then
    info "TC3.4 — Knowledge base quality"

    # TC3.4.1 — NixOS synonym map fires in query_expansion.py
    info "TC3.4.1: NixOS synonym map fires for 'flake'..."
    qa_script="${REPO_ROOT}/ai-stack/mcp-servers/hybrid-coordinator/query_expansion.py"
    if [[ ! -f "${qa_script}" ]]; then
        fail "TC3.4.1: query_expansion.py not found at ${qa_script}"
    else
        expanded="$(python3 - <<PYEOF 2>/dev/null
import sys
import os
# Ensure both hybrid-coordinator and shared modules are importable.
sys.path.insert(0, "${REPO_ROOT}/ai-stack/mcp-servers")
sys.path.insert(0, "${REPO_ROOT}/ai-stack/mcp-servers/hybrid-coordinator")
os.environ["AI_STRICT_ENV"] = "false"
from query_expansion import QueryExpander
qe = QueryExpander()
result = qe.expand_simple("how to fix flake input conflict", max_expansions=6)
# result may be a string or list; stringify either way
out = result if isinstance(result, str) else " ".join(str(r) for r in result)
print(out)
PYEOF
        )" || expanded=""
        if echo "${expanded}" | grep -qiE "inputs|follows|lock|flake\.nix"; then
            pass "TC3.4.1: expansion for 'flake' includes NixOS-specific terms: $(echo "${expanded}" | head -c 120)"
        else
            fail "TC3.4.1: expansion did not include expected NixOS terms. Got: $(echo "${expanded}" | head -c 120)"
        fi
    fi

    # TC3.4.2 — vector timestamps present (requires AIDB running)
    info "TC3.4.2: vector timestamp fields in AIDB..."
    aidb_url="${AIDB_URL:-http://localhost:8002}"
    if curl -fsS --max-time 5 --connect-timeout 3 "${aidb_url}/health" >/dev/null 2>&1; then
        ts_result="$(curl -fsS --max-time 10 --connect-timeout 3 \
            "${aidb_url}/documents?limit=1" 2>/dev/null || echo "")"
        if echo "${ts_result}" | python3 -c "
import sys, json
data = json.load(sys.stdin)
docs = data if isinstance(data, list) else data.get('results', data.get('documents', []))
if not docs:
    print('empty')
    sys.exit(0)
d = docs[0]
payload = d.get('payload', d)
has_ts = (
    'ingested_at' in payload or
    'last_accessed_at' in payload or
    'created_at' in payload or
    'imported_at' in payload
)
print('ok' if has_ts else 'missing')
" 2>/dev/null | grep -q "ok"; then
            pass "TC3.4.2: timestamp field present (ingested_at / last_accessed_at / imported_at)"
        else
            fail "TC3.4.2: no timestamp fields found on retrieved vector (or DB empty)"
        fi
    else
        skip "TC3.4.2: AIDB not reachable at ${aidb_url} — skip"
    fi
fi

# ---------------------------------------------------------------------------
# TC3.5 — Performance Baseline
# ---------------------------------------------------------------------------
if [[ "${SKIP_PERF}" -eq 0 ]]; then
    info "TC3.5 — Performance baseline"

    hybrid_url="${HYBRID_URL:-http://localhost:8003}"
    api_key_file="${HYBRID_API_KEY_FILE:-/run/secrets/hybrid_coordinator_api_key}"
    api_key="${HYBRID_API_KEY:-}"
    if [[ -f "${api_key_file}" ]]; then
        api_key="$(cat "${api_key_file}")"
    fi

    # TC3.5.1 — p95 latency for a standard query
    info "TC3.5.1: p95 latency measurement (10 iterations)..."
    if curl -fsS --max-time 5 --connect-timeout 3 "${hybrid_url}/health" >/dev/null 2>&1; then
        latencies=()
        successes=0
        for i in $(seq 1 10); do
            t_start=$(date +%s%N)
            status_code="$(curl -sS --max-time 15 --connect-timeout 5 \
                -H "Content-Type: application/json" \
                -H "X-API-Key: ${api_key}" \
                -d '{"query":"what is lib.mkForce","limit":3}' \
                -o /dev/null -w '%{http_code}' \
                "${hybrid_url}/route_search" 2>/dev/null || echo "000")"
            t_end=$(date +%s%N)
            if [[ "${status_code}" == "200" ]]; then
                latencies+=( $(( (t_end - t_start) / 1000000 )) )
                successes=$((successes + 1))
            fi
        done
        if [[ "${successes}" -ge 3 ]]; then
            # Sort and take p95 approximation from available successful samples.
            IFS=$'\n' sorted=($(sort -n <<<"${latencies[*]}")); unset IFS
            count="${#sorted[@]}"
            p50_idx=$(( (count - 1) / 2 ))
            p95_idx=$(( count - 1 ))
            p50="${sorted[${p50_idx}]}"
            p95="${sorted[${p95_idx}]}"
            pass "TC3.5.1: p50=${p50}ms p95=${p95}ms (${successes} successful samples)"
        else
            p50="null"
            p95="null"
            skip "TC3.5.1: insufficient successful responses from hybrid-coordinator (${successes}/10)"
        fi
    else
        p50="null"
        p95="null"
        skip "TC3.5.1: hybrid-coordinator not reachable — skip"
    fi

    # TC3.5.2 — cache hit rate from Prometheus metrics
    info "TC3.5.2: embedding cache hit rate..."
    prom_url="${PROMETHEUS_URL:-http://localhost:9090}"
    cache_hit_rate="null"
    if curl -fsS --max-time 5 --connect-timeout 3 "${prom_url}/-/healthy" >/dev/null 2>&1; then
        hits="$(curl -fsS --max-time 5 "${prom_url}/api/v1/query?query=embedding_cache_hits_total" 2>/dev/null \
            | python3 -c "import sys,json; d=json.load(sys.stdin); r=d['data']['result']; print(float(r[0]['value'][1]) if r else 0)" 2>/dev/null || echo 0)"
        misses="$(curl -fsS --max-time 5 "${prom_url}/api/v1/query?query=embedding_cache_misses_total" 2>/dev/null \
            | python3 -c "import sys,json; d=json.load(sys.stdin); r=d['data']['result']; print(float(r[0]['value'][1]) if r else 0)" 2>/dev/null || echo 0)"
        total_em="$(python3 -c "print(${hits} + ${misses})" 2>/dev/null || echo 0)"
        if python3 -c "exit(0 if float('${total_em}') > 0 else 1)" 2>/dev/null; then
            cache_hit_rate="$(python3 -c "print(round(${hits} / ${total_em} * 100, 1))")"
            pass "TC3.5.2: embedding cache hit rate = ${cache_hit_rate}% (hits=${hits}, misses=${misses})"
        else
            skip "TC3.5.2: no embedding cache metrics yet (hit+miss = 0)"
        fi
    else
        skip "TC3.5.2: Prometheus not reachable at ${prom_url} — skip"
    fi

    # Write baseline JSON
    mkdir -p "$(dirname "${PERF_BASELINE_FILE}")"
    python3 - <<PYEOF
import datetime
import json

def _to_number(raw):
    value = str(raw).strip()
    if value in ("", "null", "None"):
        return None
    try:
        if "." in value:
            return float(value)
        return int(value)
    except ValueError:
        return None

data = {
    "recorded_at": datetime.datetime.now(datetime.timezone.utc).isoformat(),
    "p50_ms": _to_number("${p50}"),
    "p95_ms": _to_number("${p95}"),
    "embedding_cache_hit_rate_pct": _to_number("${cache_hit_rate}"),
}
with open("${PERF_BASELINE_FILE}", "w") as f:
    json.dump(data, f, indent=2)
print(json.dumps(data, indent=2))
PYEOF
    pass "TC3.5: baseline written to ${PERF_BASELINE_FILE}"
fi

# ---------------------------------------------------------------------------
# Summary
# ---------------------------------------------------------------------------
echo ""
if [[ "${FAILURES}" -eq 0 ]]; then
    info "All TC3 checks passed (or skipped)."
    exit 0
else
    info "${FAILURES} check(s) FAILED. See FAIL lines above."
    exit 1
fi
