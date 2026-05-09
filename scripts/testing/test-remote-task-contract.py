#!/usr/bin/env python3
"""Regression checks for remote task contract helpers and persistence."""

from __future__ import annotations

import importlib
import os
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
HYBRID_DIR = ROOT / "ai-stack" / "mcp-servers" / "hybrid-coordinator"
MCP_ROOT = ROOT / "ai-stack" / "mcp-servers"
HARNESS_SDK_JS = HYBRID_DIR / "harness_sdk.js"
HARNESS_RPC = ROOT / "scripts" / "ai" / "harness-rpc.js"
SESSION_BUILDERS = HYBRID_DIR / "core" / "session_builders.py"
SCHEMA_PATH = ROOT / "config" / "schemas" / "harness" / "remote-task-contract.schema.json"


def assert_true(condition: bool, message: str) -> None:
    if not condition:
        raise AssertionError(message)


def main() -> int:
    sys.path.insert(0, str(HYBRID_DIR))
    sys.path.insert(0, str(MCP_ROOT))
    os.environ["AI_STRICT_ENV"] = "false"

    sdk = importlib.import_module("extensions.harness_sdk")
    client = sdk.HarnessClient()
    task_contract = client.default_remote_task_contract(
        "summarize remote routing tradeoffs",
        constraints=["stay bounded", "capture evidence"],
        expected_output="compact decision memo",
        timeout_seconds=120,
        validation=["aq-qa 0", "tier0 gate"],
        depth_expectation="deep",
    )
    assert_true(task_contract["objective"] == "summarize remote routing tradeoffs", "remote task contract should preserve objective")
    assert_true(task_contract["timeout_seconds"] == 120, "remote task contract should preserve timeout")
    intent = client.intent_contract_from_remote_task_contract(task_contract)
    assert_true(intent["user_intent"] == task_contract["objective"], "intent contract should derive user_intent from objective")
    assert_true(intent["definition_of_done"] == "compact decision memo", "intent contract should derive definition_of_done from expected_output")
    assert_true(intent["no_early_exit_without"] == ["aq-qa 0", "tier0 gate"], "intent contract should derive validation guardrails")

    schema_text = SCHEMA_PATH.read_text(encoding="utf-8")
    assert_true('"timeout_seconds"' in schema_text and '"expected_output"' in schema_text, "remote task contract schema should define core fields")

    js_text = HARNESS_SDK_JS.read_text(encoding="utf-8")
    assert_true("defaultRemoteTaskContract(" in js_text, "harness_sdk.js should expose remote task contract helper")
    assert_true("intentContractFromRemoteTaskContract(" in js_text, "harness_sdk.js should map remote task contract into intent contract")

    rpc_text = HARNESS_RPC.read_text(encoding="utf-8")
    assert_true('args["remote-task-contract"]' in rpc_text, "harness-rpc should accept JSON remote task contract input")
    assert_true('args["task-output"]' in rpc_text and 'args["task-validation"]' in rpc_text, "harness-rpc should accept explicit contract fields")

    session_builders_text = SESSION_BUILDERS.read_text(encoding="utf-8")
    assert_true('"remote_task_contract": remote_task_contract' in session_builders_text, "workflow run sessions should persist remote task contracts")

    print("PASS: remote task contract helpers and persistence validated")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
