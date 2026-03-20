#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
ROOT="${ROOT:-$(cd "${SCRIPT_DIR}/../.." && pwd)}"
SDK_DIR="${ROOT}/ai-stack/mcp-servers/hybrid-coordinator"
TMP_DIR="$(mktemp -d /tmp/smoke-harness-sdk-XXXXXX)"
trap 'rm -rf "$TMP_DIR"' EXIT

pass() { printf '[PASS] %s\n' "$*"; }
fail() { printf '[FAIL] %s\n' "$*" >&2; exit 1; }

need_cmd() {
  command -v "$1" >/dev/null 2>&1 || fail "missing command: $1"
}

need_cmd python
need_cmd npm
need_cmd node

python -m py_compile "${SDK_DIR}/harness_sdk.py" || fail "python sdk compile failed"
pass "python sdk compile"

node --check "${SDK_DIR}/harness_sdk.js" || fail "js sdk syntax failed"
pass "js sdk syntax"

python - <<'PY' "${SDK_DIR}/harness_sdk.py" || fail "python sdk A2A surface drift"
from pathlib import Path
import sys
source = Path(sys.argv[1]).read_text(encoding="utf-8")
required = [
    "def a2a_agent_card",
    "def a2a_get_card",
    "def a2a_send_message",
    "def a2a_stream_message",
    "def a2a_get_task",
    "def a2a_list_tasks",
    "def a2a_cancel_task",
]
missing = [item for item in required if item not in source]
if missing:
    raise SystemExit(f"missing python A2A methods: {missing}")
PY
pass "python sdk A2A methods"

python - <<'PY' "${SDK_DIR}/harness_sdk.ts" "${SDK_DIR}/harness_sdk.js" "${SDK_DIR}/harness_sdk.d.ts" || fail "js/ts sdk A2A surface drift"
from pathlib import Path
import sys
required = [
    "a2aAgentCard",
    "a2aGetCard",
    "a2aSendMessage",
    "a2aStreamMessage",
    "a2aGetTask",
    "a2aListTasks",
    "a2aCancelTask",
]
for raw_path in sys.argv[1:]:
    source = Path(raw_path).read_text(encoding="utf-8")
    missing = [item for item in required if item not in source]
    if missing:
        raise SystemExit(f"{raw_path}: missing {missing}")
PY
pass "js/ts sdk A2A methods"

# Python and npm SDK versions must stay in lockstep.
"${ROOT}/scripts/testing/check-harness-sdk-version-parity.sh" >/dev/null || fail "SDK version parity check failed"
pass "sdk version parity"

# Generated SDK API docs drift check
"${ROOT}/scripts/data/generate-harness-sdk-api-docs.sh" --check >/dev/null || fail "generated sdk API docs are out of date"
pass "sdk API docs up-to-date"

# Python package build smoke (sdist + wheel)
(
  cd "${SDK_DIR}"
  python -m build --outdir "${TMP_DIR}/py-dist" >/dev/null
)
ls -1 "${TMP_DIR}/py-dist"/*.whl >/dev/null 2>&1 || fail "wheel not produced"
ls -1 "${TMP_DIR}/py-dist"/*.tar.gz >/dev/null 2>&1 || fail "sdist not produced"
pass "python package build (wheel + sdist)"

# npm packaging smoke
(
  cd "${SDK_DIR}"
  npm pack --dry-run >/dev/null
)
pass "npm pack dry run"

printf '\nSDK packaging smoke checks completed successfully.\n'
