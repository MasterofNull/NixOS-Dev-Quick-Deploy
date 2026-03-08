#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
ROOT="${ROOT:-$(cd "${SCRIPT_DIR}/../.." && pwd)}"
CASES_FILE="${CASES_FILE:-${ROOT}/data/harness-golden-evals.json}"
HYB_URL="${HYB_URL:-http://127.0.0.1:8003}"
MODE="${1:---offline}"
HYBRID_KEY="${HYBRID_API_KEY:-}"
HYBRID_KEY_FILE="${HYBRID_API_KEY_FILE:-/run/secrets/hybrid_coordinator_api_key}"

if [[ -z "${HYBRID_KEY}" && -r "${HYBRID_KEY_FILE}" ]]; then
  HYBRID_KEY="$(tr -d '[:space:]' < "${HYBRID_KEY_FILE}")"
fi

curl_auth_args=()
if [[ -n "${HYBRID_KEY}" ]]; then
  curl_auth_args+=(-H "X-API-Key: ${HYBRID_KEY}")
fi

fail() { echo "[FAIL] $*" >&2; exit 1; }
pass() { echo "[PASS] $*"; }
warn() { echo "[WARN] $*" >&2; }

[[ -f "$CASES_FILE" ]] || fail "missing cases file: $CASES_FILE"
command -v jq >/dev/null 2>&1 || fail "missing jq"

jq -e '.version == 1 and (.cases | type=="array" and length>0)' "$CASES_FILE" >/dev/null || fail "invalid cases schema"
pass "golden eval schema"

if [[ "$MODE" == "--offline" ]]; then
  pass "offline mode complete"
  exit 0
fi

if ! curl -fsS "${curl_auth_args[@]}" "${HYB_URL}/health" >/dev/null 2>&1; then
  warn "hybrid coordinator unavailable at ${HYB_URL}; skipping online gate"
  exit 0
fi

total="$(jq '.cases | length' "$CASES_FILE")"
ok=0

for i in $(seq 0 $((total - 1))); do
  query="$(jq -r ".cases[$i].query" "$CASES_FILE")"
  payload="$(jq -c ".cases[$i]" "$CASES_FILE")"
  if curl -fsS "${curl_auth_args[@]}" -H 'Content-Type: application/json' "${HYB_URL}/harness/eval" --data "$payload" | jq -e '.passed == true or .status == "ok"' >/dev/null; then
    ok=$((ok + 1))
  fi
done

if [[ "$ok" -lt "$total" ]]; then
  fail "regression gate failed ${ok}/${total}"
fi
pass "online regression gate ${ok}/${total}"
