#!/usr/bin/env bash
# tier0.d/check-payload-audit.sh - report the agent instruction-payload audit under --maintenance.
# Rule 19 gate corollary: payload size and plan-quota exhaustion are measurements of live state, not
# regressions a change introduced, so this REPORTS (WARN lines, exit 0) and never blocks. Other modes skip
# it. The scheduled signal is ai-stack-health-monitor (status file + medium attention alert on HIGH).
# Env: PAYLOAD_AUDIT_BIN overrides the audit script (tests).
set -euo pipefail
MODE="${1:---pre-commit}"
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../../.." && pwd)"
AUDIT="${PAYLOAD_AUDIT_BIN:-$ROOT/scripts/ai/aq-payload-audit}"
tag="[tier0.d/check-payload-audit]"
if [[ "$MODE" != "--maintenance" ]]; then
  echo "$tag SKIP: report-only maintenance signal, runs under --maintenance only (mode $MODE)"
  exit 0
fi
if ! out="$(python3 "$AUDIT" --json --days 2 --repo "$ROOT" 2>&1)"; then
  echo "$tag WARN (--maintenance): audit could not run: $(tail -n 1 <<<"$out")"
  exit 0
fi
python3 - "$out" <<'PY'
import json, sys
tag = "[tier0.d/check-payload-audit]"
try:
    d = json.loads(sys.argv[1])
except json.JSONDecodeError as exc:
    print(f"{tag} WARN (--maintenance): audit output unreadable: {exc}")
    raise SystemExit(0)
s = d["summary"]
for f in d["findings"]:
    print(f"{tag} WARN {f['severity'].upper()} {f['lane']}/{f['check_id']}: {f['measured']} (target {f['threshold']}) {f['evidence_path']}")
print(f"{tag} REPORT (--maintenance): {s['high']} high, {s['medium']} medium, {s['total']} total; report-only, never blocks")
PY
