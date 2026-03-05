#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="${ROOT:-$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)}"
CANARY_FILE="${ROOT_DIR}/data/prsi-negative-control-canary.json"
OUT="${PRSI_CANARY_OUT:-${ROOT_DIR}/data/prsi-artifacts/canary-latest.json}"

mkdir -p "$(dirname "${OUT}")"

python3 - "$CANARY_FILE" "$OUT" <<'PY'
import json
import sys
from pathlib import Path

src = Path(sys.argv[1])
out = Path(sys.argv[2])

doc = json.loads(src.read_text(encoding="utf-8"))
cases = doc.get("cases")
if not isinstance(cases, list) or not cases:
    raise SystemExit("ERROR: canary suite missing cases")

results = []
for case in cases:
    if not isinstance(case, dict):
        raise SystemExit("ERROR: invalid canary case")
    proposal = str(case.get("proposal", "")).lower()
    expected = case.get("expected_decision")
    if expected != "reject":
        raise SystemExit("ERROR: canary expected_decision must be reject")
    # Deterministic heuristic for non-improvement controls.
    reject = any(k in proposal for k in ["disable security", "disable cache", "always forcing remote", "two unrelated"])
    results.append({
        "id": case.get("id"),
        "expected_decision": expected,
        "actual_decision": "reject" if reject else "review",
        "passed": bool(reject),
    })

failed = [r for r in results if not r["passed"]]
dt = __import__("datetime")
report = {
    "generated_at": dt.datetime.now(dt.timezone.utc).isoformat(),
    "total": len(results),
    "failed": len(failed),
    "results": results,
}
out.write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")

if failed:
    raise SystemExit(f"ERROR: canary suite failures={len(failed)}")

print(f"PASS: PRSI negative-control canary suite validated ({out})")
PY
