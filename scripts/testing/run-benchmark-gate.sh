#!/usr/bin/env bash
# ---------------------------------------------------------------------------
# run-benchmark-gate.sh — Phase 43 (PAR-010/011) Benchmark Integration Gate
#
# Runs the harness gap eval pack against the hybrid coordinator, records the
# score into scores.sqlite, then publishes the score trend artifact.
# Exits non-zero if the score is below the regression threshold.
#
# Usage:
#   run-benchmark-gate.sh [--offline] [--threshold N] [--strategy TAG]
#                         [--cases FILE] [--trend-output FILE]
#
# Environment:
#   HYB_URL                 hybrid coordinator base URL (default: http://127.0.0.1:8003)
#   EVAL_SCORES_DB          path to scores.sqlite
#   EVAL_TREND_OUTPUT       path for eval-trend.json output
#   HYBRID_API_KEY          API key (or use HYBRID_API_KEY_FILE)
#   HYBRID_API_KEY_FILE     path to file containing API key
# ---------------------------------------------------------------------------
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
ROOT="${ROOT:-$(cd "${SCRIPT_DIR}/../.." && pwd)}"

GREEN='\033[0;32m'
RED='\033[0;31m'
YELLOW='\033[1;33m'
NC='\033[0m'

OFFLINE=0
THRESHOLD=75
STRATEGY="gap_pack_v1"
CASES_FILE="${ROOT}/data/harness-gap-eval-pack.json"
TREND_OUTPUT="${EVAL_TREND_OUTPUT:-${HOME}/.local/share/nixos-ai-stack/eval/results/eval-trend.json}"
SCORES_DB="${EVAL_SCORES_DB:-${HOME}/.local/share/nixos-ai-stack/eval/results/scores.sqlite}"

while [[ $# -gt 0 ]]; do
    case "$1" in
        --offline)        OFFLINE=1; shift ;;
        --threshold)      THRESHOLD="$2"; shift 2 ;;
        --strategy)       STRATEGY="$2"; shift 2 ;;
        --cases)          CASES_FILE="$2"; shift 2 ;;
        --trend-output)   TREND_OUTPUT="$2"; shift 2 ;;
        --help|-h)
            sed -n '/^# Usage/,/^# ---/p' "$0" | sed 's/^# \?//'
            exit 0 ;;
        *) echo "Unknown option: $1" >&2; exit 1 ;;
    esac
done

echo "━━━ Benchmark Integration Gate ━━━"
echo "  cases:     ${CASES_FILE}"
echo "  threshold: ${THRESHOLD}%"
echo "  strategy:  ${STRATEGY}"
echo "  offline:   ${OFFLINE}"
echo ""

# 1. Validate cases file
if [[ ! -f "$CASES_FILE" ]]; then
    echo -e "${RED}ERROR:${NC} cases file not found: ${CASES_FILE}" >&2
    exit 1
fi

case_count=$(python3 -c "import json; d=json.load(open('${CASES_FILE}')); print(len(d.get('cases', [])))" 2>/dev/null || echo "0")
echo -e "${GREEN}PASS:${NC} eval pack loaded (${case_count} cases)"

if [[ "${OFFLINE}" -eq 1 ]]; then
    echo -e "${YELLOW}WARN:${NC} offline mode — skipping live eval run"
else
    # 2. Run the gap eval pack
    echo "Running gap eval pack..."
    if ! python3 "${ROOT}/scripts/automation/run-gap-eval-pack.py" \
        --cases "${CASES_FILE}" \
        --scores-db "${SCORES_DB}" \
        --threshold "${THRESHOLD}" \
        --strategy "${STRATEGY}"; then
        EVAL_EXIT=$?
        echo -e "${RED}FAIL:${NC} gap eval pack below threshold (exit ${EVAL_EXIT})"
        # still publish trend before exiting
        python3 "${ROOT}/scripts/automation/publish-eval-trend.py" \
            --scores-db "${SCORES_DB}" \
            --output "${TREND_OUTPUT}" \
            --threshold "${THRESHOLD}" \
            --strategy "${STRATEGY}" 2>/dev/null || true
        exit "${EVAL_EXIT}"
    fi
    echo -e "${GREEN}PASS:${NC} gap eval pack passed (≥${THRESHOLD}%)"
fi

# 3. Publish score trend
echo "Publishing score trend..."
if python3 "${ROOT}/scripts/automation/publish-eval-trend.py" \
    --scores-db "${SCORES_DB}" \
    --output "${TREND_OUTPUT}" \
    --threshold "${THRESHOLD}" \
    --strategy "${STRATEGY}"; then
    echo -e "${GREEN}PASS:${NC} eval trend published → ${TREND_OUTPUT}"
else
    # publish-eval-trend exits 1 on regression
    echo -e "${RED}FAIL:${NC} score trend indicates regression (score below ${THRESHOLD}%)"
    exit 1
fi

echo ""
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo -e "${GREEN}OK: benchmark gate passed.${NC}"
echo "  Trend artifact: ${TREND_OUTPUT}"
