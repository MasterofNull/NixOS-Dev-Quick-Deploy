#!/usr/bin/env python3
"""Focused regression coverage for pipeline orchestration primitives."""

from __future__ import annotations

import asyncio
import importlib.util
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
MODULE_PATH = ROOT / "ai-stack" / "agentic-patterns" / "pipeline_orchestration.py"
SPEC = importlib.util.spec_from_file_location("pipeline_orchestration", MODULE_PATH)
pipeline_orchestration = importlib.util.module_from_spec(SPEC)
assert SPEC and SPEC.loader
SPEC.loader.exec_module(pipeline_orchestration)

CrossTeamCoordinator = pipeline_orchestration.CrossTeamCoordinator
HandoffType = pipeline_orchestration.HandoffType
Pipeline = pipeline_orchestration.Pipeline
PipelineOrchestrator = pipeline_orchestration.PipelineOrchestrator
PipelineStage = pipeline_orchestration.PipelineStage
RedistributionReason = pipeline_orchestration.RedistributionReason
StageStatus = pipeline_orchestration.StageStatus
Team = pipeline_orchestration.Team


async def test_end_to_end_pipeline_and_cross_team_handoff() -> None:
    with tempfile.TemporaryDirectory(prefix="pipeline-orchestration-") as tmpdir:
        calls = []

        async def execute_fn(stage_id: str, capability: str, input_data, agent_id: str):
            calls.append((stage_id, capability, input_data, agent_id))
            summary = ""
            if isinstance(input_data, dict):
                summary = str(input_data.get("summary", ""))
            return {
                "stage_id": stage_id,
                "capability": capability,
                "summary": summary,
                "input": input_data,
                "agent_id": agent_id,
            }

        orchestrator = PipelineOrchestrator(output_dir=Path(tmpdir), execute_fn=execute_fn)
        orchestrator.load_balancer.register_agent("researcher-1", 2, {"research", "analysis"})
        orchestrator.load_balancer.register_agent("builder-1", 2, {"implementation"})
        orchestrator.cross_team.register_team(Team("research-team", "Research", ["researcher-1"], {"research", "analysis"}))
        orchestrator.cross_team.register_team(Team("build-team", "Build", ["builder-1"], {"implementation"}))

        pipeline = orchestrator.create_pipeline(
            "feature-flow",
            [
                {"name": "research", "capability": "research"},
                {
                    "name": "implement",
                    "capability": "implementation",
                    "dependencies": ["research"],
                    "handoff": "filtered",
                    "filter_criteria": {"keys": ["summary"]},
                },
            ],
        )

        research_stage = pipeline.stages[0]
        research_stage.assigned_agent = "researcher-1"
        stage_outputs = {
            "_initial": {"summary": "seed", "debug": "ignore"},
            research_stage.stage_id: {"summary": "keep", "debug": "drop"},
        }
        stage_input = orchestrator._gather_stage_input(pipeline.stages[1], stage_outputs, pipeline)
        assert stage_input == {"summary": "keep"}
        assert pipeline.handoffs[0].handoff_type == HandoffType.FILTERED
        pending = orchestrator.cross_team.get_pending_handoffs("build-team")
        assert pending == [("research-team", {"summary": "keep"})]

        result = await orchestrator.execute_pipeline(
            pipeline.pipeline_id,
            initial_input={"summary": "initial", "debug": "discard"},
        )

        assert result["status"] == "completed"
        assert result["stages_completed"] == 2
        assert pipeline.status == StageStatus.COMPLETED
        assert len(calls) == 2
        assert calls[1][2] == {"summary": "initial"}
        assert orchestrator.resume_from_checkpoint(pipeline.pipeline_id, pipeline.stages[0].stage_id)["agent_id"] == "researcher-1"
        saved = orchestrator.save_state()
        assert saved.exists()


def test_build_execution_order_rejects_invalid_dependencies() -> None:
    orchestrator = PipelineOrchestrator(output_dir=Path(tempfile.mkdtemp(prefix="pipeline-order-")))

    missing_dep = Pipeline(
        pipeline_id="pipe-missing",
        name="missing",
        stages=[
            PipelineStage(stage_id="pipe-missing_a", name="a", required_capability="general", dependencies=["ghost"]),
        ],
    )
    try:
        orchestrator._build_execution_order(missing_dep)
    except ValueError as exc:
        assert "Unknown dependency" in str(exc)
    else:
        raise AssertionError("missing dependency should raise ValueError")

    cyclic = Pipeline(
        pipeline_id="pipe-cycle",
        name="cycle",
        stages=[
            PipelineStage(stage_id="pipe-cycle_a", name="a", required_capability="general", dependencies=["b"]),
            PipelineStage(stage_id="pipe-cycle_b", name="b", required_capability="general", dependencies=["a"]),
        ],
    )
    try:
        orchestrator._build_execution_order(cyclic)
    except ValueError as exc:
        assert "dependency cycle" in str(exc)
    else:
        raise AssertionError("cyclic pipeline should raise ValueError")


async def test_redistribution_releases_previous_slot() -> None:
    with tempfile.TemporaryDirectory(prefix="pipeline-redistribution-") as tmpdir:
        orchestrator = PipelineOrchestrator(output_dir=Path(tmpdir))
        orchestrator.load_balancer.register_agent("agent-a", 1, {"implementation"})
        orchestrator.load_balancer.register_agent("agent-b", 1, {"implementation"})

        pipeline = Pipeline(
            pipeline_id="pipe-redist",
            name="redistribute",
            stages=[
                PipelineStage(
                    stage_id="pipe-redist_build",
                    name="build",
                    required_capability="implementation",
                    retry_count=1,
                )
            ],
        )
        stage = pipeline.stages[0]

        calls = {"count": 0}
        original_should_redistribute = orchestrator.load_balancer.should_redistribute

        def should_redistribute(agent_id: str, current_stage: PipelineStage):
            calls["count"] += 1
            if calls["count"] == 1:
                return RedistributionReason.AGENT_OVERLOAD
            return original_should_redistribute(agent_id, current_stage)

        orchestrator.load_balancer.should_redistribute = should_redistribute

        result = await orchestrator._execute_stage_with_retry(stage, {"task": "x"}, pipeline)

        assert result.status == StageStatus.COMPLETED
        assert stage.status == StageStatus.COMPLETED
        assert stage.assigned_agent == "agent-b"
        assert orchestrator.stats["redistributions"] == 1
        assert orchestrator.load_balancer.agents["agent-a"].current_tasks == 0
        assert orchestrator.load_balancer.agents["agent-b"].current_tasks == 0


def test_reference_and_transformed_handoffs() -> None:
    reference_stage = PipelineStage(
        stage_id="ref",
        name="ref",
        required_capability="general",
        handoff_type=HandoffType.REFERENCE,
    )
    transformed_stage = PipelineStage(
        stage_id="transform",
        name="transform",
        required_capability="general",
        handoff_type=HandoffType.TRANSFORMED,
        transform_fn=lambda data: {"count": len(data or [])},
    )

    reference = PipelineOrchestrator._apply_handoff(reference_stage, "source-stage", {"value": 1})
    transformed = PipelineOrchestrator._apply_handoff(transformed_stage, "source-stage", [1, 2, 3])

    assert reference == {"source_stage": "source-stage", "reference_type": "checkpoint"}
    assert transformed == {"count": 3}


def main() -> int:
    asyncio.run(test_end_to_end_pipeline_and_cross_team_handoff())
    test_build_execution_order_rejects_invalid_dependencies()
    asyncio.run(test_redistribution_releases_previous_slot())
    test_reference_and_transformed_handoffs()
    print("PASS: pipeline orchestration primitives are operational")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
