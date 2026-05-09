#!/usr/bin/env python3

import importlib.util
import os
from pathlib import Path
import sys


_CONFIG_PATH = Path(__file__).resolve().parent.parent / "config.py"
os.environ["AI_STRICT_ENV"] = "false"
sys.path.insert(0, str(_CONFIG_PATH.parent))
sys.path.insert(0, str(_CONFIG_PATH.parent.parent))
_SPEC = importlib.util.spec_from_file_location("hybrid_config_real", _CONFIG_PATH)
assert _SPEC and _SPEC.loader
_MODULE = importlib.util.module_from_spec(_SPEC)
_SPEC.loader.exec_module(_MODULE)
Config = _MODULE.Config


def test_build_local_system_prompt_includes_contact_layer_contract():
    original_identity = Config.AI_LOCAL_SYSTEM_PROMPT_IDENTITY
    original_rules = Config.AI_LOCAL_SYSTEM_PROMPT_RULES
    original_workflow = Config.AI_LOCAL_SYSTEM_PROMPT_WORKFLOW
    original_sections = Config.AI_LOCAL_SYSTEM_PROMPT_OUTPUT_SECTIONS
    original_enabled = Config.AI_LOCAL_SYSTEM_PROMPT
    Config.AI_LOCAL_SYSTEM_PROMPT = True
    Config.AI_LOCAL_SYSTEM_PROMPT_IDENTITY = "You are the first-layer local harness interface."
    Config.AI_LOCAL_SYSTEM_PROMPT_RULES = ["Never invent evidence."]
    Config.AI_LOCAL_SYSTEM_PROMPT_WORKFLOW = ["Use tools first."]
    Config.AI_LOCAL_SYSTEM_PROMPT_OUTPUT_SECTIONS = ["result", "evidence"]
    try:
        prompt = Config.build_local_system_prompt()
    finally:
        Config.AI_LOCAL_SYSTEM_PROMPT_IDENTITY = original_identity
        Config.AI_LOCAL_SYSTEM_PROMPT_RULES = original_rules
        Config.AI_LOCAL_SYSTEM_PROMPT_WORKFLOW = original_workflow
        Config.AI_LOCAL_SYSTEM_PROMPT_OUTPUT_SECTIONS = original_sections
        Config.AI_LOCAL_SYSTEM_PROMPT = original_enabled

    assert "You are the first-layer local harness interface." in prompt
    assert "Non-negotiables:" in prompt
    assert "- Never invent evidence." in prompt
    assert "Workflow:" in prompt
    assert "- Use tools first." in prompt
    assert "Tool contract:" in prompt
    assert "Output sections:" in prompt


def test_default_local_prompt_workflow_includes_structured_request_scaffold():
    workflow = Config.AI_LOCAL_SYSTEM_PROMPT_WORKFLOW

    assert any(
        "Objective -> Constraints -> Context -> Validation -> Route" in step
        for step in workflow
    )
    assert any(
        "aq-feedback-loop --task" in step and "aq-context-bootstrap --task" in step and "continuation_startup_commands" in step
        for step in workflow
    )
    assert any(
        "Do not claim internal behavior, memory writes, or remote-sync behavior as fact unless a tool result supports it." in step
        for step in workflow
    )


def test_default_local_prompt_output_sections_require_evidence_buckets():
    output_sections = Config.AI_LOCAL_SYSTEM_PROMPT_OUTPUT_SECTIONS

    assert output_sections == [
        "observed_signals",
        "inferred_constraints",
        "evidence_sources",
        "unknowns_or_next_checks",
    ]


def test_built_local_system_prompt_mentions_evidence_contract():
    prompt = Config.build_local_system_prompt()

    assert "Keep answers grounded in observed repo state and captured command evidence." in prompt
    assert "aq-feedback-loop --task" in prompt
    assert "continuation_startup_commands" in prompt
    assert "- observed_signals" in prompt
    assert "- evidence_sources" in prompt
