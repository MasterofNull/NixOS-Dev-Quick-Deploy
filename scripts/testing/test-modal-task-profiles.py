#!/usr/bin/env python3
"""
Phase 162 regression: modal task profiles for local dispatch.

Tests:
- TASK_PROFILES contains all required profiles
- Each profile has required fields (temperature, frequency_penalty, enable_thinking,
  suggested_remote_profile, description)
- build_llama_payload(task_type=X) applies correct profile parameters
- Explicit keyword args override profile (backwards compat)
- No task_type preserves legacy default (temperature=0.3, freq_penalty=0.05)
- classify_task_type() maps prompts to correct profiles
- Mode-driven overrides: ralph→structured, agent→agent
- TaskConfig.from_args() accepts task_type param
- suggest_remote_profile set for all profiles
"""

from __future__ import annotations

import importlib.machinery
import importlib.util
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
SHARED = ROOT / "ai-stack" / "mcp-servers" / "shared"
LIB = ROOT / "scripts" / "ai" / "lib"
sys.path.insert(0, str(SHARED))
sys.path.insert(0, str(LIB))


def assert_true(condition: bool, message: str) -> None:
    if not condition:
        raise AssertionError(message)


def assert_eq(actual, expected, message: str) -> None:
    if actual != expected:
        raise AssertionError(f"{message}: expected {expected!r}, got {actual!r}")


def _load_llm_config():
    loader = importlib.machinery.SourceFileLoader("llm_config", str(SHARED / "llm_config.py"))
    spec = importlib.util.spec_from_loader("llm_config", loader)
    mod = importlib.util.module_from_spec(spec)
    loader.exec_module(mod)
    return mod


def _load_dispatch():
    loader = importlib.machinery.SourceFileLoader("dispatch", str(LIB / "dispatch.py"))
    spec = importlib.util.spec_from_loader("dispatch", loader)
    mod = importlib.util.module_from_spec(spec)
    loader.exec_module(mod)
    return mod


def _load_task_config():
    loader = importlib.machinery.SourceFileLoader("task_config", str(LIB / "task_config.py"))
    spec = importlib.util.spec_from_loader("task_config", loader)
    mod = importlib.util.module_from_spec(spec)
    loader.exec_module(mod)
    return mod


def test_task_profiles_all_present():
    mod = _load_llm_config()
    profiles = mod.TASK_PROFILES
    required = {"structured", "lookup", "code", "reasoning", "agent", "research", "deep_reasoning"}
    for name in required:
        assert_true(name in profiles, f"TASK_PROFILES missing '{name}' profile")
    print("PASS  TASK_PROFILES contains all required profiles")


def test_task_profiles_fields():
    mod = _load_llm_config()
    for name, p in mod.TASK_PROFILES.items():
        assert_true(hasattr(p, "temperature"), f"{name}: missing temperature")
        assert_true(hasattr(p, "frequency_penalty"), f"{name}: missing frequency_penalty")
        assert_true(hasattr(p, "enable_thinking"), f"{name}: missing enable_thinking")
        assert_true(hasattr(p, "suggested_remote_profile"), f"{name}: missing suggested_remote_profile")
        assert_true(hasattr(p, "description"), f"{name}: missing description")
        assert_true(p.suggested_remote_profile, f"{name}: suggested_remote_profile is empty")
    print("PASS  all profiles have required fields")


def test_structured_profile_parameters():
    mod = _load_llm_config()
    payload = mod.build_llama_payload(
        [{"role": "user", "content": "Return as JSON"}],
        task_type="structured",
    )
    assert_eq(payload["temperature"], 0.0, "structured temperature")
    assert_eq(payload["frequency_penalty"], 0.0, "structured frequency_penalty (prevents dense-token EOS)")
    assert_eq(payload["chat_template_kwargs"]["enable_thinking"], False, "structured enable_thinking")
    print("PASS  structured profile: temp=0.0, freq_penalty=0.0, thinking=False")


def test_reasoning_profile_parameters():
    mod = _load_llm_config()
    payload = mod.build_llama_payload(
        [{"role": "user", "content": "Analyze the architecture"}],
        task_type="reasoning",
    )
    assert_eq(payload["temperature"], 0.5, "reasoning temperature")
    assert_eq(payload["frequency_penalty"], 0.05, "reasoning frequency_penalty")
    print(f"PASS  reasoning profile: temp=0.5, freq_penalty=0.05")


def test_code_profile_parameters():
    mod = _load_llm_config()
    payload = mod.build_llama_payload(
        [{"role": "user", "content": "Write a function"}],
        task_type="code",
    )
    assert_eq(payload["temperature"], 0.15, "code temperature")
    assert_eq(payload["frequency_penalty"], 0.0, "code frequency_penalty")
    print("PASS  code profile: temp=0.15, freq_penalty=0.0")


def test_explicit_temperature_overrides_profile():
    """Explicit temperature kwarg must always win over profile default."""
    mod = _load_llm_config()
    payload = mod.build_llama_payload(
        [{"role": "user", "content": "analyze this"}],
        task_type="reasoning",
        temperature=0.1,
    )
    assert_eq(payload["temperature"], 0.1, "explicit temperature override")
    print("PASS  explicit temperature overrides reasoning profile (backwards compat)")


def test_explicit_frequency_penalty_overrides_profile():
    """frequency_penalty in **extra must override profile value."""
    mod = _load_llm_config()
    payload = mod.build_llama_payload(
        [{"role": "user", "content": "Write code"}],
        task_type="code",
        frequency_penalty=0.3,
    )
    assert_eq(payload["frequency_penalty"], 0.3, "explicit frequency_penalty override")
    print("PASS  explicit frequency_penalty overrides code profile")


def test_no_task_type_legacy_defaults():
    """Without task_type, legacy defaults (temp=0.3, freq_penalty=0.05) are preserved."""
    mod = _load_llm_config()
    payload = mod.build_llama_payload([{"role": "user", "content": "hello"}])
    assert_eq(payload["temperature"], 0.3, "legacy temperature default")
    assert_eq(payload["frequency_penalty"], 0.05, "legacy frequency_penalty default")
    print("PASS  no task_type preserves legacy defaults (backwards compat)")


def test_classify_task_type_structured():
    mod = _load_dispatch()
    assert_eq(mod.classify_task_type("return as json", "direct"), "structured", "structured signal")
    assert_eq(mod.classify_task_type("output as json schema", "direct"), "structured", "json schema signal")
    print("PASS  classify_task_type: structured signals → 'structured'")


def test_classify_task_type_lookup():
    mod = _load_dispatch()
    assert_eq(mod.classify_task_type("yes or no", "direct"), "lookup", "yes/no → lookup")
    assert_eq(mod.classify_task_type("reply with one word", "direct"), "lookup", "one word → lookup")
    print("PASS  classify_task_type: tiny signals → 'lookup'")


def test_classify_task_type_reasoning():
    mod = _load_dispatch()
    assert_eq(mod.classify_task_type("analyze the architecture of the system", "direct"), "reasoning", "analyze")
    assert_eq(mod.classify_task_type("evaluate the tradeoff between X and Y", "direct"), "reasoning", "tradeoff")
    print("PASS  classify_task_type: reasoning signals → 'reasoning'")


def test_classify_task_type_code():
    mod = _load_dispatch()
    assert_eq(mod.classify_task_type("implement a sorting function", "direct"), "code", "implement")
    assert_eq(mod.classify_task_type("refactor this module", "direct"), "code", "refactor")
    print("PASS  classify_task_type: code signals → 'code'")


def test_classify_task_type_mode_overrides():
    mod = _load_dispatch()
    assert_eq(mod.classify_task_type("anything", "ralph"), "structured", "ralph mode → structured")
    assert_eq(mod.classify_task_type("anything", "agent"), "agent", "agent mode → agent")
    print("PASS  classify_task_type: mode overrides (ralph→structured, agent→agent)")


def test_classify_task_type_agent_analysis_only():
    mod = _load_dispatch()
    prompt = "analysis only: read these local artifacts, produce ranked remaining slices, do not edit files"
    assert_eq(mod.classify_task_type(prompt, "agent"), "research", "agent analysis-only → research")
    print("PASS  classify_task_type: agent analysis-only prompts → 'research'")


def test_task_config_has_task_type():
    mod = _load_task_config()
    cfg = mod.TaskConfig.from_args(
        mode="direct",
        role="implementer",
        timeout_secs=300,
        max_tokens=None,
        llama_url="http://127.0.0.1:8080",
        hybrid_url="http://127.0.0.1:8003",
        ralph_url="http://127.0.0.1:8004",
        task_type="reasoning",
    )
    assert_eq(cfg.task_type, "reasoning", "TaskConfig.task_type")
    print("PASS  TaskConfig.from_args() accepts and stores task_type")


def test_task_config_analysis_aliases_to_research():
    mod = _load_task_config()
    cfg = mod.TaskConfig.from_args(
        mode="agent",
        role="architect",
        timeout_secs=300,
        max_tokens=None,
        llama_url="http://127.0.0.1:8080",
        hybrid_url="http://127.0.0.1:8003",
        ralph_url="http://127.0.0.1:8004",
        task_type="analysis",
    )
    assert_eq(cfg.task_type, "research", "analysis alias normalizes to research")
    print("PASS  TaskConfig.from_args() normalizes analysis aliases to research")


def test_task_config_invalid_task_type_fallback():
    """Unknown task_type falls back to 'code'."""
    mod = _load_task_config()
    cfg = mod.TaskConfig.from_args(
        mode="direct",
        role="implementer",
        timeout_secs=300,
        max_tokens=None,
        llama_url="http://127.0.0.1:8080",
        hybrid_url="http://127.0.0.1:8003",
        ralph_url="http://127.0.0.1:8004",
        task_type="unknown_profile",
    )
    assert_eq(cfg.task_type, "code", "invalid task_type falls back to 'code'")
    print("PASS  invalid task_type falls back to 'code'")


def test_all_profiles_have_remote_profile():
    mod = _load_llm_config()
    expected_profiles = {
        "structured": "remote-tool-calling",
        "lookup": "remote-free",
        "code": "remote-coding",
        "reasoning": "remote-reasoning",
        "agent": "local-agent",
        "research": "remote-reasoning",
        "deep_reasoning": "remote-reasoning",
    }
    for task_type, expected_remote in expected_profiles.items():
        p = mod.TASK_PROFILES[task_type]
        assert_eq(p.suggested_remote_profile, expected_remote, f"{task_type}.suggested_remote_profile")
    print("PASS  all profiles have correct suggested_remote_profile mappings")


def test_get_task_profile_helper():
    mod = _load_llm_config()
    p = mod.get_task_profile("code")
    assert_true(p is not None, "get_task_profile('code') should return profile")
    assert_eq(p.name, "code", "profile name")
    assert_true(mod.get_task_profile(None) is None, "get_task_profile(None) should return None")
    assert_true(mod.get_task_profile("unknown") is None, "get_task_profile(unknown) should return None")
    print("PASS  get_task_profile() helper works correctly")


if __name__ == "__main__":
    passed = failed = 0
    tests = [
        test_task_profiles_all_present,
        test_task_profiles_fields,
        test_structured_profile_parameters,
        test_reasoning_profile_parameters,
        test_code_profile_parameters,
        test_explicit_temperature_overrides_profile,
        test_explicit_frequency_penalty_overrides_profile,
        test_no_task_type_legacy_defaults,
        test_classify_task_type_structured,
        test_classify_task_type_lookup,
        test_classify_task_type_reasoning,
        test_classify_task_type_code,
        test_classify_task_type_mode_overrides,
        test_classify_task_type_agent_analysis_only,
        test_task_config_has_task_type,
        test_task_config_analysis_aliases_to_research,
        test_task_config_invalid_task_type_fallback,
        test_all_profiles_have_remote_profile,
        test_get_task_profile_helper,
    ]
    for t in tests:
        try:
            t()
            passed += 1
        except Exception as exc:
            print(f"FAIL  {t.__name__}: {exc}")
            failed += 1

    total = passed + failed
    print(f"\n{passed}/{total} tests passed")
    if failed:
        sys.exit(1)
