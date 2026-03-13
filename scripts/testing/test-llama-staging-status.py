#!/usr/bin/env python3
"""Targeted checks for aq-llama-staging-status report generation."""

import hashlib
import importlib.util
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
MODULE_PATH = ROOT / "scripts" / "ai" / "aq-llama-staging-status.py"
SPEC = importlib.util.spec_from_file_location("aq_llama_staging_status", MODULE_PATH)
if SPEC is None or SPEC.loader is None:
    raise SystemExit("ERROR: unable to load aq-llama-staging-status module")
MODULE = importlib.util.module_from_spec(SPEC)
sys.modules[SPEC.name] = MODULE
SPEC.loader.exec_module(MODULE)


def assert_true(condition: bool, message: str) -> None:
    if not condition:
        raise AssertionError(message)


def main() -> int:
    with tempfile.TemporaryDirectory() as tmp_dir:
        tmp_path = Path(tmp_dir)
        iq4 = tmp_path / "Qwen3-4B-Instruct-2507-IQ4_NL.gguf"
        iq4.write_bytes(b"iq4")
        q5_part = tmp_path / "Qwen3-4B-Instruct-2507-Q5_K_M.gguf.part"
        q5_part.write_bytes(b"partial")
        q8 = tmp_path / "Qwen3-8B-Q4_K_M.gguf"
        q8.write_bytes(b"q8")

        report = MODULE.build_report(tmp_path)

    assert_true(report["complete_n"] == 2, "expected two complete candidates")
    first = report["candidates"][0]
    second = report["candidates"][1]
    third = report["candidates"][2]
    assert_true(first["complete"] is True, "expected IQ4 file complete")
    assert_true(first["sha256"] == hashlib.sha256(b"iq4").hexdigest(), "expected IQ4 sha256")
    assert_true("Qwen3-4B-Instruct-2507-IQ4_NL.gguf" in first["registry_line"], "expected registry line")
    assert_true(first["facts_lines"][-1].endswith(f'"{first["sha256"]}";'), "expected filled sha256 facts line")
    assert_true(second["complete"] is False, "expected Q5 incomplete")
    assert_true(second["partial_exists"] is True, "expected Q5 part file detected")
    assert_true(second["registry_line"].endswith("HASH_PENDING"), "expected placeholder for incomplete file")
    assert_true(third["complete"] is True, "expected 8B Q4 file complete")
    assert_true(third["repo"] == "lm-kit/qwen-3-8b-instruct-gguf", "expected pinned 8B instruct repo")
    assert_true(third["sha256"] == hashlib.sha256(b"q8").hexdigest(), "expected 8B sha256")
    print("PASS: aq-llama-staging-status reports staging completion and patch values")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
