---
doc_type: reference
title: "Wiki: Switchboard"
subsystem: switchboard
generated: 2026-10-10T08:04:22.498988Z
graph_generated: 2026-10-10T07:31:33Z
graph_nodes: 193
---

# Switchboard

> Profile-based model routing, circuit breakers, remote/local delegation

*Auto-generated from `knowledge-graph.json`. Do not edit manually.*
*Refresh: `aq-wiki --update`  ·  Full regeneration: `aq-wiki --init --force`*

## Key Files

| File | Summary | Complexity |
|------|---------|------------|
| `capability_lease_gate.py` | CapabilityLease enforcement gate — Foundation C2 (flag-gated, deny-closed). | complex |
| `execution_cell_runner.py` | Execution Cell Runner — Foundation C, C3b R3 (default-OFF, enforcement-tier). | complex |
| `switchboard.py` | AI Switchboard — OpenAI-compatible LLM routing proxy. | complex |
| `execution_cell_adapter.py` | Execution Cell Adapter — Foundation C, C3b R5 (default-OFF, enforcement-tier). | moderate |
| `execution_cell_validator.py` | Out-of-cell validator — Foundation C, C3b R3 (default-OFF, enforcement-tier). | moderate |

## Key Functions

| Function | File | Summary |
|----------|------|---------|
| `enforce` | `capability_lease_gate.py` | Decide which of `tool_names` are admitted for execution this call. |
| `_confine_run_validate` | `execution_cell_runner.py` | _confine_run_validate(cell: 'ecc.CellReady', command: CommandDescriptor, verified: 'eg.Ver |
| `_execute_local_tool_calling` | `switchboard.py` | _execute_local_tool_calling(payload: dict, run_id: str='unknown-run') -> tuple[dict, int] |
| `proxy` | `switchboard.py` | proxy(path: str, request: Request) |
| `issue_first_party_leases` | `capability_lease_gate.py` | Issue (or return the cached) first-party leases, one per manifest |
| `resolve_current_epoch` | `capability_lease_gate.py` | Resolve the current policy epoch. Returns None iff unresolvable. |
| `classify_cell_required_effect` | `execution_cell_adapter.py` | Design §2/§3 + Q-R5-3. Returns a pure classification |
| `submit_to_cell` | `execution_cell_adapter.py` | The whole guarded pipeline for one already-C2-admitted tool call. |
| `_acquire_listen_socket` | `execution_cell_runner.py` | _acquire_listen_socket(config: RunnerConfig, env: Mapping[str, str]) -> tuple['socket.sock |
| `_handle_connection` | `execution_cell_runner.py` | _handle_connection(conn: 'socket.socket', config: RunnerConfig, semaphore: 'threading.Boun |
| `_supervise` | `execution_cell_runner.py` | Design §6: poll epoch + liveness every `poll_interval_s` (250 ms); |
| `build_config_from_env` | `execution_cell_runner.py` | build_config_from_env(env: Optional[Mapping[str, str]]=None) -> RunnerConfig |
| `derive_command_descriptor` | `execution_cell_runner.py` | Design §5/§9 + Q-R3-4. Maps the grant's classified effect SET (never |
| `process_grant` | `execution_cell_runner.py` | process_grant(raw_grant: Any, config: RunnerConfig) -> Decision |
| `terminate_cgroup_tree` | `execution_cell_runner.py` | Design §6 exact sequence: cgroup-scoped SIGTERM (enumerate |
| `_run_confined_compare` | `execution_cell_validator.py` | Runs `_COMPARE_WORKER_SRC` inside the validator's OWN bwrap sandbox |
| `_call_upstream_with_resilience` | `switchboard.py` | Execute upstream request with retries and circuit breaker. |
| `_classify_routing_intent` | `switchboard.py` | Return 'local' or 'remote' based on routing_rules task_matrix, or None to defer. |
| `_classify_tool_intent` | `switchboard.py` | _classify_tool_intent(messages: list) -> str |
| `_filter_remote_tools_for_working_set` | `switchboard.py` | _filter_remote_tools_for_working_set(payload: dict, profile: str) -> tuple[dict, dict \| N |

## Classes

| Class | File | Summary |
|-------|------|---------|
| `AdapterConfig` | `execution_cell_adapter.py` | class AdapterConfig() |
| `AdapterResult` | `execution_cell_adapter.py` | A terminal, typed outcome. `runner_decision` (when present) is the |
| `CommandDescriptor` | `execution_cell_runner.py` | class CommandDescriptor() |
| `Decision` | `execution_cell_runner.py` | A terminal, typed outcome. `diff` is populated ONLY on GREEN — the |
| `RunnerConfig` | `execution_cell_runner.py` | class RunnerConfig() |
| `SocketStartupError` | `execution_cell_runner.py` | class SocketStartupError(RuntimeError) |
| `ValidationResult` | `execution_cell_validator.py` | Terminal, typed validation verdict. `changed_paths` is populated ONLY |
| `ValidatorConfig` | `execution_cell_validator.py` | The validator's OWN trusted, statically-bound configuration — never |

## Related Documentation

- `docs/agent-guides/46-SWITCHBOARD-PROFILES.md`
- `docs/architecture/routing-profile-inventory.md`

## Coverage

- **Nodes**: 193 total (5 files, 180 functions, 8 classes)
- **Path prefix**: `ai-stack/switchboard/`
- **Graph**: `.understand-anything/knowledge-graph.json`  (generated 2026-10-10T07:31:33Z)
