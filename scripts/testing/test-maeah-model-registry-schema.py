#!/usr/bin/env python3
"""Validate model_registry entries against the MAEAH ModelEntry schema subset."""

from __future__ import annotations

import json
import os
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
os.environ.setdefault("AI_STRICT_ENV", "false")
sys.path.insert(0, str(ROOT / "ai-stack" / "mcp-servers" / "hybrid-coordinator"))

from model_registry import ModelState, _BUILTIN_CATALOG, _default_entry  # noqa: E402

SCHEMA = ROOT / "config" / "schemas" / "maeah" / "model-entry.schema.json"


def assert_true(condition: bool, message: str) -> None:
    if not condition:
        raise AssertionError(message)


def validate_entry(entry: dict, *, label: str, allowed_states: set[str], required: list[str]) -> None:
    for key in required:
        assert_true(key in entry, f"{label}: missing required key {key}")
    assert_true(entry["state"] in allowed_states, f"{label}: invalid state {entry['state']}")
    assert_true(entry["swap_sla_tier"] in {"gpu_fast", "cpu_fallback"}, f"{label}: invalid swap_sla_tier")
    assert_true(isinstance(entry.get("version"), int) and entry["version"] >= 1, f"{label}: invalid version")
    assert_true(str(entry.get("file", "")).endswith(".gguf"), f"{label}: file must end with .gguf")
    assert_true(isinstance(entry.get("audit_log"), list), f"{label}: audit_log must be a list")
    llama_args = entry.get("llama_args") or {}
    assert_true(isinstance(llama_args, dict), f"{label}: llama_args must be an object")
    if "n_gpu_layers" in llama_args:
        assert_true(isinstance(llama_args["n_gpu_layers"], int) and llama_args["n_gpu_layers"] >= 0, f"{label}: invalid n_gpu_layers")
    if "ctx_size" in llama_args:
        assert_true(isinstance(llama_args["ctx_size"], int) and llama_args["ctx_size"] > 0, f"{label}: invalid ctx_size")


def main() -> int:
    schema = json.loads(SCHEMA.read_text(encoding="utf-8"))
    required = list(schema.get("required") or [])
    allowed_states = set(schema["properties"]["state"]["enum"])
    code_states = {state.value for state in ModelState}
    assert_true(code_states == allowed_states, "ModelState enum must match schema state enum exactly")

    for raw in _BUILTIN_CATALOG:
        entry = _default_entry(raw)
        validate_entry(entry, label=str(raw.get("id")), allowed_states=allowed_states, required=required)

    print(f"PASS: {len(_BUILTIN_CATALOG)} built-in model registry entries conform to MAEAH schema subset")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
