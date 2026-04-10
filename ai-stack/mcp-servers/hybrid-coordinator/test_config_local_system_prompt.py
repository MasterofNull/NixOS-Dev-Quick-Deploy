#!/usr/bin/env python3

import importlib.util
import os
from pathlib import Path
import sys


_CONFIG_PATH = Path(__file__).with_name("config.py")
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
