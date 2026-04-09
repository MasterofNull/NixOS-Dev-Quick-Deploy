#!/usr/bin/env bash
set -euo pipefail

# Regression-test Continue-local request trimming and switchboard response limits.

SWB_URL="${SWB_URL:-http://127.0.0.1:8085}"
TMP_DIR="$(mktemp -d /tmp/switchboard-continue-context-XXXXXX)"
trap 'rm -rf "$TMP_DIR"' EXIT

need_cmd() {
  command -v "$1" >/dev/null 2>&1 || {
    printf '[FAIL] missing command: %s\n' "$1" >&2
    exit 1
  }
}

need_cmd curl
need_cmd jq
need_cmd python3
need_cmd rg

payload_json="${TMP_DIR}/payload.json"
python3 - <<'PY' >"${payload_json}"
import json

payload = {
    "model": "continue-local",
    "messages": [
        {"role": "system", "content": "You are a concise trimming regression test."},
        {"role": "user", "content": "A" * 24000},
    ],
    "max_tokens": 32,
}
print(json.dumps(payload))
PY

headers_file="${TMP_DIR}/headers.txt"
body_file="${TMP_DIR}/body.json"
http_code="$(
  curl -sS -D "${headers_file}" -o "${body_file}" \
    --connect-timeout 5 \
    --max-time 45 \
    -H 'Content-Type: application/json' \
    -H 'X-AI-Profile: continue-local' \
    "${SWB_URL}/v1/chat/completions" \
    --data @"${payload_json}" \
    -w '%{http_code}'
)"

tr -d '\r' <"${headers_file}" >"${headers_file}.norm"

if [[ "${http_code}" != "200" ]]; then
  printf '[FAIL] expected 200 from switchboard, got %s\n' "${http_code}" >&2
  cat "${body_file}" >&2
  exit 1
fi

rg -q '^x-ai-input-trimmed: 1$' "${headers_file}.norm" || {
  printf '[FAIL] expected x-ai-input-trimmed header\n' >&2
  cat "${headers_file}.norm" >&2
  exit 1
}

jq -e '.choices[0].message.content? != null' "${body_file}" >/dev/null || {
  printf '[FAIL] expected a normal chat completion payload\n' >&2
  cat "${body_file}" >&2
  exit 1
}

printf 'PASS: continue-local oversized payload is trimmed and answered successfully\n'
