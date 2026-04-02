#!/usr/bin/env python3
"""Static regression checks for Phase 5 model-optimization MCP tool wiring."""

from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
MCP_HANDLERS = ROOT / "ai-stack" / "mcp-servers" / "hybrid-coordinator" / "mcp_handlers.py"
SERVER = ROOT / "ai-stack" / "mcp-servers" / "hybrid-coordinator" / "server.py"
MODEL_OPTIMIZATION = ROOT / "ai-stack" / "mcp-servers" / "hybrid-coordinator" / "model_optimization.py"


def assert_true(condition: bool, message: str) -> None:
    if not condition:
        raise AssertionError(message)


def main() -> int:
    handlers_text = MCP_HANDLERS.read_text(encoding="utf-8")
    server_text = SERVER.read_text(encoding="utf-8")
    optimization_text = MODEL_OPTIMIZATION.read_text(encoding="utf-8")

    for tool_name in [
        "capture_training_example",
        "flush_training_data",
        "get_training_data_stats",
        "start_finetuning_job",
        "get_finetuning_jobs",
        "record_model_performance",
        "get_model_performance",
        "get_optimization_readiness",
        "generate_synthetic_training_data",
        "select_active_learning_examples",
        "run_distillation_pipeline",
    ]:
        assert_true(f'name="{tool_name}"' in handlers_text, f"MCP handlers should expose {tool_name}")
        assert_true(f'elif name == "{tool_name}"' in handlers_text, f"MCP handlers should dispatch {tool_name}")

    assert_true("import model_optimization" in server_text, "server should import model_optimization")
    assert_true("model_optimization.init(" in server_text, "server should initialize model_optimization module")
    assert_true("MODEL_OPTIMIZATION_STATE" in optimization_text, "model optimization module should use writable runtime state")
    assert_true("async def get_optimization_readiness()" in optimization_text, "model optimization module should expose readiness API")
    assert_true("async def generate_synthetic_training_data(" in optimization_text, "model optimization should expose synthetic-data generation")
    assert_true("async def select_active_learning_examples(" in optimization_text, "model optimization should expose active-learning selection")
    assert_true("async def run_distillation_pipeline(" in optimization_text, "model optimization should expose distillation pipeline")

    print("PASS: model optimization MCP tool wiring present")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
