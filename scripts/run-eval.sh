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
STRATEGY_TAG="${STRATEGY_TAG:-}"   # Phase 18.2.1 — optional strategy label for leaderboard tracking
PROMPTFOO_VERSION="${PROMPTFOO_VERSION:-latest}"
PROMPTFOO_MAX_CONCURRENCY="${PROMPTFOO_MAX_CONCURRENCY:-1}"

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
        --strategy)  STRATEGY_TAG="$2"; shift 2 ;;
        --ci)        CI_MODE=1; shift ;;
        --help|-h)
            cat <<'HELP'
Usage: scripts/run-eval.sh [OPTIONS]

Options:
  --config FILE       Promptfoo config (default: ai-stack/eval/promptfoo-config.yaml)
  --output DIR        Output directory for eval results (default: ai-stack/eval/results)
  --threshold N       Minimum pass percentage (default: 70)
  --strategy LABEL    Strategy tag for leaderboard tracking (e.g. cross-encoder-v1)
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
  --max-concurrency "${PROMPTFOO_MAX_CONCURRENCY}"
)
if [[ "${CI_MODE}" == "1" ]]; then
  promptfoo_args+=(--no-table)
fi

npx "${promptfoo_args[@]}" || eval_exit=$?

# ── Parse results ─────────────────────────────────────────────────────────────
threshold_passed=0
if [[ -f "${result_file}" ]] && command -v jq >/dev/null 2>&1; then
    passed=$(jq -r '
      if (.results | type) == "object" and (.results.stats? != null)
      then (.results.stats.successes // 0)
      else (.stats.successes // 0)
      end | tonumber
    ' "${result_file}" 2>/dev/null || echo 0)
    failures=$(jq -r '
      if (.results | type) == "object" and (.results.stats? != null)
      then (.results.stats.failures // 0)
      else (.stats.failures // 0)
      end | tonumber
    ' "${result_file}" 2>/dev/null || echo 0)
    errors=$(jq -r '
      if (.results | type) == "object" and (.results.stats? != null)
      then (.results.stats.errors // 0)
      else (.stats.errors // 0)
      end | tonumber
    ' "${result_file}" 2>/dev/null || echo 0)
    total=$((passed + failures + errors))

    if [[ "${total}" -gt 0 ]]; then
        pct=$(( passed * 100 / total ))
        info ""
        info "Results: ${passed}/${total} passed (${pct}%)"
        info "Report:  ${result_file}"

        # Also write a human-readable summary.
        summary_file="${OUTPUT_DIR}/eval-${timestamp}-summary.txt"
        {
            printf 'Eval run: %s\n' "${timestamp}"
            printf 'Config:   %s\n' "${EVAL_CONFIG}"
            printf 'Passed:   %s/%s (%s%%)\n' "${passed}" "${total}" "${pct}"
            printf 'Threshold: %s%%\n' "${ACCEPTANCE_THRESHOLD}"
        } > "${summary_file}"

        # ── Append score to CSV log (8.1.4) ──────────────────────────────────
        scores_csv="${OUTPUT_DIR}/scores.csv"
        if [[ ! -f "${scores_csv}" ]]; then
            printf 'timestamp,config,passed,total,pct_passed\n' > "${scores_csv}"
        fi
        printf '%s,%s,%s,%s,%s\n' "${timestamp}" "${EVAL_CONFIG}" "${passed}" "${total}" "${pct}" >> "${scores_csv}"
        info "Score logged: ${scores_csv}"

        # ── Append score to SQLite log (8.1.4) ──────────────────────────────
        scores_db="${OUTPUT_DIR}/scores.sqlite"
        if command -v sqlite3 >/dev/null 2>&1; then
            sqlite3 "${scores_db}" <<SQL
CREATE TABLE IF NOT EXISTS eval_scores (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  timestamp TEXT NOT NULL,
  config TEXT NOT NULL,
  passed INTEGER NOT NULL,
  total INTEGER NOT NULL,
  pct_passed INTEGER NOT NULL,
  threshold INTEGER NOT NULL,
  strategy_tag TEXT
);
-- Phase 18.2.1: add strategy_tag column to existing DBs
ALTER TABLE eval_scores ADD COLUMN strategy_tag TEXT;
INSERT INTO eval_scores (timestamp, config, passed, total, pct_passed, threshold, strategy_tag)
VALUES ('${timestamp}', '$(printf "%s" "${EVAL_CONFIG}" | sed "s/'/''/g")', ${passed}, ${total}, ${pct}, ${ACCEPTANCE_THRESHOLD}, '$(printf "%s" "${STRATEGY_TAG}" | sed "s/'/''/g")');
SQL
            info "Score logged: ${scores_db}"
        else
            warn "sqlite3 not found; skipping SQLite score logging."
        fi

        # ── Regression warning: drop below 60% is always surfaced ─────────
        if [[ "${pct}" -lt 60 ]]; then
            warn "Eval regression: pass rate ${pct}% is below the 60% minimum floor — investigate immediately."
        fi

        if [[ "${pct}" -lt "${ACCEPTANCE_THRESHOLD}" ]]; then
            fail "Eval below threshold: ${pct}% < ${ACCEPTANCE_THRESHOLD}%"
        fi
        threshold_passed=1
    else
        warn "Could not parse eval results from ${result_file}"
    fi
fi

if [[ "${eval_exit}" -ne 0 ]]; then
    if [[ "${threshold_passed}" -eq 1 ]]; then
        warn "Promptfoo exited with code ${eval_exit}, but pass-rate threshold was satisfied."
    else
        fail "Promptfoo exited with code ${eval_exit}"
    fi
fi
info "Eval complete."
