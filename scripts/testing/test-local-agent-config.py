#!/usr/bin/env python3
"""Regression checks for local-agent configuration on the hyperd workstation."""

from __future__ import annotations

import os
import importlib
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
HYBRID_DIR = ROOT / "ai-stack" / "mcp-servers" / "hybrid-coordinator"
MCP_ROOT = ROOT / "ai-stack" / "mcp-servers"
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
    assert_true(
        'profile not in ("continue-local", "embedded-assist")' in switchboard_text,
        "switchboard should scope forced no-think handling to lightweight local profiles",
    )
    assert_true(
        'kwargs["enable_thinking"] = False' in switchboard_text,
        "switchboard should disable thinking explicitly for lightweight local profiles",
    )
    assert_true(
        "Agent introspection / operator perspective:" in switchboard_text,
        "switchboard local-agent card should document evidence-first introspection guidance",
    )
    assert_true(
        'aq-feedback-loop --task "<prompt>" --format json' in switchboard_text,
        "switchboard local-agent card should route introspection prompts through the feedback loop first",
    )
    assert_true(
        "preflight_commands or continuation_startup_commands" in switchboard_text,
        "switchboard local-agent card should require following context-offload startup packets before analysis",
    )
    assert_true(
        "execute sanctioned aq-* preflight_commands or continuation_startup_commands before answering" in switchboard_text,
        "switchboard local-agent card should require direct execution of sanctioned aq-* startup packets",
    )
    assert_true(
        "Observed signals" in switchboard_text and "Evidence sources" in switchboard_text,
        "switchboard local-agent card should require evidence-oriented introspection output buckets",
    )
    assert_true(
        "Never claim internal behavior, memory writes, or remote-sync behavior as fact unless a tool result supports it." in switchboard_text,
        "switchboard local-agent card should forbid unsupported introspection claims",
    )
    runtime_text = (ROOT / "ai-stack" / "agents" / "runtimes" / "local_agent_runtime.py").read_text(encoding="utf-8")
    assert_true(
        'payload["chat_template_kwargs"] = {"enable_thinking": False}' in runtime_text,
        "local agent runtime should disable thinking explicitly when routed in no-think mode",
    )
    assert_true(
        '"name": "run_harness_cli"' in runtime_text,
        "local agent runtime should expose a bounded harness CLI execution tool",
    )
    assert_true(
        all(token in runtime_text for token in ('"aq-qa"', '"aq-report"', '"aq-operational-perspective"', '"aq-memory"', '"aq-context-bootstrap"', '"aq-feedback-loop"', '"aq-runtime"')),
        "local agent runtime should bound harness CLI execution to the sanctioned aq-* tool surface",
    )

    sys.path.insert(0, str(HYBRID_DIR))
    sys.path.insert(0, str(MCP_ROOT))
    os.environ["AI_STRICT_ENV"] = "false"
    config = importlib.import_module("config")
    assert_true(
        hasattr(config, "HybridSettings"),
        "standalone hybrid-coordinator config import should expose HybridSettings",
    )

    llm_router = importlib.import_module("knowledge.llm_router")
    assert_true(
        getattr(llm_router, "_ADVISOR_AVAILABLE", False) is True,
        "knowledge.llm_router should keep advisor support enabled when imported standalone",
    )

    print("PASS: local agent configuration keeps qwen3.6-35b for harness testing and advisor imports work")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
