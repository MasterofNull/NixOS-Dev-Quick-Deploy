#!/usr/bin/env python3
"""Targeted checks for aq-bitnet-benchmark planning surface."""

import importlib.util
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
MODULE_PATH = ROOT / "scripts" / "ai" / "aq-bitnet-benchmark.py"
SPEC = importlib.util.spec_from_file_location("aq_bitnet_benchmark", MODULE_PATH)
if SPEC is None or SPEC.loader is None:
    raise SystemExit("ERROR: unable to load aq-bitnet-benchmark module")
MODULE = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(MODULE)


def assert_true(condition: bool, message: str) -> None:
    if not condition:
        raise AssertionError(message)


def main() -> int:
    plan = MODULE.build_plan(Path("/tmp/bitnet-benchmark-test"), threads=4, prompt_tokens=256, gen_tokens=64)
    steps = plan.get("steps") or []
    assert_true(len(steps) == 8, "expected full benchmark plan")
    assert_true("BitNet" in steps[0][-1], "expected upstream clone step")
    assert_true("codegen_tl2.py" in steps[3][1], "expected tl2 codegen step")
    assert_true("-DBITNET_X86_TL2=OFF" in steps[4], "expected x86 tl2 cmake flag")
    assert_true("generate-dummy-bitnet-model.py" in steps[6][1], "expected dummy model generation step")
    assert_true("e2e_benchmark.py" in steps[7][1], "expected benchmark execution step")
    print("PASS: aq-bitnet-benchmark builds the expected dummy-model benchmark plan")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
