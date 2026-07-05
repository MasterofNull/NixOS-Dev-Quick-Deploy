#!/usr/bin/env python3
"""Regression: CollaborativePlanning persists active_plans across processes.

Backlog aq-collaborate-plan-persistence. create_plan() previously stored plans
only in the in-memory active_plans dict, so `aq-collaborate synthesize` (a
separate process) always failed with "Plan not found". This verifies the full
round-trip: create -> persist -> fresh instance reload -> get_plan/synthesize
find the plan, including a contribution and PhaseType enum reconstruction.
"""
import sys
import tempfile
import asyncio
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO / "lib" / "l4-coord" / "agents"))

import collaborative_planning as cp  # noqa: E402


def _fail(msg: str) -> None:
    print(f"FAIL: {msg}")
    sys.exit(1)


def main() -> None:
    tmp = Path(tempfile.mkdtemp(prefix="plan-persist-"))

    for cls in ("PlanContribution", "PlanPhase", "CollaborativePlan"):
        if not hasattr(getattr(cp, cls), "from_dict"):
            _fail(f"{cls}.from_dict missing")

    # Instance A: create + contribute.
    a = cp.CollaborativePlanning(state_dir=tmp)
    plan_id = a.create_plan(task_id="t1", team_id="x")
    a.add_contribution(
        plan_id=plan_id, agent_id="agent_1", content="do the thing",
        suggested_phases=[{"name": "p1", "description": "d", "phase_type": "implementation"}],
        confidence=0.8,
    )

    # Instance B (simulates a separate process): must reload from disk.
    b = cp.CollaborativePlanning(state_dir=tmp)
    plan = b.get_plan(plan_id)
    if plan is None:
        _fail("cross-instance get_plan returned None — active_plans not persisted")
    if plan.task_id != "t1" or plan.team_id != "x":
        _fail(f"reloaded fields wrong: task_id={plan.task_id} team_id={plan.team_id}")
    if not plan.contributions:
        _fail("reloaded plan lost its contributions")

    # Enum integrity: synthesize builds PlanPhase objects; phase_type must be the enum.
    synth = asyncio.run(b.synthesize_plan(plan_id, {"agent_1": ["implementation"]}))
    for ph in synth.phases:
        if not isinstance(ph.phase_type, cp.PhaseType):
            _fail(f"phase_type not a PhaseType enum after round-trip: {type(ph.phase_type)}")

    print(f"PASS: cross-process plan persistence + contribution + enum round-trip "
          f"(plan_id={plan_id}, phases={len(synth.phases)})")


if __name__ == "__main__":
    main()
