"""
Unit tests for mcp_handlers.py — dispatch table and pure helper functions.

Tests the pure, import-safe functions: phase normalization, env builder,
binary resolution, and dispatch-table validation. External imports
(mcp.types, shared.tool_audit, tooling_manifest, memory_manager) are
stubbed before the module is loaded.
"""
from __future__ import annotations

import asyncio
import os
import sys
import types
from pathlib import Path

import pytest

_HC_DIR = Path(__file__).resolve().parent.parent
if str(_HC_DIR) not in sys.path:
    sys.path.insert(0, str(_HC_DIR))

# Stub external dependencies before importing mcp_handlers.
# Tool and TextContent are instantiated at module level in mcp_handlers.py
# so stubs must accept keyword arguments.
def _make_kw_class(name: str):
    return type(name, (), {"__init__": lambda self, **kwargs: None})

_mcp_types_stub = types.SimpleNamespace(
    TextContent=_make_kw_class("TextContent"),
    Tool=_make_kw_class("Tool"),
)
sys.modules.setdefault("mcp", types.SimpleNamespace(types=_mcp_types_stub))
sys.modules.setdefault("mcp.types", _mcp_types_stub)
sys.modules.setdefault(
    "shared",
    types.SimpleNamespace(
        tool_audit=types.SimpleNamespace(write_audit_entry=lambda *a, **k: None)
    ),
)
sys.modules.setdefault(
    "shared.tool_audit",
    types.SimpleNamespace(write_audit_entry=lambda *a, **k: None),
)
sys.modules.setdefault(
    "tooling_manifest",
    types.SimpleNamespace(
        build_tooling_manifest=lambda: {},
        workflow_tool_catalog=lambda: [],
    ),
)
sys.modules.setdefault(
    "memory_manager",
    types.SimpleNamespace(
        coerce_memory_summary=lambda x: x,
        normalize_memory_type=lambda x: x,
    ),
)

import mcp_handlers  # noqa: E402 (must come after stubs)


# ---------------------------------------------------------------------------
# _normalize_qa_phase
# ---------------------------------------------------------------------------
class TestNormalizeQaPhase:
    def test_numeric_string_passthrough(self):
        assert mcp_handlers._normalize_qa_phase("0") == "0"
        assert mcp_handlers._normalize_qa_phase("1") == "1"
        assert mcp_handlers._normalize_qa_phase("3") == "3"

    def test_phase_prefix_stripped(self):
        assert mcp_handlers._normalize_qa_phase("phase0") == "0"
        assert mcp_handlers._normalize_qa_phase("phase1") == "1"
        assert mcp_handlers._normalize_qa_phase("phase3") == "3"

    def test_all_alias_resolves(self):
        assert mcp_handlers._normalize_qa_phase("all") == "all"

    def test_none_defaults_to_zero(self):
        assert mcp_handlers._normalize_qa_phase(None) == "0"

    def test_empty_string_defaults_to_zero(self):
        assert mcp_handlers._normalize_qa_phase("") == "0"

    def test_whitespace_stripped(self):
        assert mcp_handlers._normalize_qa_phase("  0  ") == "0"

    def test_integer_input(self):
        assert mcp_handlers._normalize_qa_phase(0) == "0"
        assert mcp_handlers._normalize_qa_phase(1) == "1"

    def test_unknown_phase_passed_through(self):
        # Unknown phases are passed through (validation happens in run_qa_check_as_dict)
        result = mcp_handlers._normalize_qa_phase("99")
        assert result == "99"


# ---------------------------------------------------------------------------
# _build_qa_exec_env
# ---------------------------------------------------------------------------
class TestBuildQaExecEnv:
    def test_returns_dict(self):
        env = mcp_handlers._build_qa_exec_env()
        assert isinstance(env, dict)

    def test_path_is_set(self):
        env = mcp_handlers._build_qa_exec_env()
        assert "PATH" in env
        assert len(env["PATH"]) > 0

    def test_pythonunbuffered_set(self):
        env = mcp_handlers._build_qa_exec_env()
        assert env.get("PYTHONUNBUFFERED") == "1"

    def test_home_is_set(self):
        env = mcp_handlers._build_qa_exec_env()
        assert "HOME" in env
        assert len(env["HOME"]) > 0

    def test_bash_key_in_env(self):
        env = mcp_handlers._build_qa_exec_env()
        assert "BASH" in env

    def test_python3_key_in_env(self):
        env = mcp_handlers._build_qa_exec_env()
        assert "PYTHON3" in env

    def test_path_includes_npm_global(self):
        env = mcp_handlers._build_qa_exec_env()
        path = env["PATH"]
        assert ".npm-global" in path

    def test_path_includes_nix_profile(self):
        env = mcp_handlers._build_qa_exec_env()
        path = env["PATH"]
        assert ".nix-profile" in path


# ---------------------------------------------------------------------------
# _resolve_bash_binary
# ---------------------------------------------------------------------------
class TestResolveBashBinary:
    def test_returns_string(self):
        result = mcp_handlers._resolve_bash_binary()
        assert isinstance(result, str)

    def test_path_exists(self):
        result = mcp_handlers._resolve_bash_binary()
        assert Path(result).exists(), f"bash binary not found at {result}"

    def test_env_override_respected(self):
        original = os.environ.get("BASH")
        try:
            import shutil
            bash_path = shutil.which("bash")
            if bash_path:
                os.environ["BASH"] = bash_path
                result = mcp_handlers._resolve_bash_binary()
                assert result == bash_path
        finally:
            if original is None:
                os.environ.pop("BASH", None)
            else:
                os.environ["BASH"] = original


# ---------------------------------------------------------------------------
# _resolve_python3_binary
# ---------------------------------------------------------------------------
class TestResolvePython3Binary:
    def test_returns_string(self):
        result = mcp_handlers._resolve_python3_binary()
        assert isinstance(result, str)

    def test_path_exists(self):
        result = mcp_handlers._resolve_python3_binary()
        assert Path(result).exists(), f"python3 binary not found at {result}"


# ---------------------------------------------------------------------------
# run_qa_check_as_dict validation (no subprocess)
# ---------------------------------------------------------------------------
class TestRunQaCheckAsDict:
    def test_invalid_format_raises(self):
        with pytest.raises(ValueError, match="format"):
            asyncio.run(
                mcp_handlers.run_qa_check_as_dict({"phase": "0", "format": "xml"})
            )

    def test_invalid_phase_raises(self):
        with pytest.raises(ValueError, match="phase"):
            asyncio.run(
                mcp_handlers.run_qa_check_as_dict({"phase": "99", "format": "json"})
            )

    def test_capability_only_invalid_phase_raises(self):
        with pytest.raises(ValueError, match="capability_only"):
            asyncio.run(
                mcp_handlers.run_qa_check_as_dict(
                    {"phase": "1", "format": "json", "capability_only": True}
                )
            )

    def test_missing_script_raises(self, tmp_path, monkeypatch):
        monkeypatch.setattr(mcp_handlers, "_AQ_QA_SCRIPT", tmp_path / "nonexistent-aq-qa")
        with pytest.raises(FileNotFoundError):
            asyncio.run(
                mcp_handlers.run_qa_check_as_dict({"phase": "0", "format": "json"})
            )


# ---------------------------------------------------------------------------
# QA_PHASE_ALIASES completeness
# ---------------------------------------------------------------------------
class TestQaPhaseAliases:
    def test_expected_aliases_present(self):
        aliases = mcp_handlers._QA_PHASE_ALIASES
        assert aliases.get("phase0") == "0"
        assert aliases.get("phase1") == "1"
        assert aliases.get("phase2") == "2"
        assert aliases.get("phase3") == "3"
        assert aliases.get("all") == "all"

    def test_all_valid_phases_normalizable(self):
        for phase in ("0", "1", "2", "3", "all"):
            result = mcp_handlers._normalize_qa_phase(phase)
            assert result == phase
