#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
WRAPPER="${ROOT_DIR}/scripts/ai/aq-runtime-act"
FIXTURE_DIR="${ROOT_DIR}/tests/fixtures/runtime-plan"

tmp_wrapper="$(mktemp)"
tmp_list="$(mktemp)"
tmp_action_id="$(mktemp)"
tmp_action_group="$(mktemp)"
tmp_brief="$(mktemp)"
tmp_artifact="$(mktemp)"
trap 'rm -f "${tmp_wrapper}" "${tmp_list}" "${tmp_action_id}" "${tmp_action_group}" "${tmp_brief}" "${tmp_artifact}"' EXIT

python3 "${WRAPPER}" --plan-file "${FIXTURE_DIR}/remediation-safe-plan.json" > "${tmp_wrapper}"
python3 "${WRAPPER}" --plan-file "${FIXTURE_DIR}/remediation-safe-plan.json" --list-actions > "${tmp_list}"
python3 "${WRAPPER}" --plan-file "${FIXTURE_DIR}/remediation-safe-plan.json" --action-id safe_fixture > "${tmp_action_id}"
python3 "${WRAPPER}" --plan-file "${FIXTURE_DIR}/remediation-safe-plan.json" --action-group safe_to_run_now > "${tmp_action_group}"
python3 "${WRAPPER}" --plan-file "${FIXTURE_DIR}/remediation-safe-plan.json" --brief > "${tmp_brief}"
python3 "${WRAPPER}" --plan-file "${FIXTURE_DIR}/remediation-safe-plan.json" --save-artifact "${tmp_artifact}" > /dev/null

python3 - "${tmp_wrapper}" "${tmp_list}" "${tmp_action_id}" "${tmp_action_group}" "${tmp_brief}" "${tmp_artifact}" <<'PY'
import json
import sys
from pathlib import Path

wrapped = json.loads(Path(sys.argv[1]).read_text(encoding="utf-8"))
listing = json.loads(Path(sys.argv[2]).read_text(encoding="utf-8"))
action_id = json.loads(Path(sys.argv[3]).read_text(encoding="utf-8"))
action_group = json.loads(Path(sys.argv[4]).read_text(encoding="utf-8"))
brief = json.loads(Path(sys.argv[5]).read_text(encoding="utf-8"))
artifact = json.loads(Path(sys.argv[6]).read_text(encoding="utf-8"))

if wrapped.get("plan_summary") != {}:
    print("ERROR: wrapper did not preserve the expected empty plan summary from the safe fixture", file=sys.stderr)
    raise SystemExit(1)
if wrapped.get("artifact_meta", {}).get("tool") != "aq-runtime-act":
    print("ERROR: wrapper did not expose the expected artifact metadata tool name", file=sys.stderr)
    raise SystemExit(1)
if wrapped.get("execution_order", {}).get("recommended_group_order") != ["safe_to_run_now"]:
    print("ERROR: wrapper did not surface the plan execution order", file=sys.stderr)
    raise SystemExit(1)
if wrapped.get("context_cards", {}).get("recommended_card_order") != ["repo-baseline"]:
    print("ERROR: wrapper did not surface the plan context-card recommendation", file=sys.stderr)
    raise SystemExit(1)
if wrapped.get("selection_strategy", {}).get("mode") != "prefer_plan_order":
    print("ERROR: wrapper did not expose the expected default selection strategy", file=sys.stderr)
    raise SystemExit(1)
if "result" in brief:
    print("ERROR: brief mode did not reduce the wrapper payload shape", file=sys.stderr)
    raise SystemExit(1)
if brief.get("selected_action_id") != "safe_fixture":
    print("ERROR: brief mode did not preserve the selected action id", file=sys.stderr)
    raise SystemExit(1)
if brief.get("incident_summary", {}).get("headline") != "dry-run: safe_fixture":
    print("ERROR: brief mode did not preserve the compact incident summary", file=sys.stderr)
    raise SystemExit(1)
if wrapped.get("selection_reason", {}).get("category") != "planner_recommended":
    print("ERROR: wrapper did not expose the expected planner-driven selection reason", file=sys.stderr)
    raise SystemExit(1)
if wrapped.get("incident_summary", {}).get("selected_action_id") != "safe_fixture":
    print("ERROR: wrapper did not expose the expected incident summary action id", file=sys.stderr)
    raise SystemExit(1)
result = wrapped.get("result", {})
if result.get("selected_action_id") != "safe_fixture":
    print("ERROR: wrapper did not select the recommended safe fixture action", file=sys.stderr)
    raise SystemExit(1)
if result.get("selected_action_group") != "safe_to_run_now":
    print("ERROR: wrapper did not resolve the expected recommended group", file=sys.stderr)
    raise SystemExit(1)
list_result = listing.get("result", {})
if listing.get("selection_strategy", {}).get("mode") != "list_actions":
    print("ERROR: wrapper did not expose the expected list-actions selection strategy", file=sys.stderr)
    raise SystemExit(1)
if list_result.get("mode") != "list":
    print("ERROR: wrapper did not forward list-actions mode", file=sys.stderr)
    raise SystemExit(1)
if list_result.get("actions", [])[0].get("action_id") != "safe_fixture":
    print("ERROR: wrapper list mode did not expose the expected action listing", file=sys.stderr)
    raise SystemExit(1)
if action_id.get("selection_strategy", {}).get("mode") != "explicit_action_id":
    print("ERROR: wrapper did not expose explicit_action_id strategy", file=sys.stderr)
    raise SystemExit(1)
if action_id.get("selection_reason", {}).get("category") != "wrapper_override":
    print("ERROR: wrapper did not expose explicit action-id selection reason", file=sys.stderr)
    raise SystemExit(1)
if action_id.get("incident_summary", {}).get("selection_mode") != "explicit_action_id":
    print("ERROR: wrapper did not expose the expected incident summary selection mode for action-id override", file=sys.stderr)
    raise SystemExit(1)
if action_group.get("selection_strategy", {}).get("mode") != "explicit_action_group":
    print("ERROR: wrapper did not expose explicit_action_group strategy", file=sys.stderr)
    raise SystemExit(1)
if action_group.get("selection_reason", {}).get("category") != "wrapper_override":
    print("ERROR: wrapper did not expose explicit action-group selection reason", file=sys.stderr)
    raise SystemExit(1)
if artifact.get("result", {}).get("selected_action_id") != "safe_fixture":
    print("ERROR: wrapper did not persist the expected artifact payload", file=sys.stderr)
    raise SystemExit(1)

print("PASS: aq-runtime-act wrapper behavior validated")
PY
