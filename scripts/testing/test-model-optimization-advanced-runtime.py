#!/usr/bin/env python3
"""Focused runtime regression for advanced Phase 5 model-optimization integrations."""

from __future__ import annotations

import asyncio
import importlib.util
import os
import sys
import tempfile
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "ai-stack" / "mcp-servers"))
sys.path.insert(0, str(ROOT / "ai-stack" / "mcp-servers" / "hybrid-coordinator"))


def assert_true(condition: bool, message: str) -> None:
    if not condition:
        raise AssertionError(message)


def _load_model_optimization_module():
    module_path = ROOT / "ai-stack" / "mcp-servers" / "hybrid-coordinator" / "model_optimization.py"
    spec = importlib.util.spec_from_file_location("hybrid_model_optimization_test", module_path)
    if spec is None or spec.loader is None:
        raise RuntimeError("failed to load model_optimization module spec")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


async def main() -> int:
    with tempfile.TemporaryDirectory(prefix="model-optimization-advanced-") as tmp_dir:
        tmp_path = Path(tmp_dir)
        os.environ["AI_STRICT_ENV"] = "false"
        os.environ["MODEL_OPTIMIZATION_STATE"] = str(tmp_path / "model-optimization")
        os.environ["ACTIVE_LEARNING_STATE"] = str(tmp_path / "active-learning")
        os.environ["SYNTHETIC_DATA_STATE"] = str(tmp_path / "synthetic-data")

        model_optimization = _load_model_optimization_module()
        model_optimization.init(qdrant_client=None, embed_fn=lambda text: [], record_telemetry_fn=None)

        synthetic = await model_optimization.generate_synthetic_training_data(
            target_examples=6,
            categories=["code_generation"],
            strategies=["seed_expansion"],
            min_quality=0.55,
        )
        assert_true(synthetic.get("generated_count", 0) > 0, "synthetic generation should produce examples")
        synthetic_output = Path(synthetic.get("output_path") or "")
        assert_true(synthetic_output.exists(), "synthetic generation should persist output")

        selection = await model_optimization.select_active_learning_examples(
            budget=3,
            strategy="hybrid",
            candidate_paths=[str(synthetic_output)],
        )
        assert_true(len(selection.get("selected_ids") or []) > 0, "active learning should select examples")
        assert_true(Path(selection.get("state_path") or "").exists(), "active learning should persist learner state")

        distillation = await model_optimization.run_distillation_pipeline(
            teacher_model="teacher-8b",
            student_model="student-3b",
            training_data_path=str(synthetic_output),
            quantization_method="gguf",
            quantization_bits=4,
            pruning_sparsity=0.2,
            enable_speculative_decoding=True,
        )
        assert_true(distillation.get("status") == "ready_for_deploy", "distillation pipeline should return ready-for-deploy status")
        assert_true(Path(distillation.get("distillation", {}).get("artifact") or "").exists(), "distillation artifact should be written")
        assert_true(Path(distillation.get("quantization", {}).get("artifact") or "").exists(), "quantization artifact should be written")

        readiness = await model_optimization.get_optimization_readiness()
        readiness_map = readiness.get("readiness") or {}
        assert_true((readiness_map.get("synthetic_generation") or {}).get("status") == "operational", "readiness should expose synthetic generation")
        assert_true((readiness_map.get("active_learning") or {}).get("status") == "operational", "readiness should expose active learning")
        assert_true((readiness_map.get("distillation") or {}).get("status") == "runtime_integrated", "readiness should expose distillation runtime integration")

    print("PASS: advanced model optimization runtime integration")
    return 0


if __name__ == "__main__":
    raise SystemExit(asyncio.run(main()))
