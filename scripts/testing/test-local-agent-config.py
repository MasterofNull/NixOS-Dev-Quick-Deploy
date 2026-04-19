#!/usr/bin/env python3
"""Regression checks for local-agent configuration on the hyperd workstation."""

from __future__ import annotations

import os
import importlib
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
HYBRID_DIR = ROOT / "ai-stack" / "mcp-servers" / "hybrid-coordinator"
HYPERD_FACTS = ROOT / "nix" / "hosts" / "hyperd" / "facts.nix"
SWITCHBOARD = ROOT / "nix" / "modules" / "services" / "switchboard.nix"


def assert_true(condition: bool, message: str) -> None:
    if not condition:
        raise AssertionError(message)


def main() -> int:
    facts_text = HYPERD_FACTS.read_text(encoding="utf-8")
    assert_true(
        'llamaCpp.activeModel = "qwen3.6-35b";' in facts_text,
        "hyperd should pin the local llama.cpp lane to qwen3.6-35b for harness testing",
    )
    assert_true(
        '"--n-gpu-layers" "12"' in facts_text,
        "hyperd should cap Qwen Vulkan offload layers for the local harness host",
    )
    assert_true(
        '"--flash-attn" "off"' in facts_text,
        "hyperd should disable flash attention on the constrained local Qwen host path",
    )
    switchboard_text = SWITCHBOARD.read_text(encoding="utf-8")
    assert_true(
        '"type": "local_model_loading"' in switchboard_text,
        "switchboard should classify the local llama.cpp warmup state explicitly",
    )

    sys.path.insert(0, str(HYBRID_DIR))
    os.environ["AI_STRICT_ENV"] = "false"
    config = importlib.import_module("config")
    assert_true(
        hasattr(config, "HybridSettings"),
        "standalone hybrid-coordinator config import should expose HybridSettings",
    )

    llm_router = importlib.import_module("llm_router")
    assert_true(
        getattr(llm_router, "_ADVISOR_AVAILABLE", False) is True,
        "llm_router should keep advisor support enabled when imported standalone",
    )

    print("PASS: local agent configuration keeps qwen3.6-35b for harness testing and advisor imports work")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
