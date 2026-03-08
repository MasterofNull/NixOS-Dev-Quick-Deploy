#!/usr/bin/env bash
# Purpose: Test aq-runtime-plan catalog matching and action generation
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
PLAN_SCRIPT="${ROOT_DIR}/scripts/ai/aq-runtime-plan"
FIXTURE_DIR="${ROOT_DIR}/tests/fixtures/runtime-plan"

if [[ ! -f "${PLAN_SCRIPT}" ]]; then
  echo "ERROR: missing planner script ${PLAN_SCRIPT}" >&2
  exit 2
fi

tmp_unhealthy="$(mktemp)"
tmp_healthy="$(mktemp)"
tmp_suppression="$(mktemp)"
trap 'rm -f "${tmp_unhealthy}" "${tmp_healthy}" "${tmp_suppression}"' EXIT

python3 "${PLAN_SCRIPT}" \
  --qa-fixture "${FIXTURE_DIR}/qa-unhealthy.json" \
  --diagnosis-fixture "${FIXTURE_DIR}/diagnoses-unhealthy.json" \
  > "${tmp_unhealthy}"

python3 "${PLAN_SCRIPT}" \
  --qa-fixture "${FIXTURE_DIR}/qa-healthy.json" \
  --diagnosis-fixture "${FIXTURE_DIR}/diagnoses-healthy.json" \
  > "${tmp_healthy}"

python3 "${PLAN_SCRIPT}" \
  --qa-fixture "${FIXTURE_DIR}/qa-healthy.json" \
  --diagnosis-fixture "${FIXTURE_DIR}/diagnoses-suppression.json" \
  > "${tmp_suppression}"

python3 - "${tmp_unhealthy}" "${tmp_healthy}" "${tmp_suppression}" <<'PY'
import json
import sys
from pathlib import Path

unhealthy = json.loads(Path(sys.argv[1]).read_text(encoding="utf-8"))
healthy = json.loads(Path(sys.argv[2]).read_text(encoding="utf-8"))
suppression = json.loads(Path(sys.argv[3]).read_text(encoding="utf-8"))

if unhealthy["summary"]["phase0_failed"] != 1:
    print("ERROR: unhealthy fixture did not preserve phase0_failed", file=sys.stderr)
    raise SystemExit(1)
context_cards = unhealthy.get("context_cards", {})
recommended_cards = context_cards.get("recommended_cards", [])
if not recommended_cards or recommended_cards[0].get("card_id") != "repo-baseline":
    print("ERROR: planner did not expose the expected leading repo-baseline context card", file=sys.stderr)
    raise SystemExit(1)
if "runtime-incident" not in context_cards.get("recommended_card_order", []):
    print("ERROR: planner did not recommend the runtime-incident context card for the unhealthy fixture", file=sys.stderr)
    raise SystemExit(1)
if "token-discipline" not in context_cards.get("recommended_card_order", []):
    print("ERROR: planner did not recommend the token-discipline context card for the unhealthy fixture", file=sys.stderr)
    raise SystemExit(1)

diagnoses = {item["preset"]: item for item in unhealthy["diagnoses"]}
llama = diagnoses.get("llama-cpp")
hybrid = diagnoses.get("hybrid-coordinator")
if not llama or llama["classification"] != "path_scoped_confinement_likely":
    print("ERROR: llama-cpp diagnosis missing expected confinement classification", file=sys.stderr)
    raise SystemExit(1)
if not hybrid or hybrid["classification"] != "health_probe_failed":
    print("ERROR: hybrid-coordinator diagnosis missing expected health classification", file=sys.stderr)
    raise SystemExit(1)

llama_cmds = llama.get("recommended_commands", [])
if "systemctl cat llama-cpp.service" not in llama_cmds:
    print("ERROR: llama-cpp preset override commands were not loaded from the catalog", file=sys.stderr)
    raise SystemExit(1)
if llama.get("risk") != "medium" or llama.get("safe_in_live_session") is not True:
    print("ERROR: planner did not expose action metadata from the catalog", file=sys.stderr)
    raise SystemExit(1)
hybrid_entries = hybrid.get("recommended_command_entries", [])
if not hybrid_entries or hybrid_entries[-1].get("risk") != "medium":
    print("ERROR: planner did not preserve per-command metadata entries", file=sys.stderr)
    raise SystemExit(1)

actions = unhealthy["next_actions"]
if not actions or "Stabilize base service health first" not in actions[0]["summary"]:
    print("ERROR: planner did not prioritize phase0 stabilization first", file=sys.stderr)
    raise SystemExit(1)
if len(actions) < 2 or "Focus on preset `llama-cpp` at the `confinement` layer." not in actions[1]["summary"]:
    print("ERROR: planner did not prioritize the highest-severity unhealthy preset", file=sys.stderr)
    raise SystemExit(1)
if "Prefer narrowing or bypassing path-scoped confinement before touching package code." not in actions[1]["rollback"]:
    print("ERROR: planner did not surface rollback guidance from the catalog", file=sys.stderr)
    raise SystemExit(1)
approval = unhealthy.get("approval_summary", [])
if len(approval) < 2:
    print("ERROR: planner did not emit approval_summary entries", file=sys.stderr)
    raise SystemExit(1)
if approval[1].get("highest_command_risk") != "medium":
    print("ERROR: planner did not surface the expected highest command risk", file=sys.stderr)
    raise SystemExit(1)
if approval[0].get("action_kind") != "phase0_stabilization":
    print("ERROR: planner did not expose phase0 action_kind in approval_summary", file=sys.stderr)
    raise SystemExit(1)
if approval[1].get("action_kind") != "diagnosis_primary":
    print("ERROR: planner did not expose primary diagnosis action_kind in approval_summary", file=sys.stderr)
    raise SystemExit(1)
if approval[0].get("action_id") != "phase0_stabilization":
    print("ERROR: planner did not expose stable action_id for the phase0 action", file=sys.stderr)
    raise SystemExit(1)
if approval[1].get("action_id") != "diagnosis_primary:llama-cpp.service:confinement":
    print("ERROR: planner did not expose stable action_id for the primary diagnosis action", file=sys.stderr)
    raise SystemExit(1)
if approval[0].get("action_origin", {}).get("source") != "planner" or approval[0].get("action_origin", {}).get("trigger") != "phase0_stabilization":
    print("ERROR: planner did not expose the expected planner action_origin for the phase0 action", file=sys.stderr)
    raise SystemExit(1)
if approval[1].get("action_origin", {}).get("source") != "catalog" or approval[1].get("action_origin", {}).get("classification") != "path_scoped_confinement_likely":
    print("ERROR: planner did not expose the expected catalog action_origin for the confinement action", file=sys.stderr)
    raise SystemExit(1)
if approval[1].get("required_overrides") != []:
    print("ERROR: planner reported unexpected required overrides for the confinement action", file=sys.stderr)
    raise SystemExit(1)
if approval[1].get("bucket") != "observe_first":
    print("ERROR: planner did not classify the confinement action into the expected bucket", file=sys.stderr)
    raise SystemExit(1)
if approval[1].get("confidence") != "high":
    print("ERROR: planner did not expose the expected confidence for the confinement action", file=sys.stderr)
    raise SystemExit(1)
if "action:llama-cpp.service:confinement" not in approval[1].get("evidence_refs", []):
    print("ERROR: planner did not expose the expected evidence_refs for the confinement action", file=sys.stderr)
    raise SystemExit(1)
if approval[1].get("evidence_kind") != "diagnosis" or approval[1].get("evidence_id") != "action:llama-cpp.service:confinement":
    print("ERROR: planner did not expose explicit evidence_kind/evidence_id for the confinement action", file=sys.stderr)
    raise SystemExit(1)
if approval[0].get("provenance") != "planner_builtin_phase0":
    print("ERROR: planner did not expose planner_builtin_phase0 provenance on the phase0 action", file=sys.stderr)
    raise SystemExit(1)
if approval[1].get("provenance") != "catalog_diagnosis":
    print("ERROR: planner did not expose catalog_diagnosis provenance on the confinement action", file=sys.stderr)
    raise SystemExit(1)
evidence_index = unhealthy.get("evidence_index", {})
if evidence_index.get("qa:phase0", {}).get("failed") != 1:
    print("ERROR: planner did not expose the expected qa:phase0 evidence index entry", file=sys.stderr)
    raise SystemExit(1)
if evidence_index.get("action:llama-cpp.service:confinement", {}).get("classification") != "path_scoped_confinement_likely":
    print("ERROR: planner did not expose the expected confinement diagnosis evidence index entry", file=sys.stderr)
    raise SystemExit(1)
groups = unhealthy.get("action_groups", {})
if not groups.get("observe_first"):
    print("ERROR: planner did not emit the observe_first action group", file=sys.stderr)
    raise SystemExit(1)
if groups.get("requires_override") not in ([], None):
    print("ERROR: unhealthy fixture should not require overrides in action_groups", file=sys.stderr)
    raise SystemExit(1)
execution_order = unhealthy.get("execution_order", {})
if execution_order.get("default_group_order") != ["observe_first", "safe_to_run_now", "requires_override"]:
    print("ERROR: planner did not expose the expected default execution order", file=sys.stderr)
    raise SystemExit(1)
if execution_order.get("recommended_group_order") != ["observe_first"]:
    print("ERROR: planner did not expose the expected recommended execution order for the unhealthy fixture", file=sys.stderr)
    raise SystemExit(1)
if groups["observe_first"][0].get("provenance") != "planner_builtin_phase0":
    print("ERROR: planner did not carry planner_builtin_phase0 into grouped actions for the phase0 item", file=sys.stderr)
    raise SystemExit(1)
if groups["observe_first"][0].get("action_kind") != "phase0_stabilization":
    print("ERROR: planner did not carry phase0 action_kind into grouped actions", file=sys.stderr)
    raise SystemExit(1)
if groups["observe_first"][0].get("action_id") != "phase0_stabilization":
    print("ERROR: planner did not carry phase0 action_id into grouped actions", file=sys.stderr)
    raise SystemExit(1)
if groups["observe_first"][0].get("action_origin", {}).get("source") != "planner":
    print("ERROR: planner did not carry phase0 action_origin into grouped actions", file=sys.stderr)
    raise SystemExit(1)
if len(groups["observe_first"]) < 2 or groups["observe_first"][1].get("provenance") != "catalog_diagnosis":
    print("ERROR: planner did not carry provenance into grouped actions for the confinement item", file=sys.stderr)
    raise SystemExit(1)
if len(groups["observe_first"]) < 2 or groups["observe_first"][1].get("action_kind") != "diagnosis_primary":
    print("ERROR: planner did not carry diagnosis action_kind into grouped actions", file=sys.stderr)
    raise SystemExit(1)
if len(groups["observe_first"]) < 2 or groups["observe_first"][1].get("action_id") != "diagnosis_primary:llama-cpp.service:confinement":
    print("ERROR: planner did not carry diagnosis action_id into grouped actions", file=sys.stderr)
    raise SystemExit(1)
if len(groups["observe_first"]) < 2 or groups["observe_first"][1].get("action_origin", {}).get("preset") != "llama-cpp":
    print("ERROR: planner did not carry diagnosis action_origin into grouped actions", file=sys.stderr)
    raise SystemExit(1)

healthy_actions = healthy["next_actions"]
if not healthy_actions or "All inspected presets look healthy." not in healthy_actions[0]["summary"]:
    print("ERROR: planner did not emit the healthy-path action", file=sys.stderr)
    raise SystemExit(1)
if healthy_actions[0].get("provenance") != "planner_builtin_healthy":
    print("ERROR: planner did not mark the healthy-path action as planner_builtin_healthy", file=sys.stderr)
    raise SystemExit(1)
if healthy_actions[0].get("action_kind") != "healthy_cleanup":
    print("ERROR: planner did not expose healthy_cleanup action_kind on the healthy path", file=sys.stderr)
    raise SystemExit(1)
if healthy_actions[0].get("action_id") != "healthy_cleanup":
    print("ERROR: planner did not expose healthy_cleanup action_id on the healthy path", file=sys.stderr)
    raise SystemExit(1)
if healthy_actions[0].get("action_origin", {}).get("source") != "planner" or healthy_actions[0].get("action_origin", {}).get("trigger") != "healthy_cleanup":
    print("ERROR: planner did not expose healthy action_origin on the healthy path", file=sys.stderr)
    raise SystemExit(1)
healthy_context = healthy.get("context_cards", {})
if healthy_context.get("recommended_card_order", []) != ["repo-baseline"]:
    print("ERROR: planner did not keep the healthy-path context recommendation narrow", file=sys.stderr)
    raise SystemExit(1)
healthy_groups = healthy.get("action_groups", {})
if not healthy_groups.get("safe_to_run_now"):
    print("ERROR: planner did not place healthy actions into safe_to_run_now", file=sys.stderr)
    raise SystemExit(1)
healthy_execution_order = healthy.get("execution_order", {})
if healthy_execution_order.get("recommended_group_order") != ["safe_to_run_now"]:
    print("ERROR: planner did not collapse the healthy recommended execution order to the non-empty group", file=sys.stderr)
    raise SystemExit(1)
if len(suppression.get("next_actions", [])) != 1:
    print("ERROR: planner did not suppress redundant same-service same-layer actions", file=sys.stderr)
    raise SystemExit(1)
suppressed = suppression.get("suppressed_actions", [])
if len(suppressed) != 1 or suppressed[0].get("suppression_key") != "ai-hybrid-coordinator.service:service_wiring":
    print("ERROR: planner did not report the expected suppressed action metadata", file=sys.stderr)
    raise SystemExit(1)
if suppressed[0].get("suppression_reason") != "duplicate_service_layer_lower_signal":
    print("ERROR: planner did not expose the expected suppression_reason", file=sys.stderr)
    raise SystemExit(1)
if suppressed[0].get("action_kind") != "diagnosis_secondary":
    print("ERROR: planner did not preserve suppressed action_kind", file=sys.stderr)
    raise SystemExit(1)
if suppressed[0].get("action_id") != "diagnosis_secondary:ai-hybrid-coordinator.service:service_wiring":
    print("ERROR: planner did not preserve suppressed action_id", file=sys.stderr)
    raise SystemExit(1)
if suppressed[0].get("winner_action_kind") != "diagnosis_primary":
    print("ERROR: planner did not expose winner_action_kind for the suppressed action", file=sys.stderr)
    raise SystemExit(1)
if suppressed[0].get("winner_action_id") != "diagnosis_primary:ai-hybrid-coordinator.service:service_wiring":
    print("ERROR: planner did not expose winner_action_id for the suppressed action", file=sys.stderr)
    raise SystemExit(1)
if suppressed[0].get("suppressed_by_action_id") != "diagnosis_primary:ai-hybrid-coordinator.service:service_wiring":
    print("ERROR: planner did not expose suppressed_by_action_id for the suppressed action", file=sys.stderr)
    raise SystemExit(1)
if suppressed[0].get("action_origin", {}).get("source") != "catalog" or suppressed[0].get("winner_action_origin", {}).get("source") != "catalog":
    print("ERROR: planner did not preserve action_origin on suppressed catalog actions", file=sys.stderr)
    raise SystemExit(1)
if "Focus on preset `hybrid-coordinator`" not in suppressed[0].get("winner_summary", ""):
    print("ERROR: planner did not expose the expected winner summary for suppression", file=sys.stderr)
    raise SystemExit(1)
if suppressed[0].get("confidence") != "medium":
    print("ERROR: planner did not expose the expected lowered confidence for the suppressed action", file=sys.stderr)
    raise SystemExit(1)
if suppressed[0].get("evidence_kind") != "diagnosis" or suppressed[0].get("evidence_id") != "action:ai-hybrid-coordinator.service:service_wiring":
    print("ERROR: planner did not expose explicit evidence_kind/evidence_id on the suppressed action", file=sys.stderr)
    raise SystemExit(1)
if suppressed[0].get("provenance") != "catalog_diagnosis":
    print("ERROR: planner did not preserve provenance on the suppressed action", file=sys.stderr)
    raise SystemExit(1)

print("PASS: aq-runtime-plan fixture and catalog behavior validated")
PY
