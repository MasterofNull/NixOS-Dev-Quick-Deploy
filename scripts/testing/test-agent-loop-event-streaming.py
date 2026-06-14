#!/usr/bin/env python3
"""Static contract checks for Phase E agent loop event streaming."""

from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
AGENT_EXECUTOR = ROOT / "ai-stack" / "local-agents" / "agent_executor.py"
AQ_AGENT_LOOP = ROOT / "scripts" / "ai" / "aq-agent-loop"
MCP_SERVERS_NIX = ROOT / "nix" / "modules" / "services" / "mcp-servers.nix"


def require(text: str, needle: str, message: str) -> None:
    if needle not in text:
        raise AssertionError(message)


def main() -> int:
    executor = AGENT_EXECUTOR.read_text(encoding="utf-8")
    loop = AQ_AGENT_LOOP.read_text(encoding="utf-8")
    nix = MCP_SERVERS_NIX.read_text(encoding="utf-8")

    require(executor, "from harness_paths import AGENT_RUN_EVENTS", "agent_executor must use harness_paths.AGENT_RUN_EVENTS")
    require(loop, "from harness_paths import AGENT_RUN_EVENTS", "aq-agent-loop must use harness_paths.AGENT_RUN_EVENTS")

    for event_type in (
        "agent_step_start",
        "agent_tool_intent",
        "agent_tool_result",
        "agent_synthesis_start",
        "agent_complete",
        "agent_failed",
        "agent_stall",
    ):
        require(executor, event_type, f"agent_executor missing {event_type}")

    for event_type in ("agent_step_start", "agent_complete", "agent_failed"):
        require(loop, event_type, f"aq-agent-loop missing {event_type}")

    require(executor, "asyncio.create_task(self._async_append_jsonl(path, event))", "executor events must be fire-and-forget")
    require(loop, "asyncio.create_task(_async_append_jsonl(path, event))", "aq-agent-loop events must be fire-and-forget")
    require(executor, "asyncio.get_running_loop()", "stall watchdog must use running loop")
    require(executor, ".call_later(STALL_TIMEOUT, _fire_stall)", "stall watchdog must use loop.call_later")
    require(executor, 'os.environ.get("STALL_TIMEOUT_OVERRIDE", "300")', "stall watchdog must support STALL_TIMEOUT_OVERRIDE")
    require(executor, '_watchdog_last_activity[0] = time.time()', "event emission must reset watchdog activity")
    require(executor, '"advisory": True', "agent_stall must be advisory")
    require(executor, "_agent_event_seq.pop(task.id, None)", "terminal events must clean per-task sequence state")
    require(executor, '"run_attempt"', "terminal events must include run_attempt")

    require(nix, "agent-run-events.jsonl 0664 ${hybridUser} ${aiGroup}", "tmpfiles rules must create/relabel agent-run-events.jsonl")
    require(nix, "f ${dataDir}/hybrid/telemetry/agent-run-events.jsonl", "tmpfiles f rule missing")
    require(nix, "z ${dataDir}/hybrid/telemetry/agent-run-events.jsonl", "tmpfiles z rule missing")

    print("agent loop event streaming contract OK")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
