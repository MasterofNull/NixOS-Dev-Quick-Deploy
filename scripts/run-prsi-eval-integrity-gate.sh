#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="${ROOT:-$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)}"
GOLDEN="${ROOT_DIR}/data/harness-golden-evals.json"
GAP_PACK="${ROOT_DIR}/data/harness-gap-eval-pack.json"
HOLDOUT="${ROOT_DIR}/data/harness-holdout-evals.json"
OUT="${PRSI_EVAL_INTEGRITY_OUT:-${ROOT_DIR}/data/prsi-artifacts/eval-integrity-latest.json}"

mkdir -p "$(dirname "${OUT}")"

python3 - "$GOLDEN" "$GAP_PACK" "$HOLDOUT" "$OUT" <<'PY'
import hashlib
import json
import sys
from pathlib import Path

p_golden = Path(sys.argv[1])
p_gap = Path(sys.argv[2])
p_hold = Path(sys.argv[3])
p_out = Path(sys.argv[4])

for p in [p_golden, p_gap, p_hold]:
    if not p.exists():
        raise SystemExit(f"ERROR: missing eval file: {p}")

j_g = json.loads(p_golden.read_text(encoding="utf-8"))
j_p = json.loads(p_gap.read_text(encoding="utf-8"))
j_h = json.loads(p_hold.read_text(encoding="utf-8"))

def queries(doc):
    cases = doc.get("cases") if isinstance(doc, dict) else None
    if not isinstance(cases, list):
        return set()
    out = set()
    for c in cases:
        if isinstance(c, dict) and isinstance(c.get("query"), str):
            out.add(c["query"].strip().lower())
    return out

golden_q = queries(j_g)
gap_q = queries(j_p)
hold_q = queries(j_h)

if not hold_q:
    raise SystemExit("ERROR: holdout eval pack has no queries")

opt_q = golden_q | gap_q
overlap = sorted(hold_q & opt_q)
contam_ratio = (len(overlap) / len(hold_q)) if hold_q else 1.0

risk_level = "low"
if contam_ratio > 0:
    risk_level = "high" if contam_ratio >= 0.20 else "medium"

dt = __import__("datetime")
summary = {
    "generated_at": dt.datetime.now(dt.timezone.utc).isoformat(),
    "holdout_queries": len(hold_q),
    "optimization_queries": len(opt_q),
    "overlap_count": len(overlap),
    "overlap_queries": overlap,
    "contamination_ratio": round(contam_ratio, 4),
    "contamination_risk": risk_level,
    "pins": {
        "golden_eval_sha256": hashlib.sha256(p_golden.read_bytes()).hexdigest(),
        "gap_eval_pack_sha256": hashlib.sha256(p_gap.read_bytes()).hexdigest(),
        "holdout_eval_sha256": hashlib.sha256(p_hold.read_bytes()).hexdigest(),
    }
}

p_out.write_text(json.dumps(summary, indent=2) + "\n", encoding="utf-8")

if overlap:
    raise SystemExit(f"ERROR: holdout contamination detected (overlap={len(overlap)})")

print(f"PASS: PRSI eval integrity validated ({p_out})")
PY
