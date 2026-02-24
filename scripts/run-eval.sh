#!/usr/bin/env bash
# ---------------------------------------------------------------------------
# run-eval.sh — Run Promptfoo regression eval against the local AI stack.
#
# Phase 29.4.3 — NixOS-Dev-Quick-Deploy MLOps Lifecycle Layer
#
# Usage:
#   scripts/run-eval.sh [--config FILE] [--output DIR] [--ci]
#
# Expects:
#   - llama.cpp running at LLAMA_URL (from config/service-endpoints.sh)
#   - Node.js available (from ai-dev system package or nix shell)
#   - npx in PATH (bundled with Node.js)
#
# Exit codes:
#   0 — all evals passed (or above threshold)
#   1 — evals below acceptance threshold
#   2 — setup/connectivity error
# ---------------------------------------------------------------------------
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
# shellcheck source=../config/service-endpoints.sh
source "${SCRIPT_DIR}/../config/service-endpoints.sh"

EVAL_CONFIG="${EVAL_CONFIG:-ai-stack/eval/promptfoo-config.yaml}"
OUTPUT_DIR="${OUTPUT_DIR:-ai-stack/eval/results}"
LLAMA_BASE_URL="${LLAMA_URL%/}"
ACCEPTANCE_THRESHOLD="${ACCEPTANCE_THRESHOLD:-70}"   # percent
CI_MODE="${CI_MODE:-0}"
PROMPTFOO_VERSION="${PROMPTFOO_VERSION:-latest}"

info()    { printf '\033[0;32m[run-eval] %s\033[0m\n' "$*"; }
warn()    { printf '\033[0;33m[run-eval] WARN: %s\033[0m\n' "$*" >&2; }
error()   { printf '\033[0;31m[run-eval] ERROR: %s\033[0m\n' "$*" >&2; exit 2; }
fail()    { printf '\033[0;31m[run-eval] FAIL: %s\033[0m\n' "$*" >&2; exit 1; }

# ── Parse args ────────────────────────────────────────────────────────────────
while [[ $# -gt 0 ]]; do
    case "$1" in
        --config)    EVAL_CONFIG="$2"; shift 2 ;;
        --output)    OUTPUT_DIR="$2"; shift 2 ;;
        --threshold) ACCEPTANCE_THRESHOLD="$2"; shift 2 ;;
        --ci)        CI_MODE=1; shift ;;
        --help|-h)
            cat <<'HELP'
Usage: scripts/run-eval.sh [OPTIONS]

Options:
  --config FILE       Promptfoo config (default: ai-stack/eval/promptfoo-config.yaml)
  --output DIR        Output directory for eval results (default: ai-stack/eval/results)
  --threshold N       Minimum pass percentage (default: 70)
  --ci                CI mode — strip color, exit non-zero on failure
  --help              Show this message
HELP
            exit 0 ;;
        *) error "Unknown option: $1" ;;
    esac
done

# ── Preflight: llama.cpp ──────────────────────────────────────────────────────
info "Checking llama.cpp at ${LLAMA_BASE_URL}/v1/models..."
if ! curl -sf "${LLAMA_BASE_URL}/v1/models" --max-time 10 >/dev/null; then
    error "llama.cpp not reachable at ${LLAMA_BASE_URL}. Ensure llama-cpp.service is running."
fi
info "llama.cpp: OK"

# ── Preflight: Node.js / npx ──────────────────────────────────────────────────
command -v npx >/dev/null 2>&1 || error "npx not found. Install Node.js via the ai-dev profile."

# ── Create output directory ───────────────────────────────────────────────────
mkdir -p "${OUTPUT_DIR}"
timestamp=$(date -u +%Y%m%dT%H%M%SZ)
result_file="${OUTPUT_DIR}/eval-${timestamp}.json"

# ── Run Promptfoo ─────────────────────────────────────────────────────────────
info "Running eval: ${EVAL_CONFIG}"
info "Output: ${result_file}"

eval_exit=0
promptfoo_args=(
  "promptfoo@${PROMPTFOO_VERSION}"
  eval
  --config "${EVAL_CONFIG}"
  --output "${result_file}"
)
if [[ "${CI_MODE}" == "1" ]]; then
  promptfoo_args+=(--no-table)
fi

npx "${promptfoo_args[@]}" || eval_exit=$?

# ── Parse results ─────────────────────────────────────────────────────────────
if [[ -f "${result_file}" ]] && command -v jq >/dev/null 2>&1; then
    total=$(jq '.stats.successes + .stats.failures' "${result_file}" 2>/dev/null || echo 0)
    passed=$(jq '.stats.successes' "${result_file}" 2>/dev/null || echo 0)

    if [[ "${total}" -gt 0 ]]; then
        pct=$(( passed * 100 / total ))
        info ""
        info "Results: ${passed}/${total} passed (${pct}%)"
        info "Report:  ${result_file}"

        # Also write a human-readable summary.
        summary_file="${OUTPUT_DIR}/eval-${timestamp}-summary.txt"
        {
            echo "Eval run: ${timestamp}"
            echo "Config:   ${EVAL_CONFIG}"
            echo "Passed:   ${passed}/${total} (${pct}%)"
            echo "Threshold: ${ACCEPTANCE_THRESHOLD}%"
        } > "${summary_file}"

        if [[ "${pct}" -lt "${ACCEPTANCE_THRESHOLD}" ]]; then
            fail "Eval below threshold: ${pct}% < ${ACCEPTANCE_THRESHOLD}%"
        fi
    else
        warn "Could not parse eval results from ${result_file}"
    fi
fi

[[ "${eval_exit}" -eq 0 ]] || fail "Promptfoo exited with code ${eval_exit}"
info "Eval complete."
