#!/usr/bin/env bash
# Purpose: Test capability remediation planning and execution
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
PLAN="${ROOT_DIR}/scripts/ai/aq-capability-plan"
RUNNER="${ROOT_DIR}/scripts/ai/aq-capability-remediate"
FIXTURE_DIR="${ROOT_DIR}/tests/fixtures/capability-plan"

tmp_plan="$(mktemp)"
tmp_preview="$(mktemp)"
tmp_execute="$(mktemp)"
tmp_unsafe_plan="$(mktemp)"
tmp_unsafe="$(mktemp)"
trap 'rm -f "${tmp_plan}" "${tmp_preview}" "${tmp_execute}" "${tmp_unsafe_plan}" "${tmp_unsafe}"' EXIT

python3 "${PLAN}" --gap-file "${FIXTURE_DIR}/missing-repo-tool.json" > "${tmp_plan}"
python3 "${RUNNER}" --plan-file "${tmp_plan}" > "${tmp_preview}"
python3 "${RUNNER}" --plan-file "${tmp_plan}" --execute > "${tmp_execute}"
python3 "${PLAN}" --gap-file "${FIXTURE_DIR}/missing-external-cli.json" > "${tmp_unsafe_plan}"
python3 "${RUNNER}" --plan-file "${tmp_unsafe_plan}" --execute > "${tmp_unsafe}"
python3 "${RUNNER}" --gap-file "${FIXTURE_DIR}/missing-repo-tool.json" > /dev/null

python3 - "${tmp_plan}" "${tmp_preview}" "${tmp_execute}" "${tmp_unsafe_plan}" "${tmp_unsafe}" <<'PY'
import json
import sys
from pathlib import Path

plan = json.loads(Path(sys.argv[1]).read_text(encoding="utf-8"))
preview = json.loads(Path(sys.argv[2]).read_text(encoding="utf-8"))
execute = json.loads(Path(sys.argv[3]).read_text(encoding="utf-8"))
unsafe_plan = json.loads(Path(sys.argv[4]).read_text(encoding="utf-8"))
unsafe = json.loads(Path(sys.argv[5]).read_text(encoding="utf-8"))

if plan.get("summary", {}).get("classification") != "missing_repo_tooling":
    print("ERROR: capability plan did not preserve the missing_repo_tooling classification", file=sys.stderr)
    raise SystemExit(1)
if plan.get("context_cards", {}).get("recommended_card_order") != ["capability-gap"]:
    print("ERROR: capability plan did not emit the expected capability-gap context card", file=sys.stderr)
    raise SystemExit(1)
if "repo_harness" != plan.get("summary", {}).get("missing_origin"):
    print("ERROR: capability plan did not preserve missing origin", file=sys.stderr)
    raise SystemExit(1)
if "repo-harness" not in plan.get("summary", {}).get("stack_matchers_applied", []):
    print("ERROR: capability plan did not preserve applied stack matchers", file=sys.stderr)
    raise SystemExit(1)
if preview.get("mode") != "dry-run" or preview.get("selection", {}).get("selected_action_id") != "capability_primary:aq-context-bootstrap":
    print("ERROR: capability remediation preview did not select the expected primary action", file=sys.stderr)
    raise SystemExit(1)
if "repo-harness" not in preview.get("stack_matchers_applied", []):
    print("ERROR: capability remediation preview did not preserve applied stack matchers", file=sys.stderr)
    raise SystemExit(1)
if not any(item.get("resolver") == "repo_script" for item in preview.get("resolver_hints", [])):
    print("ERROR: capability remediation preview did not preserve resolver hints", file=sys.stderr)
    raise SystemExit(1)
if preview.get("repo_manifest_matches") not in ([], None):
    print("ERROR: repo-script remediation preview should not report unrelated repo manifest matches", file=sys.stderr)
    raise SystemExit(1)
if execute.get("results", [])[0].get("returncode") != 0:
    print("ERROR: capability remediation execute did not run the allowed repo-script command", file=sys.stderr)
    raise SystemExit(1)
if unsafe_plan.get("approval_summary", [])[0].get("required_overrides") != ["--allow-unsafe-live"]:
    print("ERROR: unsafe capability plan did not mark override pressure", file=sys.stderr)
    raise SystemExit(1)
if unsafe.get("results", [])[0].get("block_reason") != "unsafe_live_session":
    print("ERROR: capability remediation did not block the unsafe external-cli path", file=sys.stderr)
    raise SystemExit(1)

print("PASS: capability remediation validated")
PY
