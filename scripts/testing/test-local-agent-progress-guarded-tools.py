#!/usr/bin/env python3
"""Guard local-agent tool loops against fixed max-call regressions."""

import importlib.machinery
import importlib.util
import json
import sys
import tempfile
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
AGENT_EXECUTOR = ROOT / "ai-stack" / "local-agents" / "agent_executor.py"
LOCAL_RUNTIME = ROOT / "ai-stack" / "agents" / "runtimes" / "local_agent_runtime.py"
AQ_AGENT_LOOP = ROOT / "scripts" / "ai" / "aq-agent-loop"
AQ_CHAT = ROOT / "scripts" / "ai" / "aq-chat"
COORDINATOR = ROOT / "ai-stack" / "mcp-servers" / "hybrid-coordinator" / "extensions" / "ai_coordinator_handlers.py"
DISPATCH = ROOT / "scripts" / "ai" / "lib" / "dispatch.py"
AGENT_SPAWNER = ROOT / "ai-stack" / "local-agents" / "agent_spawner.py"


def require(condition: bool, message: str) -> None:
    if not condition:
        raise AssertionError(message)


def _load_agent_loop():
    loader = importlib.machinery.SourceFileLoader("aq_agent_loop_progress_test", str(AQ_AGENT_LOOP))
    spec = importlib.util.spec_from_loader("aq_agent_loop_progress_test", loader)
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    loader.exec_module(module)
    return module


def _count_only_receipt() -> dict:
    return {
        "budget_mode": "AQ_LOCAL_DOGFOOD_BUDGET",
        "call_number": 1,
        "task_type_class": "code",
        "system_unicode_chars": 10,
        "non_system_unicode_chars": 20,
        "tools_unicode_chars": 30,
        "grammar_unicode_chars": 40,
        "payload_json_unicode_chars": 100,
        "estimated_tokens": 25,
        "max_tokens": 192,
    }


def test_final_progress_preserves_only_valid_budget_receipt() -> None:
    loop = _load_agent_loop()
    rejected = {
        "task_id": "reject-task", "status": "failed", "success": False,
        "tool_calls": [], "elapsed_seconds": 1.5, "result": None, "error": "budget rejected",
    }
    completed = {
        "task_id": "done-task", "status": "completed", "success": True,
        "tool_calls": [object()], "elapsed_seconds": 2.5, "result": "COMPLETED: ok", "error": None,
    }
    with tempfile.TemporaryDirectory() as tmp:
        progress = Path(tmp) / "progress.json"
        receipt = _count_only_receipt()
        progress.write_text(json.dumps({"payload_budget": receipt, "raw_task": "do not copy"}), encoding="utf-8")
        loop._write_final_progress(progress, rejected)
        rejected_final = json.loads(progress.read_text(encoding="utf-8"))
        require(rejected_final["status"] == "failed" and rejected_final["success"] is False,
                "rejected terminal fields were not authoritative")
        require(rejected_final.get("payload_budget") == receipt, "rejected final write lost budget receipt")
        require("raw_task" not in rejected_final, "raw prior progress field was copied")

        progress.write_text(json.dumps({"payload_budget": receipt, "stale_raw": "never copy"}), encoding="utf-8")
        loop._write_final_progress(progress, completed)
        completed_final = json.loads(progress.read_text(encoding="utf-8"))
        require(completed_final["status"] == "completed" and completed_final["success"] is True,
                "completed terminal fields were not authoritative")
        require(completed_final.get("payload_budget") == receipt, "completed final write lost budget receipt")
        require("stale_raw" not in completed_final, "completed write copied stale raw field")

        progress.write_text("[not-a-dict]", encoding="utf-8")
        loop._write_final_progress(progress, completed)
        malformed_final = json.loads(progress.read_text(encoding="utf-8"))
        require("payload_budget" not in malformed_final, "malformed prior state should be ignored")

        progress.write_text(json.dumps({"payload_budget": {**receipt, "raw_task_type": "secret"}}), encoding="utf-8")
        loop._write_final_progress(progress, completed)
        raw_final = json.loads(progress.read_text(encoding="utf-8"))
        require("payload_budget" not in raw_final, "non-closed receipt must not be copied")

    print("PASS: terminal progress preserves only closed count-only payload budget receipts")


def main() -> int:
    executor = AGENT_EXECUTOR.read_text(encoding="utf-8")
    runtime = LOCAL_RUNTIME.read_text(encoding="utf-8")
    aq_agent_loop = AQ_AGENT_LOOP.read_text(encoding="utf-8")
    aq_chat = AQ_CHAT.read_text(encoding="utf-8")
    coordinator = COORDINATOR.read_text(encoding="utf-8")
    dispatch = DISPATCH.read_text(encoding="utf-8")
    spawner = AGENT_SPAWNER.read_text(encoding="utf-8")

    require("while tool_call_count < max_tool_calls" not in executor, "agent_executor must not hard-cap tool calls")
    require("reached max tool calls" not in executor, "agent_executor must not return max-tool-call incomplete results")
    require("while True:" in executor, "agent_executor tool loop should be progress-guarded")
    require("Stagnation detected:" in executor, "agent_executor must retain runaway progress guard")
    require("_store_prune_checkpoint" in executor, "agent_executor must retain prune checkpoint memory path")
    require("_refresh_active_tools" in executor, "agent_executor must retain hot-swap tool expansion")
    require("llm_streaming" in executor, "agent_executor must heartbeat progress while LLM tokens stream")
    require("AGENT_PROGRESS_FILE" in executor, "agent_executor must update progress sidecar during streaming")

    require("for _round in range(max_rounds)" not in runtime, "local runtime must not hard-cap tool rounds")
    require("while True:" in runtime, "local runtime tool loop should be progress-guarded")
    require("_refresh_tools_from_result" in runtime, "local runtime must retain hot-swap tool expansion")
    require("Stagnation detected:" in runtime, "local runtime must retain runaway progress guard")

    require('"max_tool_calls":' not in aq_chat, "aq-chat must not send max_tool_calls in delegate payload")
    require("local_tool_budget_exhausted" not in aq_chat, "aq-chat must not depend on budget-exhausted response state")
    require("AGENT_MAX_TOOL_ROUNDS" not in coordinator, "coordinator must not inject AGENT_MAX_TOOL_ROUNDS")

    require("default=50" not in dispatch, "delegate dispatch must not default max-calls to 50")
    require("per_call * max_calls" not in dispatch, "delegate dispatch must not convert max-calls into wall-clock cap")
    require("AGENT_WALL_CLOCK_SECS opt-in cap" in dispatch, "delegate dispatch wall-clock cap must be opt-in only")
    require('"max_tool_calls": 0' in spawner, "agent spawner role defaults must use 0/unlimited tool calls")
    require('AGENT_MAX_TOOL_CALLS", "0"' in spawner, "agent spawner env fallback must use 0/unlimited tool calls")

    require("Deprecated compatibility flag; ignored" in aq_agent_loop, "aq-agent-loop --max-calls must be deprecated")
    require("del max_calls" in aq_agent_loop, "aq-agent-loop must ignore legacy max_calls")
    require("max(14400.0, float(timeout_secs) * 8)" in aq_agent_loop, "aq-agent-loop must allow long-horizon local stream silence")
    require(".agents\" / \"telemetry\" / \"hybrid-events.jsonl" in aq_agent_loop, "training signal must use user telemetry spool")
    require("incomplete_result" in aq_agent_loop, "aq-agent-loop summary must expose incomplete_result")
    require("repeated-read stagnation:" in aq_agent_loop, "aq-agent-loop must fail repeated-read stagnation results")
    require("analysis checkpoint stagnation:" in aq_agent_loop, "aq-agent-loop must fail analysis checkpoint stagnation results")
    require('status_label = "failed" if incomplete_result else result_task.status.value' in aq_agent_loop, "aq-agent-loop must write failed status for incomplete results")
    test_final_progress_preserves_only_valid_budget_receipt()

    print("PASS: local-agent tool loops are progress-guarded, not max-call capped")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
