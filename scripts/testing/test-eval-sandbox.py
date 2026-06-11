#!/usr/bin/env python3
"""Phase 150 Slice 5: verify EvalSandboxExecutor static evaluation logic."""
from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "ai-stack" / "local-agents"))
from eval_sandbox import EvalSandboxExecutor


def test_eval_sandbox() -> None:
    ex = EvalSandboxExecutor()

    # Healthy candidate — should pass
    good = {
        "id": "C-001",
        "category": "health",
        "title": "Fix health-spider timeout",
        "description": "Spider times out on large payloads",
        "proposed_action": "Add 30s timeout to requests",
        "priority": 2,
    }
    res = ex.evaluate(good)
    assert res["sandbox_pass"] is True, f"expected pass, got: {res}"
    assert res["hardware_compatible"] is True
    assert res["tokenomics_impact"] in ("low", "medium", "high")
    assert "violations" not in res

    # GPU violation — should fail hardware_compatible
    bad_gpu = {
        "id": "C-002",
        "category": "performance",
        "title": "Increase GPU layers to 24",
        "description": "Set --n-gpu-layers 24 for better throughput",
        "proposed_action": "n_gpu_layers=24",
        "priority": 1,
    }
    res2 = ex.evaluate(bad_gpu)
    assert res2["sandbox_pass"] is False, f"expected fail, got: {res2}"
    assert res2["hardware_compatible"] is False
    assert any("gpu" in v.lower() for v in res2.get("violations", []))

    # Missing required field — should fail
    bad_schema = {"id": "C-003", "category": "tooling"}  # missing title
    res3 = ex.evaluate(bad_schema)
    assert res3["sandbox_pass"] is False
    assert any("title" in v for v in res3.get("violations", []))

    # Unknown category — still gets evaluated, violation noted
    unk_cat = {
        "id": "C-004",
        "category": "unicorn",
        "title": "A unicorn improvement",
        "priority": 3,
    }
    res4 = ex.evaluate(unk_cat)
    assert any("unknown category" in v for v in res4.get("violations", []))

    # Tokenomics: high-priority delegation-quality → high impact
    high_tok = {
        "id": "C-005",
        "category": "delegation-quality",
        "title": "Improve delegation routing",
        "priority": 1,
    }
    res5 = ex.evaluate(high_tok)
    assert res5["tokenomics_impact"] == "high", f"expected high, got {res5['tokenomics_impact']}"

    print("Test EvalSandboxExecutor: PASSED")
    sys.exit(0)


if __name__ == "__main__":
    try:
        test_eval_sandbox()
    except Exception as exc:
        print(f"Test EvalSandboxExecutor: FAILED - {exc}")
        import traceback
        traceback.print_exc()
        sys.exit(1)
