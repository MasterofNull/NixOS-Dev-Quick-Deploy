#!/usr/bin/env python3
"""Targeted checks for aq-bitnet-compare surface."""

import importlib.util
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
MODULE_PATH = ROOT / "scripts" / "ai" / "aq-bitnet-compare.py"
SPEC = importlib.util.spec_from_file_location("aq_bitnet_compare", MODULE_PATH)
if SPEC is None or SPEC.loader is None:
    raise SystemExit("ERROR: unable to load aq-bitnet-compare module")
MODULE = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(MODULE)


def assert_true(condition: bool, message: str) -> None:
    if not condition:
        raise AssertionError(message)


def main() -> int:
    report = MODULE.bitnet_benchmark(Path("/tmp/missing-bitnet"), prompt_tokens=64, gen_tokens=16, threads=4, timeout_seconds=1)
    assert_true(report["status"] == "missing_artifact", "expected missing_artifact for absent BitNet workdir")
    assert_true("missing" in report, "expected missing path detail")
    assert_true(MODULE.DEFAULT_BASELINE_MODEL.endswith(".gguf"), "expected concrete gguf baseline model default")
    print("PASS: aq-bitnet-compare handles baseline defaults and missing BitNet artifacts")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
