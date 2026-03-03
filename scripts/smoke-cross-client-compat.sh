#!/usr/bin/env bash
set -euo pipefail

ROOT="${ROOT:-/home/hyperd/Documents/NixOS-Dev-Quick-Deploy}"
HYB_URL="${HYB_URL:-http://127.0.0.1:8003}"
SWB_URL="${SWB_URL:-http://127.0.0.1:8085}"
HYBRID_API_KEY_FILE="${HYBRID_API_KEY_FILE:-/run/secrets/hybrid_api_key}"
HYBRID_API_KEY="${HYBRID_API_KEY:-}"

if [[ -z "$HYBRID_API_KEY" && -r "$HYBRID_API_KEY_FILE" ]]; then
  HYBRID_API_KEY="$(tr -d '[:space:]' < "$HYBRID_API_KEY_FILE")"
fi
if [[ -z "$HYBRID_API_KEY" ]]; then
  for candidate in /run/secrets/hybrid_coordinator_api_key /run/secrets/hybrid_api_key; do
    if [[ -r "$candidate" ]]; then
      HYBRID_API_KEY="$(tr -d '[:space:]' < "$candidate")"
      break
    fi
  done
fi

pass() { echo "[PASS] $*"; }
warn() { echo "[WARN] $*" >&2; }
fail() { echo "[FAIL] $*" >&2; exit 1; }

curl_args=()
if [[ -n "$HYBRID_API_KEY" ]]; then
  curl_args+=(-H "X-API-Key: ${HYBRID_API_KEY}")
fi

if ! curl -fsS "${HYB_URL}/health" >/dev/null 2>&1; then
  warn "hybrid coordinator unavailable; cross-client smoke skipped"
  exit 0
fi

# Client 1: raw HTTP
http_code="$(curl -sS -o /tmp/cross-client-http.json -w "%{http_code}" "${curl_args[@]}" "${HYB_URL}/workflow/plan?q=cross-client-smoke" || true)"
if [[ "$http_code" == "401" && -z "$HYBRID_API_KEY" ]]; then
  warn "hybrid API key required but unavailable; cross-client smoke skipped"
  exit 0
fi
[[ "$http_code" == "200" ]] || fail "HTTP client failed (code=${http_code})"
jq -e '.phases | length >= 5' /tmp/cross-client-http.json >/dev/null || fail "HTTP client payload invalid"
pass "HTTP client workflow plan"

# Client 2: JS RPC wrapper
HYBRID_API_KEY="${HYBRID_API_KEY}" node "${ROOT}/scripts/harness-rpc.js" plan --query "cross client rpc smoke" >/tmp/cross-client-rpc.json
jq -e '.ok == true and .data.objective != null' /tmp/cross-client-rpc.json >/dev/null || fail "RPC client failed"
pass "RPC client workflow plan"

# Client 3: Python SDK
python - "$ROOT" "$HYBRID_API_KEY" <<'PY'
import importlib.util
import json
import os
import pathlib
import sys

root = pathlib.Path(sys.argv[1])
provided_key = (sys.argv[2] or "").strip()
sdk = root / "ai-stack/mcp-servers/hybrid-coordinator/harness_sdk.py"
spec = importlib.util.spec_from_file_location("harness_sdk_mod", sdk)
mod = importlib.util.module_from_spec(spec)
sys.modules["harness_sdk_mod"] = mod
spec.loader.exec_module(mod)  # type: ignore[attr-defined]
client = mod.HarnessClient(base_url="http://127.0.0.1:8003")
key = provided_key or (os.getenv("HYBRID_API_KEY") or "").strip()
if not key:
    key_path = pathlib.Path("/run/secrets/hybrid_api_key")
    if key_path.exists():
        key = key_path.read_text().strip()
if key:
    client.api_key = key
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
