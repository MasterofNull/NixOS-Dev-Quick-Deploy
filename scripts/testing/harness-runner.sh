#!/usr/bin/env bash
# harness-runner.sh — unified QA harness entry point (Phase 44 / PAR-002)
#
# Chains all harness gates in order:
#   1. Schema validation   — eval pack JSON schema check
#   2. Gap eval            — run-gap-eval-pack.py against hybrid-coordinator
#   3. Regression gate     — run-benchmark-gate.sh (trend + threshold)
#   4. Parity scorecard    — repo-structure-lint.sh + tier0-validation-gate.sh
#
# Exit codes:
#   0  all gates passed
#   1  one or more gates failed
#   2  usage / configuration error
#
# Options:
#   --offline              skip live-service eval (schema + parity only)
#   --threshold N          eval pass threshold (default: 70, passed to gate)
#   --strategy TAG         eval strategy tag (default: harness-gap)
#   --cases FILE           eval cases file (default: data/harness-gap-eval-pack.json)
#   --trend-output FILE    trend JSON output path
#   --skip-parity          skip parity scorecard gate
#   --skip-schema          skip schema validation gate
#   --skip-eval            skip live eval + regression gate
#   --verbose              verbose output from sub-gates

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "$SCRIPT_DIR/../.." && pwd)"

# ── defaults ──────────────────────────────────────────────────────────────────
OFFLINE=false
THRESHOLD=70
STRATEGY="harness-gap"
CASES_FILE="$REPO_ROOT/data/harness-gap-eval-pack.json"
TREND_OUTPUT="$REPO_ROOT/data/eval-trend.json"
SKIP_PARITY=false
SKIP_SCHEMA=false
SKIP_EVAL=false
VERBOSE=false

# ── parse args ────────────────────────────────────────────────────────────────
while [[ $# -gt 0 ]]; do
  case "$1" in
    --offline)       OFFLINE=true; shift ;;
    --threshold)     THRESHOLD="$2"; shift 2 ;;
    --strategy)      STRATEGY="$2"; shift 2 ;;
    --cases)         CASES_FILE="$2"; shift 2 ;;
    --trend-output)  TREND_OUTPUT="$2"; shift 2 ;;
    --skip-parity)   SKIP_PARITY=true; shift ;;
    --skip-schema)   SKIP_SCHEMA=true; shift ;;
    --skip-eval)     SKIP_EVAL=true; shift ;;
    --verbose)       VERBOSE=true; shift ;;
    -h|--help)
      grep "^#" "$0" | head -30 | sed 's/^# \?//'
      exit 0 ;;
    *)
      echo "[harness-runner] unknown option: $1" >&2; exit 2 ;;
  esac
done

# ── helpers ───────────────────────────────────────────────────────────────────
PASS=0
FAIL=0
SKIP=0

log()  { echo "[harness-runner] $*"; }
ok()   { echo "[harness-runner] ✓ $*"; ((PASS++)) || true; }
fail() { echo "[harness-runner] ✗ $*" >&2; ((FAIL++)) || true; }
skip() { echo "[harness-runner] - $*"; ((SKIP++)) || true; }

run_gate() {
  local name="$1"; shift
  if $VERBOSE; then
    "$@"
  else
    "$@" >/dev/null 2>&1
  fi
}

# ── gate 1: schema validation ─────────────────────────────────────────────────
if $SKIP_SCHEMA; then
  skip "schema validation (--skip-schema)"
else
  log "gate 1/4: schema validation — $CASES_FILE"
  if [[ ! -f "$CASES_FILE" ]]; then
    fail "cases file not found: $CASES_FILE"
  else
    SCHEMA_ERR=$(python3 - <<PYEOF 2>&1
import json, sys
try:
    data = json.load(open("$CASES_FILE"))
    assert "cases" in data, "missing 'cases' key"
    assert isinstance(data["cases"], list), "'cases' must be a list"
    assert len(data["cases"]) >= 1, "eval pack must have at least 1 case"
    for i, c in enumerate(data["cases"]):
        for field in ("id", "query", "expected_keywords", "mode"):
            assert field in c, f"case[{i}] missing field '{field}'"
    print("ok")
except Exception as e:
    print(f"error: {e}", file=sys.stderr)
    sys.exit(1)
PYEOF
    )
    if [[ "$SCHEMA_ERR" == "ok" ]]; then
      CASE_COUNT=$(python3 -c "import json; d=json.load(open('$CASES_FILE')); print(len(d['cases']))")
      ok "schema valid — $CASE_COUNT cases"
    else
      fail "schema invalid: $SCHEMA_ERR"
    fi
  fi
fi

# ── gate 2+3: eval + regression (skipped if --offline or --skip-eval) ─────────
if $SKIP_EVAL || $OFFLINE; then
  skip "live eval + regression gate (offline/skip-eval mode)"
else
  log "gate 2/4: gap eval — $CASES_FILE"
  EVAL_SCRIPT="$REPO_ROOT/scripts/automation/run-gap-eval-pack.py"
  if [[ ! -x "$EVAL_SCRIPT" ]]; then
    fail "eval script not executable: $EVAL_SCRIPT"
  else
    if run_gate "gap-eval" python3 "$EVAL_SCRIPT" \
        --cases "$CASES_FILE" \
        --threshold "$THRESHOLD" \
        --strategy "$STRATEGY"; then
      ok "gap eval passed (threshold ≥ $THRESHOLD%)"
    else
      fail "gap eval did not meet threshold ($THRESHOLD%)"
    fi
  fi

  log "gate 3/4: regression gate + trend"
  GATE_SCRIPT="$REPO_ROOT/scripts/testing/run-benchmark-gate.sh"
  if [[ ! -x "$GATE_SCRIPT" ]]; then
    fail "benchmark gate not executable: $GATE_SCRIPT"
  else
    GATE_ARGS=(--threshold "$THRESHOLD" --strategy "$STRATEGY" --cases "$CASES_FILE")
    if [[ -n "${TREND_OUTPUT:-}" ]]; then
      GATE_ARGS+=(--trend-output "$TREND_OUTPUT")
    fi
    if run_gate "benchmark-gate" "$GATE_SCRIPT" "${GATE_ARGS[@]}"; then
      ok "regression gate passed"
    else
      fail "regression detected — eval score regressed below threshold"
    fi
  fi
fi

# ── gate 4: parity scorecard ──────────────────────────────────────────────────
if $SKIP_PARITY; then
  skip "parity scorecard (--skip-parity)"
else
  log "gate 4/4: parity scorecard"
  LINT_SCRIPT="$REPO_ROOT/scripts/governance/repo-structure-lint.sh"
  TIER0_SCRIPT="$REPO_ROOT/scripts/governance/tier0-validation-gate.sh"

  if [[ ! -x "$LINT_SCRIPT" ]]; then
    fail "repo-structure-lint.sh not found or not executable"
  elif run_gate "repo-lint" "$LINT_SCRIPT" --all; then
    ok "repo structure lint passed"
  else
    fail "repo structure lint failed"
  fi

  if [[ ! -x "$TIER0_SCRIPT" ]]; then
    fail "tier0-validation-gate.sh not found or not executable"
  elif run_gate "tier0" "$TIER0_SCRIPT" --ci; then
    ok "tier0 validation passed"
  else
    fail "tier0 validation failed"
  fi
fi

# ── summary ───────────────────────────────────────────────────────────────────
echo ""
echo "[harness-runner] ─────────────────────────────────────"
echo "[harness-runner]  passed: $PASS  failed: $FAIL  skipped: $SKIP"
echo "[harness-runner] ─────────────────────────────────────"

if [[ $FAIL -gt 0 ]]; then
  echo "[harness-runner] RESULT: FAIL ($FAIL gate(s) failed)" >&2
  exit 1
fi
echo "[harness-runner] RESULT: PASS"
exit 0
