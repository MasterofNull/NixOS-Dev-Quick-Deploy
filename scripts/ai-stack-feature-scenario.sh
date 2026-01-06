#!/usr/bin/env bash
# End-to-end feature scenario runner for the AI stack.
# Runs a test scenario, records results, and stores them in AIDB.

set -euo pipefail

PROJECT_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
LOG_DIR="${LOG_DIR:-$HOME/.cache/nixos-quick-deploy/logs}"
RUN_ID="$(date +%Y%m%d_%H%M%S)"
RESULT_PATH="${LOG_DIR}/ai-stack-feature-scenario-${RUN_ID}.json"
RESULTS_JSONL="$(mktemp)"

AIDB_URL="${AIDB_URL:-http://localhost:8091}"
HYBRID_URL="${HYBRID_URL:-http://localhost:8092}"
QDRANT_URL="${QDRANT_URL:-http://localhost:6333}"
LLAMA_URL="${LLAMA_URL:-http://localhost:8080}"
OPEN_WEBUI_URL=""

mkdir -p "$LOG_DIR" >/dev/null 2>&1 || true

require_cmd() {
    if ! command -v "$1" >/dev/null 2>&1; then
        echo "✗ Missing required command: $1" >&2
        exit 1
    fi
}

request() {
    local name="$1"
    local method="$2"
    local url="$3"
    local data="${4:-}"
    local timeout="${5:-8}"
    local tmp_body
    tmp_body="$(mktemp)"

    local http_code
    set +e
    if [[ "$method" == "GET" ]]; then
        http_code=$(curl -sS --max-time "$timeout" -o "$tmp_body" -w "%{http_code}" "$url")
    else
        http_code=$(curl -sS --max-time "$timeout" -o "$tmp_body" -w "%{http_code}" \
            -H "Content-Type: application/json" \
            -d "$data" \
            "$url")
    fi
    local curl_rc=$?
    set -e

    python3 - "$name" "$method" "$url" "$http_code" "$curl_rc" "$tmp_body" >> "$RESULTS_JSONL" <<'PY'
import json
import sys
from pathlib import Path

name, method, url, status, curl_rc, body_path = sys.argv[1:]
body = ""
try:
    body = Path(body_path).read_text(encoding="utf-8", errors="replace")
except Exception:
    body = ""

entry = {
    "name": name,
    "method": method,
    "url": url,
    "status": int(status) if status.isdigit() else status,
    "curl_rc": int(curl_rc),
    "body": body,
}
print(json.dumps(entry))
PY

    rm -f "$tmp_body"
}

require_cmd curl
require_cmd python3

echo "ℹ Running AI stack feature scenario (${RUN_ID})..."

# Detect Open WebUI port
if curl -sf --max-time 3 http://localhost:3001 >/dev/null 2>&1; then
    OPEN_WEBUI_URL="http://localhost:3001"
elif curl -sf --max-time 3 http://localhost:3000 >/dev/null 2>&1; then
    OPEN_WEBUI_URL="http://localhost:3000"
fi

request "aidb.health" "GET" "${AIDB_URL}/health"
request "aidb.discovery.info" "GET" "${AIDB_URL}/discovery/info"
request "aidb.discovery.quickstart" "GET" "${AIDB_URL}/discovery/quickstart"
python3 - "$AIDB_URL" "$RESULTS_JSONL" <<'PY'
import json
import sys
import urllib.request

base = sys.argv[1]
results_path = sys.argv[2]

def record(entry):
    with open(results_path, "a", encoding="utf-8") as handle:
        handle.write(json.dumps(entry) + "\n")

def post_json(url, payload, timeout=90):
    data = json.dumps(payload).encode()
    req = urllib.request.Request(url, data=data, headers={"Content-Type": "application/json"})
    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            body = resp.read().decode()
            return resp.status, body, 0
    except Exception as exc:
        status = getattr(getattr(exc, "code", None), "__int__", lambda: 0)()
        body = getattr(exc, "read", lambda: b"")().decode() if hasattr(exc, "read") else str(exc)
        return status or 0, body, 1

embed_status, embed_body, embed_err = post_json(
    f"{base}/vector/embed",
    {"texts": ["feature scenario: verify embedding pipeline"]},
)
record({
    "name": "aidb.embed",
    "method": "POST",
    "url": f"{base}/vector/embed",
    "status": embed_status,
    "curl_rc": embed_err,
    "body": embed_body,
})

if embed_status == 200:
    try:
        embedding = json.loads(embed_body)["embeddings"][0]
    except Exception as exc:
        record({
            "name": "aidb.vector.search",
            "method": "POST",
            "url": f"{base}/vector/search",
            "status": 0,
            "curl_rc": 1,
            "body": f"Failed to parse embedding: {exc}",
        })
    else:
        search_status, search_body, search_err = post_json(
            f"{base}/vector/search",
            {"embedding": embedding, "limit": 3, "project": "NixOS-Dev-Quick-Deploy"},
        )
        record({
            "name": "aidb.vector.search",
            "method": "POST",
            "url": f"{base}/vector/search",
            "status": search_status,
            "curl_rc": search_err,
            "body": search_body,
        })
else:
    record({
        "name": "aidb.vector.search",
        "method": "POST",
        "url": f"{base}/vector/search",
        "status": 0,
        "curl_rc": 1,
        "body": "Skipping search because embed failed",
    })
PY

request "hybrid.health" "GET" "${HYBRID_URL}/health"
request "hybrid.stats" "GET" "${HYBRID_URL}/stats"
request "hybrid.augment" "POST" "${HYBRID_URL}/augment_query" '{"query":"feature scenario: ensure hybrid context pipeline uses local knowledge","agent_type":"local"}'

request "qdrant.health" "GET" "${QDRANT_URL}/healthz"
request "qdrant.collections" "GET" "${QDRANT_URL}/collections"

request "llama.health" "GET" "${LLAMA_URL}/health"
request "llama.models" "GET" "${LLAMA_URL}/v1/models"

if [[ -n "$OPEN_WEBUI_URL" ]]; then
    request "open_webui.home" "GET" "${OPEN_WEBUI_URL}/"
fi

# Build result payload
python3 - "$RESULT_PATH" "$RESULTS_JSONL" "$RUN_ID" <<'PY'
import json
import sys
from datetime import datetime, timezone
from pathlib import Path

result_path, jsonl_path, run_id = sys.argv[1:]
entries = []
for line in Path(jsonl_path).read_text(encoding="utf-8").splitlines():
    try:
        entries.append(json.loads(line))
    except json.JSONDecodeError:
        continue

summary = {
    "total_checks": len(entries),
    "success": sum(1 for e in entries if e.get("status") in (200, 201)),
    "errors": sum(1 for e in entries if e.get("status") not in (200, 201)),
}

payload = {
    "run_id": run_id,
    "timestamp": datetime.now(timezone.utc).isoformat(),
    "summary": summary,
    "checks": entries,
}

Path(result_path).write_text(json.dumps(payload, indent=2), encoding="utf-8")
PY

# Store results in AIDB (best-effort)
if curl -sf --max-time 3 "${AIDB_URL}/health" >/dev/null 2>&1; then
    doc_title="AI Stack Feature Scenario ${RUN_ID}"
    doc_path="system-tests/ai-stack-feature-scenario-${RUN_ID}.json"
    doc_content="$(cat "$RESULT_PATH")"
    DOC_TITLE="$doc_title"
    DOC_PATH="$doc_path"
    DOC_CONTENT="$doc_content"
    export DOC_TITLE DOC_PATH DOC_CONTENT
    doc_payload="$(python3 - <<PY
import json
import os

payload = {
    "project": "NixOS-Dev-Quick-Deploy",
    "relative_path": os.environ["DOC_PATH"],
    "title": os.environ["DOC_TITLE"],
    "content_type": "application/json",
    "content": os.environ["DOC_CONTENT"],
}
print(json.dumps(payload))
PY
)"
    if [[ -n "${AIDB_API_KEY:-}" ]]; then
        curl -sf --max-time 8 \
            -H "Content-Type: application/json" \
            -H "X-API-Key: ${AIDB_API_KEY}" \
            -d "$doc_payload" \
            "${AIDB_URL}/documents" >/dev/null 2>&1 || true
    else
        curl -sf --max-time 8 \
            -H "Content-Type: application/json" \
            -d "$doc_payload" \
            "${AIDB_URL}/documents" >/dev/null 2>&1 || true
    fi
fi

rm -f "$RESULTS_JSONL"

echo "✓ Feature scenario complete"
echo "✓ Results stored at: $RESULT_PATH"
