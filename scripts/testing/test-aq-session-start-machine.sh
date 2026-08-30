#!/usr/bin/env bash
# Regression coverage for aq-session-start's closed machine-output contract.
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
SESSION_START="${SCRIPT_DIR}/../ai/aq-session-start"

output="$("$SESSION_START" --task "x" --machine --no-write)"
python3 -c '
import json
import sys

payload = json.loads(sys.stdin.read())
assert isinstance(payload, dict), "machine output must be a JSON object"
assert payload.get("status") == "closed", "machine output must be closed"
assert payload.get("task") == "x", "machine output must preserve --task"
' <<<"$output"

set +e
unknown_output="$("$SESSION_START" --definitely-unknown 2>&1)"
unknown_status=$?
set -e
if [[ "$unknown_status" -ne 2 || "$unknown_output" != "unknown arg: --definitely-unknown" ]]; then
    printf 'FAIL: unknown flag did not preserve the exit-2 error contract\n' >&2
    exit 1
fi

printf 'PASS: aq-session-start machine output contract\n'
