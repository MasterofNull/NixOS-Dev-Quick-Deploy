#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
FIXTURE_DIR="${ROOT_DIR}/tests/fixtures"

tmp_phase2="$(mktemp)"
tmp_phase3="$(mktemp)"
tmp_plan="$(mktemp)"
trap 'rm -f "${tmp_phase2}" "${tmp_phase3}" "${tmp_plan}"' EXIT

AQ_QA_FIXTURE_LLAMA_DIAG="${FIXTURE_DIR}/runtime-diagnose/llama-unhealthy.json" \
  "${ROOT_DIR}/scripts/ai/aq-qa" 2 --json > "${tmp_phase2}" || true

AQ_QA_FIXTURE_APPARMOR_DIAG="${FIXTURE_DIR}/runtime-diagnose/apparmor-healthy.json" \
  "${ROOT_DIR}/scripts/ai/aq-qa" 3 --json > "${tmp_phase3}"

python3 "${ROOT_DIR}/scripts/ai/aq-runtime-plan" \
  --qa-fixture "${FIXTURE_DIR}/runtime-plan/qa-unhealthy.json" \
  --diagnosis-fixture "${FIXTURE_DIR}/runtime-plan/diagnoses-unhealthy.json" \
  > "${tmp_plan}"

python3 - "${tmp_phase2}" "${tmp_phase3}" "${tmp_plan}" <<'PY'
import json
import sys
from pathlib import Path

phase2 = json.loads(Path(sys.argv[1]).read_text(encoding="utf-8"))
phase3 = json.loads(Path(sys.argv[2]).read_text(encoding="utf-8"))
plan = json.loads(Path(sys.argv[3]).read_text(encoding="utf-8"))

if phase2["failed"] < 1:
    print("ERROR: phase 2 fixture did not produce a failure", file=sys.stderr)
    raise SystemExit(1)

phase2_desc = "\n".join(test["description"] for test in phase2["tests"])
if "classification=path_scoped_confinement_likely" not in phase2_desc:
    print("ERROR: phase 2 did not surface the expected llama classification", file=sys.stderr)
    raise SystemExit(1)

if phase3["failed"] != 0:
    print("ERROR: phase 3 healthy fixture should pass", file=sys.stderr)
    raise SystemExit(1)

phase3_desc = "\n".join(test["description"] for test in phase3["tests"])
if "apparmor/confinement loop passes (runtime_probe_active)" not in phase3_desc:
    print("ERROR: phase 3 did not surface the expected healthy apparmor classification", file=sys.stderr)
    raise SystemExit(1)

actions = plan["next_actions"]
if len(actions) < 2 or "Focus on preset `llama-cpp` at the `confinement` layer." not in actions[1]["summary"]:
    print("ERROR: planner handoff did not prioritize the runtime diagnosis result", file=sys.stderr)
    raise SystemExit(1)

print("PASS: aq-qa runtime phases and planner handoff validated")
PY
