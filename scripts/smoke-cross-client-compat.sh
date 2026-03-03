#!/usr/bin/env bash
set -euo pipefail

ROOT="${ROOT:-/home/hyperd/Documents/NixOS-Dev-Quick-Deploy}"
HYB_URL="${HYB_URL:-http://127.0.0.1:8003}"
SWB_URL="${SWB_URL:-http://127.0.0.1:8085}"

pass() { echo "[PASS] $*"; }
warn() { echo "[WARN] $*" >&2; }
fail() { echo "[FAIL] $*" >&2; exit 1; }

if ! curl -fsS "${HYB_URL}/health" >/dev/null 2>&1; then
  warn "hybrid coordinator unavailable; cross-client smoke skipped"
  exit 0
fi

# Client 1: raw HTTP
curl -fsS "${HYB_URL}/workflow/plan?q=cross-client-smoke" | jq -e '.phases | length >= 5' >/dev/null || fail "HTTP client failed"
pass "HTTP client workflow plan"

# Client 2: JS RPC wrapper
node "${ROOT}/scripts/harness-rpc.js" plan --query "cross client rpc smoke" >/tmp/cross-client-rpc.json
jq -e '.ok == true and .data.objective != null' /tmp/cross-client-rpc.json >/dev/null || fail "RPC client failed"
pass "RPC client workflow plan"

# Client 3: Python SDK
python - "$ROOT" <<'PY'
import importlib.util
import json
import pathlib
import sys

root = pathlib.Path(sys.argv[1])
sdk = root / "ai-stack/mcp-servers/hybrid-coordinator/harness_sdk.py"
spec = importlib.util.spec_from_file_location("harness_sdk_mod", sdk)
mod = importlib.util.module_from_spec(spec)
spec.loader.exec_module(mod)  # type: ignore[attr-defined]
client = mod.HarnessClient(base_url="http://127.0.0.1:8003")
plan = client.plan("python sdk cross client smoke")
assert isinstance(plan.get("phases"), list) and len(plan["phases"]) >= 5
print(json.dumps({"ok": True}))
PY
pass "Python SDK workflow plan"

if curl -fsS "${SWB_URL}/v1/models" >/dev/null 2>&1; then
  pass "switchboard reachable for client matrix"
else
  warn "switchboard unavailable; client matrix limited to hybrid APIs"
fi
