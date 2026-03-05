#!/usr/bin/env bash
set -euo pipefail

# Validate PRSI bootstrap integration across blueprint/policy/prompt/schemas/knowledge sources.
# Intended as a fast, deterministic local release gate.

ROOT_DIR="${ROOT:-$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)}"

python3 - "$ROOT_DIR" <<'PY'
import json
import sys
from pathlib import Path

root = Path(sys.argv[1])

blueprints_path = root / "config/workflow-blueprints.json"
policy_path = root / "config/runtime-prsi-policy.json"
prompts_path = root / "ai-stack/prompts/registry.yaml"
knowledge_path = root / "ai-stack/data/knowledge-sources.yaml"
plan_path = root / "docs/SYSTEM-IMPROVEMENT-PLAN-2026-03.md"

schema_paths = [
    root / "config/schemas/prsi/cycle-plan.schema.json",
    root / "config/schemas/prsi/validation-report.schema.json",
    root / "config/schemas/prsi/cycle-outcome.schema.json",
]

phase7_policy_refs = [
    root / "config/prsi/validation-matrix.json",
    root / "config/prsi/confidence-calibration-policy.json",
    root / "config/prsi/eval-pinning-policy.json",
    root / "config/prsi/quarantine-workflow.json",
    root / "config/prsi/high-risk-approval-rubric.json",
    root / "config/prsi/edge-brownout-policy.json",
]

required_knowledge_ids = {
    "prsi-research-index",
    "react-paper",
    "toolformer-paper",
    "reflexion-paper",
    "self-refine-paper",
    "voyager-paper",
    "constitutional-ai-paper",
    "openai-eval-best-practices",
    "swe-agent-docs",
    "swebench-contamination-2506",
    "swebench-contamination-2512",
    "swebench-contamination-2510",
}

try:
    import yaml  # type: ignore
except Exception as exc:
    raise SystemExit(f"ERROR: pyyaml unavailable: {exc}")


def must_exist(path: Path) -> None:
    if not path.exists():
        raise SystemExit(f"ERROR: missing required file: {path}")


def read_json(path: Path):
    must_exist(path)
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        raise SystemExit(f"ERROR: invalid JSON in {path}: {exc}")


for p in [blueprints_path, policy_path, prompts_path, knowledge_path, plan_path, *schema_paths, *phase7_policy_refs]:
    must_exist(p)

blueprints = read_json(blueprints_path)
policy = read_json(policy_path)

if not isinstance(blueprints, dict) or not isinstance(blueprints.get("blueprints"), list):
    raise SystemExit("ERROR: workflow-blueprints.json missing blueprints array")

prsi_bp = next((b for b in blueprints["blueprints"] if isinstance(b, dict) and b.get("id") == "prsi-pessimistic-recursive-improvement"), None)
if prsi_bp is None:
    raise SystemExit("ERROR: missing PRSI workflow blueprint id=prsi-pessimistic-recursive-improvement")

phases = prsi_bp.get("phases")
if not isinstance(phases, list) or len(phases) < 6:
    raise SystemExit("ERROR: PRSI workflow blueprint must define >=6 phases")

phase_ids = [p.get("id") for p in phases if isinstance(p, dict)]
for expected in ["scope_lock", "discover", "propose", "execute", "verify", "learn", "decide"]:
    if expected not in phase_ids:
        raise SystemExit(f"ERROR: PRSI workflow blueprint missing phase '{expected}'")

cycle = policy.get("cycle")
if not isinstance(cycle, dict):
    raise SystemExit("ERROR: runtime-prsi-policy missing cycle object")

required_artifacts = cycle.get("required_artifacts")
if not isinstance(required_artifacts, list):
    raise SystemExit("ERROR: runtime-prsi-policy.cycle.required_artifacts must be a list")
for name in ["cycle_plan.json", "patch.diff", "validation_report.json", "cycle_outcome.json", "rollback_notes.md"]:
    if name not in required_artifacts:
        raise SystemExit(f"ERROR: runtime-prsi-policy missing artifact requirement '{name}'")

if cycle.get("max_mutating_actions") != 1:
    raise SystemExit("ERROR: runtime-prsi-policy.cycle.max_mutating_actions must be 1")

gates = policy.get("gates", {}) if isinstance(policy.get("gates"), dict) else {}
if not bool(gates.get("require_independent_verifier_for_high_risk", False)):
    raise SystemExit("ERROR: runtime-prsi-policy.gates.require_independent_verifier_for_high_risk must be true")

policy_refs = policy.get("policy_refs")
if not isinstance(policy_refs, dict):
    raise SystemExit("ERROR: runtime-prsi-policy missing policy_refs object")

prompt_doc = yaml.safe_load(prompts_path.read_text(encoding="utf-8"))
prompts = prompt_doc.get("prompts") if isinstance(prompt_doc, dict) else None
if not isinstance(prompts, list):
    raise SystemExit("ERROR: prompt registry missing prompts list")
if not any(isinstance(p, dict) and p.get("id") == "prsi_pessimistic_cycle_orchestrator" for p in prompts):
    raise SystemExit("ERROR: missing prompt id=prsi_pessimistic_cycle_orchestrator")

knowledge_doc = yaml.safe_load(knowledge_path.read_text(encoding="utf-8"))
sources = knowledge_doc.get("sources") if isinstance(knowledge_doc, dict) else None
if not isinstance(sources, list):
    raise SystemExit("ERROR: knowledge-sources missing sources list")
source_ids = {s.get("id") for s in sources if isinstance(s, dict)}
missing_sources = sorted(required_knowledge_ids - source_ids)
if missing_sources:
    raise SystemExit(f"ERROR: missing PRSI knowledge source ids: {missing_sources}")

for schema_path in schema_paths:
    schema = read_json(schema_path)
    if schema.get("type") != "object":
        raise SystemExit(f"ERROR: schema must be object type: {schema_path}")

plan_text = plan_path.read_text(encoding="utf-8")
for marker in [
    "## PRSI Master Prompt Integration",
    "## Phase 7 — Pessimistic Recursive Self-Improvement (PRSI) Program",
    "## Overlooked or Underspecified Items",
]:
    if marker not in plan_text:
        raise SystemExit(f"ERROR: plan missing marker: {marker}")

print("PASS: PRSI bootstrap integrity validated")
PY
