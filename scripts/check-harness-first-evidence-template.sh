#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
POLICY_FILE="${ROOT_DIR}/config/harness-first-policy.json"

fail() {
  echo "FAIL: $*" >&2
  exit 1
}

[[ -f "${POLICY_FILE}" ]] || fail "missing policy file: ${POLICY_FILE}"
command -v python3 >/dev/null 2>&1 || fail "python3 is required"

mapfile -t policy_data < <(python3 - "${POLICY_FILE}" <<'PY'
import json
import sys
from pathlib import Path

policy = json.loads(Path(sys.argv[1]).read_text(encoding="utf-8"))
print(policy["evidence_template"])
for item in policy["required_evidence_sections"]:
    print("SECTION::" + item)
PY
)

[[ ${#policy_data[@]} -gt 0 ]] || fail "policy read returned no data"
template_rel="${policy_data[0]}"
TEMPLATE_FILE="${ROOT_DIR}/${template_rel}"
[[ -f "${TEMPLATE_FILE}" ]] || fail "missing evidence template: ${template_rel}"

for line in "${policy_data[@]:1}"; do
  section="${line#SECTION::}"
  grep -Fq "${section}" "${TEMPLATE_FILE}" || fail "evidence template missing section: ${section}"
done

required_markers=(
  "Task ID: HF-"
  "scripts/aq-hints"
  "scripts/harness-rpc.js run-start"
  "scripts/aq-qa 0 --json"
  "scripts/aq-qa 1 --json"
)

for marker in "${required_markers[@]}"; do
  grep -Fq "${marker}" "${TEMPLATE_FILE}" || fail "evidence template missing marker: ${marker}"
done

echo "PASS: harness-first evidence template contract validated"
