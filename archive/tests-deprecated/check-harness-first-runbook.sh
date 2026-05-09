#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
POLICY_FILE="${ROOT_DIR}/config/harness-first-policy.json"
SCHEMA_FILE="${ROOT_DIR}/config/schemas/harness-first/policy.schema.json"

fail() {
  echo "FAIL: $*" >&2
  exit 1
}

[[ -f "${POLICY_FILE}" ]] || fail "missing policy file: ${POLICY_FILE}"
[[ -f "${SCHEMA_FILE}" ]] || fail "missing policy schema: ${SCHEMA_FILE}"

command -v python3 >/dev/null 2>&1 || fail "python3 is required"

mapfile -t policy_data < <(python3 - "${POLICY_FILE}" <<'PY'
import json
import sys
from pathlib import Path

path = Path(sys.argv[1])
try:
    policy = json.loads(path.read_text(encoding="utf-8"))
except Exception as exc:
    print(f"ERROR: unable to parse policy JSON: {exc}", file=sys.stderr)
    raise SystemExit(1)

required = {
    "version": int,
    "runbook": str,
    "evidence_template": str,
    "required_sections": list,
    "required_commands": list,
    "required_evidence_sections": list,
}
for key, expected in required.items():
    if key not in policy:
        print(f"ERROR: missing key: {key}", file=sys.stderr)
        raise SystemExit(1)
    if not isinstance(policy[key], expected):
        print(f"ERROR: key {key} must be {expected.__name__}", file=sys.stderr)
        raise SystemExit(1)

if policy["version"] < 1:
    print("ERROR: version must be >= 1", file=sys.stderr)
    raise SystemExit(1)

if not policy["required_sections"]:
    print("ERROR: required_sections must not be empty", file=sys.stderr)
    raise SystemExit(1)
if not policy["required_commands"]:
    print("ERROR: required_commands must not be empty", file=sys.stderr)
    raise SystemExit(1)

print(policy["runbook"])
for item in policy["required_sections"]:
    print("SECTION::" + item)
for item in policy["required_commands"]:
    print("COMMAND::" + item)
PY
)

[[ ${#policy_data[@]} -gt 0 ]] || fail "policy read returned no data"
runbook_rel="${policy_data[0]}"
RUNBOOK_FILE="${ROOT_DIR}/${runbook_rel}"
[[ -f "${RUNBOOK_FILE}" ]] || fail "missing runbook file: ${runbook_rel}"

sections=()
commands=()
for line in "${policy_data[@]:1}"; do
  case "${line}" in
    SECTION::*) sections+=("${line#SECTION::}") ;;
    COMMAND::*) commands+=("${line#COMMAND::}") ;;
  esac
done

for section in "${sections[@]}"; do
  grep -Fq "${section}" "${RUNBOOK_FILE}" || fail "runbook missing required section: ${section}"
done

for cmd in "${commands[@]}"; do
  grep -Fq "${cmd}" "${RUNBOOK_FILE}" || fail "runbook missing required command marker: ${cmd}"
done

echo "PASS: harness-first runbook contract validated"
