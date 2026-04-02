#!/usr/bin/env python3
"""Focused regression checks for Phase 5 model optimization implementations."""

from __future__ import annotations

import asyncio
import importlib.util
import json
import sys
import tempfile
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]


def load_module(name: str, relative_path: str):
    path = ROOT / relative_path
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module


def assert_true(condition: bool, message: str) -> None:
    if not condition:
        raise AssertionError(message)


async def main() -> int:
    synthetic_data = load_module(
        "phase5_synthetic_data",
        "ai-stack/model-optimization/synthetic_data.py",
    )
    active_learning = load_module(
        "phase5_active_learning",
        "ai-stack/model-optimization/active_learning.py",
    )
    distillation = load_module(
        "phase5_distillation",
        "ai-stack/model-optimization/distillation.py",
    )

    with tempfile.TemporaryDirectory(prefix="phase5-impl-") as tmp_dir:
        tmp_path = Path(tmp_dir)

        async def fake_teacher(prompt: str) -> str:
            snippet = prompt.strip().splitlines()[0][:80]
            return (
                "```python\n"
                f"def generated_solution():\n    return {len(snippet)}\n"
                "```\n"
                f"Explanation for: {snippet}"
            )

        generator = synthetic_data.SyntheticDataGenerator(
            output_dir=tmp_path / "synthetic",
            teacher_model_fn=fake_teacher,
        )
        generation_config = synthetic_data.GenerationConfig(
            target_examples=6,
            categories=[
                synthetic_data.TaskCategory.CODE_GENERATION,
                synthetic_data.TaskCategory.DEBUGGING,
            ],
            strategies=[
                synthetic_data.GenerationStrategy.SELF_INSTRUCT,
                synthetic_data.GenerationStrategy.SEED_EXPANSION,
            ],
            min_quality=0.45,
            batch_size=2,
            rate_limit_delay=0.0,
        )
        examples = await generator.generate_batch(generation_config)
        saved_examples = generator.save_examples(filename="synthetic.jsonl")
        assert_true(len(examples) >= 4, "synthetic data generator should keep multiple examples")
        assert_true(saved_examples.exists(), "synthetic data generator should persist output")

        candidates = [
            active_learning.CandidateExample(
                id=example.id,
                prompt=example.prompt,
                response=example.response,
                metadata={"quality_score": example.quality_score},
            )
            for example in examples
        ]
        learner = active_learning.ActiveLearner(
            strategy=active_learning.AcquisitionStrategy.HYBRID,
            output_dir=tmp_path / "active-learning",
        )
        selection = await learner.select(candidates, budget=3)
        state_path = learner.save_state()
        assert_true(len(selection.selected_ids) == 3, "active learner should honor selection budget")
        assert_true(selection.coverage_estimate > 0, "active learner should compute positive coverage")
        assert_true(state_path.exists(), "active learner should persist state")

        model_path = tmp_path / "model.bin"
        model_path.write_bytes(b"x" * 8 * 1024 * 1024)

        quantizer = distillation.ModelQuantizer()
        quantized = quantizer.quantize(
            model_path,
            distillation.QuantizationConfig(
                method=distillation.QuantizationMethod.AWQ,
                bits=4,
                calibration_samples=256,
            ),
            tmp_path / "artifacts" / "awq",
        )
        quant_manifest = json.loads(quantized.output_path.read_text(encoding="utf-8"))
        assert_true(quantized.compressed_size_mb < quantized.original_size_mb, "quantization should reduce size")
        assert_true(quant_manifest["method"] == "awq", "quantization manifest should record the method")

        pruner = distillation.ModelPruner()
        pruned = pruner.prune(
            model_path,
            sparsity=0.3,
            output_path=tmp_path / "artifacts" / "pruning",
            config=distillation.PruningConfig(
                sparsity=0.3,
                method=distillation.PruningMethod.STRUCTURED,
                iterative_steps=3,
            ),
        )
        prune_manifest = json.loads(pruned.output_path.read_text(encoding="utf-8"))
        assert_true(len(prune_manifest["schedule"]) == 3, "pruning should emit the full iterative schedule")
        assert_true(pruned.latency_improvement > 1.0, "pruning should estimate a speed benefit")

        decoder = distillation.SpeculativeDecoder()
        spec_config = decoder.setup_speculative_pair(tmp_path / "llama-1b", tmp_path / "llama-7b")
        simulated = decoder.simulate_generation(prompt_tokens=48, output_tokens=96, config=spec_config)
        assert_true(simulated["estimated_speedup"] > 1.0, "speculative decoding should estimate speedup")
        assert_true(spec_config["num_draft_tokens"] >= 2, "speculative decoding should size draft chunks dynamically")

        training_data = tmp_path / "training.jsonl"
        training_data.write_text(
            "\n".join(
                json.dumps({"prompt": ex.prompt, "response": ex.response})
                for ex in examples
            ),
            encoding="utf-8",
        )
        distiller = distillation.KnowledgeDistiller()
        distilled = await distiller.distill(
            distillation.DistillationConfig(
                teacher_model="llama-7b",
                student_model="llama-1b",
                num_epochs=2,
                dataset_size=len(examples),
            ),
            training_data,
            tmp_path / "artifacts" / "distilled",
        )
        assert_true(distilled.compression_ratio > 1.0, "distillation should estimate compression")
        assert_true(distilled.output_path.exists(), "distillation should persist a manifest")

        optimizer = distillation.CompressionOptimizer()
        best = optimizer.find_optimal_compression(
            model_path,
            distillation.CompressionTarget.BALANCED,
            max_accuracy_drop=0.05,
        )
        assert_true(best is not None, "optimizer should find at least one viable compression candidate")
        assert_true(best.accuracy_drop <= 0.05, "optimizer should honor the accuracy cap")

    print("PASS: Phase 5 implementation primitives are operational")
    return 0


if __name__ == "__main__":
    raise SystemExit(asyncio.run(main()))
