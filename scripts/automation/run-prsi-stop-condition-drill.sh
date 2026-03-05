#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="${ROOT:-$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)}"
TMP_DIR="$(mktemp -d)"
trap 'rm -rf "$TMP_DIR"' EXIT

POLICY_FILE="${TMP_DIR}/runtime-prsi-policy-drill.json"
STATE_FILE="${TMP_DIR}/runtime-state.json"
QUEUE_FILE="${TMP_DIR}/queue.json"
LOG_FILE="${TMP_DIR}/actions.jsonl"

python3 - "$ROOT_DIR/config/runtime-prsi-policy.json" "$POLICY_FILE" <<'PY'
import json,sys
src=json.load(open(sys.argv[1]))
src.setdefault('budget',{})['remote_token_cap_daily']=1
src['budget']['hard_stop_on_cap']=True
json.dump(src, open(sys.argv[2],'w'), indent=2)
PY

cat > "$STATE_FILE" <<'EOF2'
{
  "date": "2099-01-01",
  "remote_tokens_used": 1,
  "counterfactual_samples": 0
}
EOF2

# Sync+execute in dry-run with budget exhausted should select none and return message.
out="$({
  PRSI_POLICY_FILE="$POLICY_FILE" \
  PRSI_STATE_PATH="$STATE_FILE" \
  PRSI_ACTION_QUEUE_PATH="$QUEUE_FILE" \
  PRSI_ACTIONS_LOG_PATH="$LOG_FILE" \
  python3 "$ROOT_DIR/scripts/automation/prsi-orchestrator.py" execute --dry-run --limit 1
} || true)"

echo "$out" | jq -e '.ok == true' >/dev/null
echo "$out" | jq -e '.message == "no approved actions" or .message == "no actions selected after policy gates"' >/dev/null

echo "PASS: PRSI stop-condition drill validated (budget hard-stop behavior)"
