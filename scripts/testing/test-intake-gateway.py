#!/usr/bin/env python3
import asyncio
import sys
from pathlib import Path

# Dynamically add the hybrid-coordinator module to sys.path for testing
repo_root = Path(__file__).resolve().parent.parent.parent
hybrid_coordinator_path = repo_root / "ai-stack" / "mcp-servers" / "hybrid-coordinator"
sys.path.insert(0, str(hybrid_coordinator_path))

from intake_gateway import build_lifecycle_pipeline, LifecycleSession

async def test_intake_gateway():
    pipeline = build_lifecycle_pipeline()

    # 1. Simple Task (should skip DISCOVER and PRD)
    simple_session = LifecycleSession(
        session_id="test-simple",
        task_description="fix typo"
    )
    res_simple = await pipeline.process(simple_session)
    assert res_simple.complexity == "simple"
    assert res_simple.current_phase == "COMMIT"
    assert "discover_complete" not in res_simple.context
    assert "prd_generated" not in res_simple.context

    # 2. Complex Task (should hit DISCOVER and PRD)
    long_task = "We need a complete redesign of the network. " * 10
    complex_session = LifecycleSession(
        session_id="test-complex",
        task_description=long_task
    )
    res_complex = await pipeline.process(complex_session)
    assert res_complex.complexity == "complex"
    assert res_complex.current_phase == "COMMIT"
    assert res_complex.context.get("discover_complete") is True
    assert res_complex.context.get("prd_generated") is True

    # 3. Validation Failure
    empty_session = LifecycleSession(
        session_id="test-empty",
        task_description=""
    )
    res_empty = await pipeline.process(empty_session)
    assert res_empty.halt_execution is True
    assert "Validation Error" in res_empty.errors[0]

    print("✅ Intake Gateway UAG pipeline tests passed!")

if __name__ == "__main__":
    asyncio.run(test_intake_gateway())
