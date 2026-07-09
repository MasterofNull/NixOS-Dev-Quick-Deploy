#!/usr/bin/env python3
"""Guard local-agent tool loops against fixed max-call regressions."""

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

    print("PASS: local-agent tool loops are progress-guarded, not max-call capped")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
