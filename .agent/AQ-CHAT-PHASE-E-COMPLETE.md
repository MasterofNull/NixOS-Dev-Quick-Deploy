# AQ Chat Phase E Complete

Status: COMPLETE
Code commit: `511d78e2`
Updated: 2026-06-14T06:07:19Z

## Scope

Phase E of the locked aq-chat Unified Routing plan is implemented.

## Event Coverage

`ai-stack/local-agents/agent_executor.py` now emits these agent-run events to `harness_paths.AGENT_RUN_EVENTS`:

- `agent_step_start`
- `agent_tool_intent`
- `agent_tool_result`
- `agent_synthesis_start`
- `agent_complete`
- `agent_failed`
- `agent_stall`

Terminal events include `run_attempt` and clean `_agent_event_seq` with `_agent_event_seq.pop(task.id, None)`.

`scripts/ai/aq-agent-loop` now emits wrapper lifecycle events:

- `agent_step_start`
- `agent_complete`
- `agent_failed`

The wrapper uses a suffixed task id (`<task_id>:aq-agent-loop`) so it does not collide with the executor's per-task sequence stream.

## Stall Watchdog

The executor watchdog uses `asyncio.get_running_loop().call_later(STALL_TIMEOUT, _fire_stall)`.

- Default timeout: 300 seconds
- CI override: `STALL_TIMEOUT_OVERRIDE`
- Watchdog activity reset: `_watchdog_last_activity[0] = time.time()` on every `_emit_agent_event()`
- Stall payload: `{"elapsed_s": ..., "advisory": True}`
- The watchdog is advisory only and is cancelled on all normal loop exits.

## Tmpfiles

Required tmpfiles rules are present in `nix/modules/services/mcp-servers.nix`:

- `f ${dataDir}/hybrid/telemetry/agent-run-events.jsonl 0664 ${hybridUser} ${aiGroup} - -`
- `z ${dataDir}/hybrid/telemetry/agent-run-events.jsonl 0664 ${hybridUser} ${aiGroup} - -`

Activation is pending `nixos-rebuild switch`.

## Validation

- `python3 -m py_compile ai-stack/local-agents/agent_executor.py`: PASS
- `python3 -m py_compile scripts/ai/aq-agent-loop`: PASS
- `python3 scripts/testing/test-agent-loop-event-streaming.py`: PASS
- `aq-qa 0`: 116 passed, 1 failed (`0.8.1` delegate 24h success rate; known xfail class)
- `scripts/governance/tier0-validation-gate.sh --pre-commit`: PASS, 19 passed / 0 failed

## Next

Run `sudo nixos-rebuild switch --flake .#hyperd-ai-dev` to activate B.4 and the Phase E tmpfiles state.
