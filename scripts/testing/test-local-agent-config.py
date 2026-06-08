#!/usr/bin/env python3
"""Regression checks for local-agent configuration on the hyperd workstation."""

from __future__ import annotations

import os
import importlib
import re
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
HYBRID_DIR = ROOT / "ai-stack" / "mcp-servers" / "hybrid-coordinator"
MCP_ROOT = ROOT / "ai-stack" / "mcp-servers"
HYPERD_FACTS = ROOT / "nix" / "hosts" / "hyperd" / "facts.nix"
SWITCHBOARD = ROOT / "nix" / "modules" / "services" / "switchboard.nix"
SWITCHBOARD_PY = ROOT / "ai-stack" / "switchboard" / "switchboard.py"


def assert_true(condition: bool, message: str) -> None:
    if not condition:
        raise AssertionError(message)


def main() -> int:
    facts_text = HYPERD_FACTS.read_text(encoding="utf-8")
    assert_true(
        'llamaCpp.activeModel = "qwen3.6-35b-mtp-q5";' in facts_text,
        "hyperd should pin the local llama.cpp lane to qwen3.6-35b-mtp-q5 for harness testing",
    )
    assert_true(
        '"--n-gpu-layers" "12"' in facts_text,
        "hyperd should cap Qwen Vulkan offload layers for the local harness host",
    )
    assert_true(
        "q8_0 KV cache requires --flash-attn" in facts_text,
        "hyperd should document flash-attn as required by the q8_0 KV cache path",
    )
    local_model_text = (ROOT / "config" / "local-model-config.yaml").read_text(encoding="utf-8")
    assert_true(
        "flash_attn: true" in local_model_text,
        "local-model-config.yaml should mirror the q8_0 KV cache flash-attn deployment path",
    )
    switchboard_text = SWITCHBOARD.read_text(encoding="utf-8")
    assert_true(
        "[profile-card:local-tool-calling]" in switchboard_text,
        "switchboard should expose the local tool-calling profile card",
    )
    assert_true(
        "[profile-card:embedded-assist]" in switchboard_text and "/no_think" in switchboard_text,
        "switchboard should expose no-think local profile cards",
    )
    switchboard_py_text = SWITCHBOARD_PY.read_text(encoding="utf-8")
    assert_true(
        'kwargs["enable_thinking"] = False' in switchboard_py_text,
        "switchboard should disable thinking explicitly for local profiles",
    )
    assert_true(
        "current_val is True and not is_reasoning_profile" in switchboard_py_text,
        "switchboard should override caller-supplied thinking mode for non-reasoning local profiles",
    )
    assert_true(
        "is_reasoning_profile" in switchboard_py_text,
        "switchboard should leave room for explicit reasoning profiles",
    )
    runtime_text = (ROOT / "ai-stack" / "agents" / "runtimes" / "local_agent_runtime.py").read_text(encoding="utf-8")
    assert_true(
        "build_llama_payload(" in runtime_text,
        "local agent runtime should use the shared llama payload builder for no-think mode",
    )
    llm_config_text = (ROOT / "ai-stack" / "mcp-servers" / "shared" / "llm_config.py").read_text(encoding="utf-8")
    assert_true(
        '"chat_template_kwargs": {"enable_thinking": False}' in llm_config_text,
        "shared llama payload builder should disable thinking explicitly",
    )
    aq_chat_text = (ROOT / "scripts" / "ai" / "aq-chat").read_text(encoding="utf-8")
    assert_true(
        "enable_thinking=true" not in aq_chat_text,
        "aq-chat system prompt should not contradict the local no-think request contract",
    )
    assert_true(
        re.search(r"enable_thinking[\"']\s*:\s*True", aq_chat_text) is None,
        "aq-chat should never send enable_thinking=True to local llama.cpp or switchboard local tools",
    )
    assert_true(
        aq_chat_text.count('"chat_template_kwargs"] = {"enable_thinking": False}') >= 2,
        "aq-chat should disable thinking for direct local and local-tool-calling payloads",
    )
    agent_executor_text = (ROOT / "ai-stack" / "local-agents" / "agent_executor.py").read_text(encoding="utf-8")
    training_ingest_text = (ROOT / "ai-stack" / "local-agents" / "training_ingest.py").read_text(encoding="utf-8")
    drop_spec_text = (ROOT / "scripts" / "ai" / "lib" / "drop_spec.py").read_text(encoding="utf-8")
    assert_true(
        "safe_load_all" in agent_executor_text and "safe_load_all" in training_ingest_text and "safe_load_all" in drop_spec_text,
        "agent prompt extension and drop-zone YAML readers should support multi-document YAML",
    )
    phase0_text = (ROOT / "scripts" / "testing" / "harness_qa" / "phases" / "phase0.py").read_text(encoding="utf-8")
    assert_true(
        "safe_load_all(config.read_text())" in phase0_text,
        "aq-qa local model config check should support multi-document YAML",
    )
    gate_text = (ROOT / "scripts" / "testing" / "gate-local-payload-discipline.sh").read_text(encoding="utf-8")
    assert_true(
        ("enable_thinking=" + "True") in gate_text and "--include=\"aq-chat\"" in gate_text,
        "local payload discipline gate should reject thinking-mode drift in Python and aq-chat sources",
    )
    assert_true(
        '"name": "run_harness_cli"' in runtime_text,
        "local agent runtime should expose a bounded harness CLI execution tool",
    )
    assert_true(
        all(token in runtime_text for token in ('"aq-qa"', '"aq-report"', '"aq-operational-perspective"', '"aq-introspection-validate"', '"aq-memory"', '"aq-context-bootstrap"', '"aq-context-manage"', '"aq-feedback-loop"', '"aq-hints"', '"aq-runtime"')),
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

    print("PASS: local agent configuration keeps qwen3.6-35b-mtp-q5 for harness testing and advisor imports work")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
