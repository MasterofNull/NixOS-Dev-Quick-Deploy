#!/usr/bin/env python3
"""Targeted checks for delegated prompt failure capture and aq-report surfacing."""

from __future__ import annotations

import json
import os
import subprocess
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
os.environ.setdefault("AI_STRICT_ENV", "false")
sys.path.insert(0, str(ROOT / "ai-stack" / "mcp-servers"))
sys.path.insert(0, str(ROOT / "ai-stack" / "mcp-servers" / "hybrid-coordinator"))

from delegation_feedback import classify_delegated_response  # noqa: E402


def assert_true(condition: bool, message: str) -> None:
    if not condition:
        raise AssertionError(message)


def main() -> int:
    classification = classify_delegated_response(
        task="Return strict JSON only with key result and use only existing repo files.",
        messages=[{"role": "user", "content": "Return strict JSON only with key result."}],
        status_code=200,
        body={
            "choices": [
                {
                    "message": {
                        "content": (
                            "Here is a summary. Please inspect docs/not-real.md and scripts/missing.sh.\n"
                            "sudo systemctl status ai-hybrid-coordinator.service"
                        )
                    }
                }
            ]
        },
        profile="remote-free",
        runtime_id="openrouter-free",
        stage="final",
        fallback_applied=False,
    )
    failure_classes = set(classification.get("failure_classes") or [])
    assert_true("json_contract_failed" in failure_classes, "expected json_contract_failed")
    assert_true("invented_repo_paths" in failure_classes, "expected invented_repo_paths")
    salvage = classification.get("salvage") if isinstance(classification.get("salvage"), dict) else {}
    commands = salvage.get("commands") or []
    assert_true(any("systemctl status ai-hybrid-coordinator.service" in item for item in commands), "expected command salvage")

    tool_call_only = classify_delegated_response(
        task="Return TOOL_READY only.",
        messages=[{"role": "user", "content": "Return TOOL_READY only."}],
        status_code=200,
        body={
            "choices": [
                {
                    "message": {
                        "content": None,
                        "tool_calls": [
                            {
                                "type": "function",
                                "id": "call_1",
                                "function": {
                                    "name": "noop_status",
                                    "arguments": "{\"status\":\"TOOL_READY\"}",
                                },
                            }
                        ],
                    }
                }
            ]
        },
        profile="remote-tool-calling",
        runtime_id="openrouter-tool-calling",
        stage="final",
        fallback_applied=False,
    )
    tool_failures = set(tool_call_only.get("failure_classes") or [])
    assert_true("tool_call_without_final_text" in tool_failures, "expected tool_call_without_final_text")
    assert_true("empty_content" not in tool_failures, "tool-call-only output should not be tagged as empty_content")
    tool_salvage = tool_call_only.get("salvage") if isinstance(tool_call_only.get("salvage"), dict) else {}
    tool_calls = tool_salvage.get("tool_calls") or []
    assert_true(any(item.get("name") == "noop_status" for item in tool_calls if isinstance(item, dict)), "expected tool call salvage")

    with tempfile.TemporaryDirectory() as tmpdir:
        tmp = Path(tmpdir)
        delegation_log = tmp / "delegation-feedback.jsonl"
        delegation_log.write_text(
            "\n".join(
                [
                    json.dumps(
                        {
                            "timestamp": "2026-03-13T12:00:00Z",
                            "selected_profile": "remote-free",
                            "failure_stage": "final",
                            "failure_class": "json_contract_failed",
                            "failure_classes": ["json_contract_failed", "invented_repo_paths"],
                            "fallback_applied": False,
                            "task_excerpt": "Return strict JSON for delegated plan",
                            "response_preview": "Here is a summary",
                            "salvage": {"has_useful_data": True, "commands": ["sudo systemctl status ai-hybrid-coordinator.service"]},
                            "improvement_actions": ["tighten prompt contract"],
                        }
                    ),
                    json.dumps(
                        {
                            "timestamp": "2026-03-13T12:05:00Z",
                            "selected_profile": "remote-coding",
                            "failure_stage": "initial",
                            "failure_class": "rate_limited",
                            "failure_classes": ["rate_limited"],
                            "fallback_applied": True,
                            "task_excerpt": "Implement bounded fix",
                            "response_preview": "",
                            "salvage": {"has_useful_data": False},
                            "improvement_actions": ["reduce max_tokens"],
                        }
                    ),
                ]
            )
            + "\n",
            encoding="utf-8",
        )
        env = os.environ.copy()
        env["DELEGATION_FEEDBACK_LOG_PATH"] = str(delegation_log)
        result = subprocess.run(
            [sys.executable, str(ROOT / "scripts" / "ai" / "aq-report"), "--since=7d", "--format=json"],
            capture_output=True,
            text=True,
            check=False,
            env=env,
            timeout=60,
        )
        assert_true(result.returncode == 0, f"aq-report failed: {(result.stderr or '').strip()}")
        payload = json.loads(result.stdout)
        delegated = payload.get("delegated_prompt_failures") if isinstance(payload.get("delegated_prompt_failures"), dict) else {}
        assert_true(int(delegated.get("total_failures", 0) or 0) == 2, "expected delegated failure count")
        top_classes = delegated.get("top_failure_classes") or []
        assert_true(any(name == "json_contract_failed" for name, _count in top_classes), "missing delegated failure class")
        actions = payload.get("structured_actions") or []
        assert_true(any(item.get("action") == "tighten_openrouter_delegation_contract" for item in actions if isinstance(item, dict)), "missing prompt structured action")

    print("PASS: delegation feedback classification and aq-report surfacing work")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
