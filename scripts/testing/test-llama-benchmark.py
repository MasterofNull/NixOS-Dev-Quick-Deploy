#!/usr/bin/env python3
"""Targeted checks for aq-llama-benchmark worksheet and metric parsing."""

import importlib.util
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
MODULE_PATH = ROOT / "scripts" / "ai" / "aq-llama-benchmark.py"
SPEC = importlib.util.spec_from_file_location("aq_llama_benchmark", MODULE_PATH)
if SPEC is None or SPEC.loader is None:
    raise SystemExit("ERROR: unable to load aq-llama-benchmark module")
MODULE = importlib.util.module_from_spec(SPEC)
sys.modules[SPEC.name] = MODULE
SPEC.loader.exec_module(MODULE)


def assert_true(condition: bool, message: str) -> None:
    if not condition:
        raise AssertionError(message)


def main() -> int:
    batch = MODULE.build_batch([8192, 16384])
    runs = batch.get("runs") or []
    assert_true(len(runs) == 10, "expected 5 models x 2 contexts")
    assert_true(runs[0]["run_id"] == "qwen3_4b_q4_k_m_ctx8192", "expected stable run id format")
    assert_true(runs[-1]["run_id"] == "qwen3_8b_q4_k_m_ctx16384", "expected final batch entry")
    assert_true(batch["winners_extend_to_ctx"] == [32768], "expected 32K winner extension rule")

    metrics = MODULE.parse_metrics(
        "\n".join(
            [
                "# comment",
                "llamacpp:prompt_tokens_total 12",
                "llamacpp:tokens_predicted_total 8",
                "llamacpp:requests_deferred 0",
            ]
        )
    )
    assert_true(metrics["llamacpp:prompt_tokens_total"] == 12.0, "expected prompt token metric parse")
    assert_true(metrics["llamacpp:tokens_predicted_total"] == 8.0, "expected predicted token metric parse")
    assert_true(metrics["llamacpp:requests_deferred"] == 0.0, "expected deferred request metric parse")
    print("PASS: aq-llama-benchmark builds the requested batch and parses llama.cpp metrics")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
