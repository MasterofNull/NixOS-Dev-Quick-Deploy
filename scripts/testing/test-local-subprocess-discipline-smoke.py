#!/usr/bin/env python3
"""Validate local subprocess exact-output discipline without capability trimming."""

import json
import sys
from pathlib import Path

import httpx


ROOT = Path(__file__).resolve().parents[2]


def test_static_capability_preservation() -> None:
    handler = ROOT / "ai-stack/mcp-servers/hybrid-coordinator/extensions/ai_coordinator_handlers.py"
    text = handler.read_text(encoding="utf-8")
    marker = "if _is_tool_free or _is_exact_output:"
    end_marker = "# Phase 8.9"
    if marker not in text or end_marker not in text:
        print("FAIL: exact-output discipline block markers missing")
        sys.exit(1)
    block = text.split(marker, 1)[1].split(end_marker, 1)[0]
    if "if _is_tool_free:" not in block:
        print("FAIL: tool disabling must be gated by explicit _is_tool_free")
        sys.exit(1)
    tool_free_block = block.split("if _is_tool_free:", 1)[1]
    if 'data["tools_enabled"] = False' not in tool_free_block:
        print("FAIL: explicit tool-free tasks must still disable tools")
        sys.exit(1)
    exact_preamble = block.split("if _is_tool_free:", 1)[0]
    if 'data["tools_enabled"] = False' in exact_preamble or 'data["thinking_mode"] = "off"' in exact_preamble:
        print("FAIL: exact-output tasks must not disable tools/thinking unless explicitly tool-free")
        sys.exit(1)


def test_dashboard_metric_not_faked() -> None:
    dashboard = ROOT / "assets/dashboard.js"
    text = dashboard.read_text(encoding="utf-8")
    if "logic_discipline_rate ?? 100" in text:
        print("FAIL: dashboard must not default missing logic discipline telemetry to 100%")
        sys.exit(1)
    err_pos = text.find("logicRate < 70")
    warn_pos = text.find("logicRate < 90")
    if err_pos < 0 or warn_pos < 0 or err_pos > warn_pos:
        print("FAIL: logic discipline error threshold must be reachable before warning threshold")
        sys.exit(1)


def test_discipline() -> None:
    url = "http://127.0.0.1:8003/control/ai-coordinator/delegate"
    payload = {
        "task": "Return exactly PLANNING_SMOKE_OK",
        "profile": "local-tool-calling",
        "task_id": "phase150-discipline-smoke",
        "max_tokens": 32,
        "temperature": 0.0,
        "auto_memorize": False,
    }

    print(f"Calling {url} with task: {payload['task']}")
    try:
        r = httpx.post(url, json=payload, timeout=90.0)
        print(f"Status Code: {r.status_code}")
        if r.status_code != 200:
            print(f"Error: {r.text}")
            sys.exit(1)

        data = r.json()
        content = data["choices"][0]["message"]["content"].strip()
        print(f"Received Content: '{content}'")

        if content == "PLANNING_SMOKE_OK":
            print("PASS: Exact output achieved.")
        else:
            print(f"FAIL: Content mismatch. Expected 'PLANNING_SMOKE_OK', got '{content}'")
            sys.exit(1)

    except Exception as e:
        print(f"Exception: {e}")
        sys.exit(1)


def test_dashboard_logic_discipline_endpoint() -> None:
    url = "http://127.0.0.1:8889/api/insights/routing/analytics"
    print(f"Calling {url} for logic discipline telemetry")
    try:
        r = httpx.get(url, timeout=20.0)
        print(f"Status Code: {r.status_code}")
        if r.status_code != 200:
            print(f"Error: {r.text}")
            sys.exit(1)
        data = r.json()
        logic = data.get("logic_discipline")
        if not isinstance(logic, dict):
            print("FAIL: routing analytics missing logic_discipline object")
            sys.exit(1)
        required = {"score", "sample_n", "discipline_failures"}
        if not required <= set(logic):
            print(f"FAIL: incomplete logic_discipline payload: {json.dumps(logic, sort_keys=True)}")
            sys.exit(1)
        if data.get("logic_discipline_rate") != logic.get("score"):
            print("FAIL: logic_discipline_rate must mirror logic_discipline.score")
            sys.exit(1)
        print("PASS: Dashboard logic discipline telemetry contract available.")
    except Exception as e:
        print(f"Exception: {e}")
        sys.exit(1)


if __name__ == "__main__":
    test_static_capability_preservation()
    test_dashboard_metric_not_faked()
    test_discipline()
    test_dashboard_logic_discipline_endpoint()
