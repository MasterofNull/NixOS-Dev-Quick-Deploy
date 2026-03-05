#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
OUT_DIR="${SECURITY_SUITE_OUT_DIR:-${ROOT_DIR}/artifacts/security-tests}"
OUT_JSON="${OUT_DIR}/latest.json"
OUT_MD="${OUT_DIR}/latest.md"
mkdir -p "${OUT_DIR}"

steps=(
  "scripts/testing/check-api-auth-hardening.sh"
  "scripts/testing/chaos-harness-smoke.sh"
  "scripts/testing/check-prsi-high-risk-approval-rubric.sh"
  "scripts/testing/check-prsi-quarantine-workflow.sh"
  "scripts/testing/check-npm-security-monitor-smoke.sh"
)

declare -a results=()
overall=0
RESULTS_FILE="${OUT_DIR}/results.jsonl"
: > "${RESULTS_FILE}"

for step in "${steps[@]}"; do
  name="$(basename "${step}")"
  log_file="${OUT_DIR}/${name%.sh}.log"
  if "${ROOT_DIR}/${step}" >"${log_file}" 2>&1; then
    printf '{"step":"%s","status":"pass","log":"%s"}\n' "${step}" "${log_file}" >> "${RESULTS_FILE}"
  else
    printf '{"step":"%s","status":"fail","log":"%s"}\n' "${step}" "${log_file}" >> "${RESULTS_FILE}"
    overall=1
  fi
done

python3 - <<'PY' "${OUT_JSON}" "${OUT_MD}" "${overall}" "${RESULTS_FILE}"
import json
import pathlib
import sys
from datetime import datetime, timezone

out_json = pathlib.Path(sys.argv[1])
out_md = pathlib.Path(sys.argv[2])
overall = int(sys.argv[3])
results_file = pathlib.Path(sys.argv[4])
rows = []
if results_file.exists():
    for line in results_file.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line:
            continue
        rows.append(json.loads(line))

payload = {
    "generated_at": datetime.now(tz=timezone.utc).isoformat(),
    "status": "pass" if overall == 0 else "fail",
    "results": rows,
}
out_json.write_text(json.dumps(payload, indent=2), encoding="utf-8")

lines = [
    "# Security Penetration Suite",
    "",
    f"- Generated: {payload['generated_at']}",
    f"- Status: {payload['status']}",
    "",
    "## Steps",
    "",
]
for row in rows:
    lines.append(f"- {row['status'].upper()}: {row['step']} (log: {row['log']})")
out_md.write_text("\n".join(lines) + "\n", encoding="utf-8")
print(str(out_json))
PY

echo "Security suite reports written:"
echo "  ${OUT_JSON}"
echo "  ${OUT_MD}"

exit "${overall}"
