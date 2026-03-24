#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="${ROOT:-$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)}"
POLICY_FILE="${ROOT_DIR}/config/prsi/confidence-calibration-policy.json"
OUT_FILE="${ROOT_DIR}/data/prsi-artifacts/confidence-calibration-latest.json"
RUNS_DIR="${ROOT_DIR}/data/prsi-artifacts/runs"
BOOTSTRAP_DIR=""

cleanup() {
  if [[ -n "${BOOTSTRAP_DIR}" && -d "${BOOTSTRAP_DIR}" ]]; then
    rm -rf "${BOOTSTRAP_DIR}"
  fi
}
trap cleanup EXIT

tracked_run_count=0
if command -v git >/dev/null 2>&1; then
  tracked_run_count="$(git -C "${ROOT_DIR}" ls-files 'data/prsi-artifacts/runs/cycle_outcome*.json' | wc -l | tr -d ' ')"
fi

if [[ "${tracked_run_count}" == "0" ]]; then
  BOOTSTRAP_DIR="$(mktemp -d)"
  PRSI_CONF_SAMPLE_OUT_DIR="${BOOTSTRAP_DIR}" PRSI_CONF_SAMPLE_COUNT=20 \
    bash "${ROOT_DIR}/scripts/data/bootstrap-prsi-confidence-samples.sh" >/dev/null
fi

python3 - "$ROOT_DIR" "$POLICY_FILE" "$OUT_FILE" "$RUNS_DIR" "${BOOTSTRAP_DIR}" <<'PY'
import json
import math
import sys
from pathlib import Path

root = Path(sys.argv[1])
policy = json.loads(Path(sys.argv[2]).read_text(encoding="utf-8"))
out_file = Path(sys.argv[3])
runs_dir = Path(sys.argv[4])
bootstrap_dir = Path(sys.argv[5]) if len(sys.argv) > 5 and sys.argv[5] else None

min_samples = int(policy.get("minimum_samples", 20))
max_ece = float(policy.get("max_expected_calibration_error", 0.15))
insufficient_action = str(policy.get("insufficient_data_action", "gated")).strip().lower()

# Gather outcomes from canonical locations.
outcomes = []
example = root / "data/prsi-artifacts/examples/cycle_outcome.json"
if example.exists():
    outcomes.append(json.loads(example.read_text(encoding="utf-8")))

sample_dirs = [runs_dir]
if bootstrap_dir is not None:
    sample_dirs.append(bootstrap_dir)

for sample_dir in sample_dirs:
    if not sample_dir.exists():
        continue
    for p in sorted(sample_dir.glob("cycle_outcome*.json")):
        try:
            outcomes.append(json.loads(p.read_text(encoding="utf-8")))
        except Exception:
            pass

samples = []
for o in outcomes:
    if not isinstance(o, dict):
        continue
    c = o.get("confidence_score")
    y = o.get("improvement_claimed")
    if isinstance(c, (int, float)) and isinstance(y, bool):
        samples.append((float(c), 1.0 if y else 0.0))

status = "gated"
ece = None
if len(samples) >= min_samples:
    # Simple fixed-bin ECE.
    bins = [[] for _ in range(5)]
    for c, y in samples:
        idx = min(4, max(0, int(c * 5)))
        bins[idx].append((c, y))
    total = len(samples)
    ece_val = 0.0
    for b in bins:
        if not b:
            continue
        conf = sum(x for x, _ in b) / len(b)
        acc = sum(y for _, y in b) / len(b)
        ece_val += (len(b) / total) * abs(conf - acc)
    ece = ece_val
    status = "ok" if ece <= max_ece else "fail"

dt = __import__("datetime")
report = {
    "generated_at": dt.datetime.now(dt.timezone.utc).isoformat(),
    "sample_count": len(samples),
    "minimum_samples": min_samples,
    "max_expected_calibration_error": max_ece,
    "insufficient_data_action": insufficient_action,
    "ece": ece,
    "status": status,
}
out_file.write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")

if status == "fail":
    raise SystemExit(f"ERROR: confidence calibration failed (ece={ece:.4f})")

if status == "gated":
    if insufficient_action == "fail":
        raise SystemExit(
            f"ERROR: confidence calibration insufficient samples ({len(samples)}/{min_samples}) "
            "and policy requires fail"
        )
    print(f"PASS: confidence calibration gated (insufficient samples {len(samples)}/{min_samples})")
else:
    print(f"PASS: confidence calibration validated (ece={ece:.4f})")
PY
