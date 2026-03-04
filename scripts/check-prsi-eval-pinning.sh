#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="${ROOT:-$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)}"
POLICY_FILE="${ROOT_DIR}/config/prsi/eval-pinning-policy.json"
OUT="${PRSI_EVAL_PINS_OUT:-${ROOT_DIR}/data/prsi-artifacts/eval-pins-latest.json}"

mkdir -p "$(dirname "${OUT}")"

python3 - "$ROOT_DIR" "$POLICY_FILE" "$OUT" <<'PY'
import hashlib
import json
import sys
from pathlib import Path

root = Path(sys.argv[1])
policy_path = Path(sys.argv[2])
out_path = Path(sys.argv[3])

policy = json.loads(policy_path.read_text(encoding="utf-8"))
required_files = policy.get("required_files", [])
required_pins = policy.get("required_pins", [])
if not isinstance(required_files, list) or not isinstance(required_pins, list):
    raise SystemExit("ERROR: invalid pinning policy schema")

pin_map = {
    "ai-stack/prompts/registry.yaml": "prompt_registry_sha256",
    "config/runtime-prsi-policy.json": "runtime_prsi_policy_sha256",
    "data/harness-golden-evals.json": "golden_eval_sha256",
    "data/harness-gap-eval-pack.json": "gap_eval_pack_sha256",
    "data/harness-holdout-evals.json": "holdout_eval_sha256",
}

pins = {}
for rel in required_files:
    path = root / rel
    if not path.exists():
        raise SystemExit(f"ERROR: missing required file for pinning: {rel}")
    key = pin_map.get(rel)
    if key:
        pins[key] = hashlib.sha256(path.read_bytes()).hexdigest()

missing = [k for k in required_pins if k not in pins]
if missing:
    raise SystemExit(f"ERROR: missing required computed pins: {missing}")

dt = __import__("datetime")
out = {
    "generated_at": dt.datetime.now(dt.timezone.utc).isoformat(),
    "pins": pins,
}
out_path.write_text(json.dumps(out, indent=2) + "\n", encoding="utf-8")
print(f"PASS: PRSI eval pinning validated ({out_path})")
PY
