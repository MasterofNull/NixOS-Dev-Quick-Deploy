#!/usr/bin/env bash
# Purpose: Test aq-runtime-remediate plan execution and safety controls
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
RUNNER="${ROOT_DIR}/scripts/ai/aq-runtime-remediate"
FIXTURE_DIR="${ROOT_DIR}/tests/fixtures/runtime-plan"

tmp_preview="$(mktemp)"
tmp_preview_by_id="$(mktemp)"
tmp_preview_by_group="$(mktemp)"
tmp_preview_by_preferred_group="$(mktemp)"
tmp_preview_by_plan_order="$(mktemp)"
tmp_list="$(mktemp)"
tmp_preview_meta="$(mktemp)"
tmp_execute="$(mktemp)"
tmp_execute_by_id="$(mktemp)"
tmp_blocked="$(mktemp)"
tmp_unsafe="$(mktemp)"
tmp_command_meta="$(mktemp)"
tmp_missing_id_stdout="$(mktemp)"
tmp_missing_id_stderr="$(mktemp)"
tmp_plan="$(mktemp)"
trap 'rm -f "${tmp_preview}" "${tmp_preview_by_id}" "${tmp_preview_by_group}" "${tmp_preview_by_preferred_group}" "${tmp_preview_by_plan_order}" "${tmp_list}" "${tmp_preview_meta}" "${tmp_execute}" "${tmp_execute_by_id}" "${tmp_blocked}" "${tmp_unsafe}" "${tmp_command_meta}" "${tmp_missing_id_stdout}" "${tmp_missing_id_stderr}" "${tmp_plan}"' EXIT

cp "${FIXTURE_DIR}/remediation-safe-plan.json" "${tmp_plan}"

python3 "${RUNNER}" --plan-file "${tmp_plan}" > "${tmp_preview}"
python3 "${RUNNER}" --plan-file "${tmp_plan}" --action-id safe_fixture > "${tmp_preview_by_id}"
python3 "${RUNNER}" --plan-file "${tmp_plan}" --action-group safe_to_run_now > "${tmp_preview_by_group}"
python3 "${RUNNER}" --plan-file "${tmp_plan}" --prefer-group observe_first --prefer-group safe_to_run_now > "${tmp_preview_by_preferred_group}"
python3 "${RUNNER}" --plan-file "${tmp_plan}" --prefer-plan-order > "${tmp_preview_by_plan_order}"
python3 "${RUNNER}" --plan-file "${tmp_plan}" --list-actions > "${tmp_list}"
python3 "${RUNNER}" --plan-file "${FIXTURE_DIR}/remediation-command-metadata-plan.json" > "${tmp_preview_meta}"
python3 "${RUNNER}" --plan-file "${tmp_plan}" --execute > "${tmp_execute}"
python3 "${RUNNER}" --plan-file "${tmp_plan}" --action-id safe_fixture --execute > "${tmp_execute_by_id}"
python3 "${RUNNER}" --plan-file "${FIXTURE_DIR}/remediation-blocked-plan.json" --execute > "${tmp_blocked}"
python3 "${RUNNER}" --plan-file "${FIXTURE_DIR}/remediation-unsafe-live-plan.json" --execute > "${tmp_unsafe}"
python3 "${RUNNER}" --plan-file "${FIXTURE_DIR}/remediation-command-metadata-plan.json" --execute > "${tmp_command_meta}"
if python3 "${RUNNER}" --plan-file "${tmp_plan}" --action-id missing_fixture > "${tmp_missing_id_stdout}" 2> "${tmp_missing_id_stderr}"; then
  echo "ERROR: missing action-id unexpectedly succeeded" >&2
  exit 1
fi

python3 - "${tmp_preview}" "${tmp_preview_by_id}" "${tmp_preview_by_group}" "${tmp_preview_by_preferred_group}" "${tmp_preview_by_plan_order}" "${tmp_list}" "${tmp_preview_meta}" "${tmp_execute}" "${tmp_execute_by_id}" "${tmp_blocked}" "${tmp_unsafe}" "${tmp_command_meta}" "${tmp_missing_id_stderr}" <<'PY'
import json
import sys
from pathlib import Path

preview = json.loads(Path(sys.argv[1]).read_text(encoding="utf-8"))
preview_by_id = json.loads(Path(sys.argv[2]).read_text(encoding="utf-8"))
preview_by_group = json.loads(Path(sys.argv[3]).read_text(encoding="utf-8"))
preview_by_preferred_group = json.loads(Path(sys.argv[4]).read_text(encoding="utf-8"))
preview_by_plan_order = json.loads(Path(sys.argv[5]).read_text(encoding="utf-8"))
listing = json.loads(Path(sys.argv[6]).read_text(encoding="utf-8"))
preview_meta = json.loads(Path(sys.argv[7]).read_text(encoding="utf-8"))
execute = json.loads(Path(sys.argv[8]).read_text(encoding="utf-8"))
execute_by_id = json.loads(Path(sys.argv[9]).read_text(encoding="utf-8"))
blocked = json.loads(Path(sys.argv[10]).read_text(encoding="utf-8"))
unsafe_live = json.loads(Path(sys.argv[11]).read_text(encoding="utf-8"))
command_meta = json.loads(Path(sys.argv[12]).read_text(encoding="utf-8"))
missing_id = json.loads(Path(sys.argv[13]).read_text(encoding="utf-8"))

if preview.get("mode") != "dry-run":
    print("ERROR: runner did not default to dry-run", file=sys.stderr)
    raise SystemExit(1)
if not preview["action"]["commands"]:
    print("ERROR: runner did not expose action commands in preview mode", file=sys.stderr)
    raise SystemExit(1)
if preview["action"].get("selected_action_id") != "safe_fixture":
    print("ERROR: preview mode did not expose selected_action_id", file=sys.stderr)
    raise SystemExit(1)
if preview.get("selected_action_id") != "safe_fixture" or preview.get("selected_action_kind") != "healthy_cleanup" or preview.get("selected_action_provenance") != "planner_builtin_healthy":
    print("ERROR: preview mode did not expose the expected top-level selected action metadata", file=sys.stderr)
    raise SystemExit(1)
if preview.get("selection", {}).get("selected_action_id") != "safe_fixture":
    print("ERROR: preview mode did not expose the normalized selection object", file=sys.stderr)
    raise SystemExit(1)
if preview_by_id["action"].get("selected_action_id") != "safe_fixture":
    print("ERROR: action-id selection did not resolve the expected action in preview mode", file=sys.stderr)
    raise SystemExit(1)
if preview_by_group["action"].get("selected_action_id") != "safe_fixture":
    print("ERROR: action-group selection did not resolve the expected action in preview mode", file=sys.stderr)
    raise SystemExit(1)
if preview_by_group.get("selected_action_group") != "safe_to_run_now":
    print("ERROR: action-group selection did not expose the resolved group name", file=sys.stderr)
    raise SystemExit(1)
if preview_by_preferred_group["action"].get("selected_action_id") != "safe_fixture":
    print("ERROR: prefer-group selection did not resolve the expected action in preview mode", file=sys.stderr)
    raise SystemExit(1)
if preview_by_preferred_group.get("selected_action_group") != "safe_to_run_now":
    print("ERROR: prefer-group selection did not expose the resolved fallback group", file=sys.stderr)
    raise SystemExit(1)
if preview_by_plan_order["action"].get("selected_action_id") != "safe_fixture":
    print("ERROR: prefer-plan-order selection did not resolve the expected action in preview mode", file=sys.stderr)
    raise SystemExit(1)
if preview_by_plan_order.get("selected_action_group") != "safe_to_run_now":
    print("ERROR: prefer-plan-order selection did not expose the resolved recommended group", file=sys.stderr)
    raise SystemExit(1)
if listing.get("mode") != "list" or not listing.get("actions"):
    print("ERROR: list-actions mode did not return an action listing", file=sys.stderr)
    raise SystemExit(1)
if listing["actions"][0].get("action_id") != "safe_fixture":
    print("ERROR: list-actions mode did not expose the expected stable action_id", file=sys.stderr)
    raise SystemExit(1)
if listing.get("groups", {}).get("safe_to_run_now", [])[0].get("action_id") != "safe_fixture":
    print("ERROR: list-actions mode did not expose the expected grouped action listing", file=sys.stderr)
    raise SystemExit(1)
if not preview_meta["action"].get("command_entries"):
    print("ERROR: runner did not expose structured command entries in preview mode", file=sys.stderr)
    raise SystemExit(1)
if execute.get("mode") != "execute":
    print("ERROR: runner did not switch to execute mode", file=sys.stderr)
    raise SystemExit(1)
if not execute.get("results"):
    print("ERROR: execute mode did not return command results", file=sys.stderr)
    raise SystemExit(1)
if execute["results"][0]["returncode"] != 0:
    print("ERROR: first remediation command failed in execute mode", file=sys.stderr)
    raise SystemExit(1)
if "runner-ok" not in execute["results"][0]["stdout"]:
    print("ERROR: execute mode did not capture command stdout", file=sys.stderr)
    raise SystemExit(1)
if execute["results"][0].get("blocked") is not False:
    print("ERROR: successful command should not be marked blocked", file=sys.stderr)
    raise SystemExit(1)
if execute_by_id["results"][0]["returncode"] != 0 or "runner-ok" not in execute_by_id["results"][0]["stdout"]:
    print("ERROR: action-id execute path did not run the expected safe fixture command", file=sys.stderr)
    raise SystemExit(1)
if blocked["results"][0]["returncode"] != 126:
    print("ERROR: blocked command did not fail with policy return code", file=sys.stderr)
    raise SystemExit(1)
if "blocked by runtime remediation policy" not in blocked["results"][0]["stderr"]:
    print("ERROR: blocked command did not surface policy message", file=sys.stderr)
    raise SystemExit(1)
if blocked["results"][0].get("block_reason") != "policy_prefix_not_allowed":
    print("ERROR: blocked command did not expose the expected policy block_reason", file=sys.stderr)
    raise SystemExit(1)
if blocked["results"][0].get("required_overrides") != []:
    print("ERROR: blocked command did not expose the expected empty override list", file=sys.stderr)
    raise SystemExit(1)
if unsafe_live["results"][0]["returncode"] != 126:
    print("ERROR: unsafe-live action did not fail with metadata policy return code", file=sys.stderr)
    raise SystemExit(1)
if "not safe in live session" not in unsafe_live["results"][0]["stderr"]:
    print("ERROR: unsafe-live action did not surface metadata block message", file=sys.stderr)
    raise SystemExit(1)
if unsafe_live["results"][0].get("block_reason") != "unsafe_live_session":
    print("ERROR: unsafe-live action did not expose the expected block_reason", file=sys.stderr)
    raise SystemExit(1)
if unsafe_live["results"][0].get("required_overrides") != ["--allow-unsafe-live"]:
    print("ERROR: unsafe-live action did not expose the expected override flag", file=sys.stderr)
    raise SystemExit(1)
if len(command_meta["results"]) != 2:
    print("ERROR: per-command metadata plan did not produce two execution results", file=sys.stderr)
    raise SystemExit(1)
if "first-ok" not in command_meta["results"][0]["stdout"]:
    print("ERROR: per-command metadata plan did not execute the safe first command", file=sys.stderr)
    raise SystemExit(1)
if command_meta["results"][1]["returncode"] != 126 or "not safe in live session" not in command_meta["results"][1]["stderr"]:
    print("ERROR: per-command metadata plan did not block the unsafe second command", file=sys.stderr)
    raise SystemExit(1)
if command_meta["results"][1].get("block_reason") != "unsafe_live_session":
    print("ERROR: per-command metadata plan did not expose block_reason on the blocked command", file=sys.stderr)
    raise SystemExit(1)
if command_meta["results"][1].get("rollback") != "No rollback needed.":
    print("ERROR: per-command metadata plan did not propagate rollback context", file=sys.stderr)
    raise SystemExit(1)
if missing_id.get("error") != "action-id not found" or not missing_id.get("available_actions"):
    print("ERROR: missing action-id path did not expose available action hints", file=sys.stderr)
    raise SystemExit(1)

print("PASS: aq-runtime-remediate dry-run and execute behavior validated")
PY
