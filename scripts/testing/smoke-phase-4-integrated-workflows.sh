#!/usr/bin/env bash
# smoke-phase-4-integrated-workflows.sh
# Consolidated Phase 4 acceptance:
# - 4.1 deployment -> monitoring -> alerting
# - 4.2 query -> agent -> storage -> learning
# - 4.3 security -> audit -> compliance
#
# Emits a machine-readable JSON summary so Phase 4 acceptance can be checked
# from one artifact instead of three independent smoke outputs.

set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
REPORT_PATH="${PHASE4_ACCEPTANCE_REPORT_PATH:-${ROOT_DIR}/.reports/phase-4-acceptance-report.json}"
TMP_DIR="$(mktemp -d /tmp/smoke-phase4-integrated-XXXXXX)"
trap 'rm -rf "${TMP_DIR}"' EXIT

pass() {
  printf '[PASS] %s\n' "$1"
}

fail() {
  printf '[FAIL] %s\n' "$1" >&2
  exit 1
}

need_cmd() {
  command -v "$1" >/dev/null 2>&1 || fail "missing command: $1"
}

need_cmd jq
need_cmd python3

mkdir -p "$(dirname "${REPORT_PATH}")"

run_smoke() {
  local key="$1"
  local label="$2"
  local script_path="$3"
  local stdout_path="${TMP_DIR}/${key}.stdout"
  local stderr_path="${TMP_DIR}/${key}.stderr"
  local status="passed"
  local started_at ended_at

  started_at="$(date -Is)"
  if bash "${script_path}" >"${stdout_path}" 2>"${stderr_path}"; then
    status="passed"
  else
    status="failed"
  fi
  ended_at="$(date -Is)"

  python3 - "$REPORT_PATH" "$key" "$label" "$script_path" "$status" "$started_at" "$ended_at" "$stdout_path" "$stderr_path" <<'PY'
import json
import sys
from pathlib import Path

report_path = Path(sys.argv[1])
key = sys.argv[2]
label = sys.argv[3]
script_path = sys.argv[4]
status = sys.argv[5]
started_at = sys.argv[6]
ended_at = sys.argv[7]
stdout_path = Path(sys.argv[8])
stderr_path = Path(sys.argv[9])

if report_path.exists():
    report = json.loads(report_path.read_text(encoding="utf-8"))
else:
    report = {"status": "in_progress", "generated_at": "", "phase": "4", "flows": {}}

report["generated_at"] = ended_at
flows = report.setdefault("flows", {})
flows[key] = {
    "label": label,
    "script": script_path,
    "status": status,
    "started_at": started_at,
    "ended_at": ended_at,
    "stdout": stdout_path.read_text(encoding="utf-8"),
    "stderr": stderr_path.read_text(encoding="utf-8"),
}

flow_states = [flow.get("status", "unknown") for flow in flows.values()]
report["status"] = "passed" if flow_states and all(state == "passed" for state in flow_states) else "failed"
report_path.write_text(json.dumps(report, indent=2, sort_keys=True) + "\n", encoding="utf-8")
PY

  if [[ "${status}" == "passed" ]]; then
    pass "${label}"
  else
    printf '%s\n' "--- ${label} stdout ---" >&2
    cat "${stdout_path}" >&2 || true
    printf '%s\n' "--- ${label} stderr ---" >&2
    cat "${stderr_path}" >&2 || true
    fail "${label}"
  fi
}

cat > "${REPORT_PATH}" <<EOF
{
  "generated_at": "$(date -Is)",
  "phase": "4",
  "status": "in_progress",
  "flows": {}
}
EOF

run_smoke \
  "deployment_monitoring_alerting" \
  "Phase 4.1 deployment -> monitoring -> alerting" \
  "${ROOT_DIR}/scripts/testing/smoke-deployment-monitoring-alerting.sh"
run_smoke \
  "query_agent_storage_learning" \
  "Phase 4.2 query -> agent -> storage -> learning" \
  "${ROOT_DIR}/scripts/testing/smoke-query-agent-storage-learning.sh"
run_smoke \
  "security_audit_compliance" \
  "Phase 4.3 security -> audit -> compliance" \
  "${ROOT_DIR}/scripts/testing/smoke-security-audit-compliance.sh"

jq -e '.status == "passed"' "${REPORT_PATH}" >/dev/null \
  || fail "phase 4 consolidated report did not mark success"

pass "phase 4 consolidated acceptance report written to ${REPORT_PATH}"
printf '\nPhase 4 integrated workflow acceptance passed.\n'
