---
doc_type: reference
title: "Wiki: Agent Runtimes"
subsystem: agent-runtimes
generated: 2026-10-10T08:04:22.511152Z
graph_generated: 2026-10-10T07:31:33Z
graph_nodes: 62
---

# Agent Runtimes

> Agent runtime implementations: slot scheduling, local_agent_runtime

*Auto-generated from `knowledge-graph.json`. Do not edit manually.*
*Refresh: `aq-wiki --update`  ·  Full regeneration: `aq-wiki --init --force`*

## Key Files

| File | Summary | Complexity |
|------|---------|------------|
| `local_agent_runtime.py` | Local agent subprocess runtime. | complex |
| `test_local_agent_runtime.py` | Unit tests for the local agent runtime. | moderate |

## Key Functions

| Function | File | Summary |
|----------|------|---------|
| `_dispatch_tool` | `local_agent_runtime.py` | Execute a harness tool call and return a plaintext result string. |
| `_validate_harness_cli` | `local_agent_runtime.py` | _validate_harness_cli(tool: str, args: list[str]) -> tuple[list[str], float] |
| `run` | `local_agent_runtime.py` | run() -> None |
| `_post_completion_with_fallback` | `local_agent_runtime.py` | _post_completion_with_fallback(client: httpx.AsyncClient, *, payload: dict, headers: dict, |
| `_run_harness_cli` | `local_agent_runtime.py` | _run_harness_cli(tool: str, args: list[str]) -> str |
| `_select_tools_for_task` | `local_agent_runtime.py` | Select 4-6 relevant tool schemas from TOOL_CATALOG for a given task. |
| `_T` | `local_agent_runtime.py` | _T(name: str, desc: str, required_props: dict \| None=None) -> dict |
| `_build_cli_exec_env` | `local_agent_runtime.py` | _build_cli_exec_env() -> dict[str, str] |
| `_build_inference_payload` | `local_agent_runtime.py` | _build_inference_payload(messages: list[dict], selected_tools: list[dict] \| None=None) -> |
| `_compress_tool_output` | `local_agent_runtime.py` | Trim tool output to max_chars, appending a truncation notice if needed. |
| `_payload_for_direct_llama` | `local_agent_runtime.py` | _payload_for_direct_llama(payload: dict) -> dict |
| `_post_agent_event` | `local_agent_runtime.py` | _post_agent_event(client: httpx.AsyncClient, *, event_type: str, sub_type: str, outcome: s |
| `_profile_for_role` | `local_agent_runtime.py` | _profile_for_role(role: str) -> str |
| `_refresh_tools_from_result` | `local_agent_runtime.py` | Hot-swap active tool set based on tool result content. |
| `_resolve_bash_binary` | `local_agent_runtime.py` | _resolve_bash_binary() -> str |
| `_resolve_python3_binary` | `local_agent_runtime.py` | _resolve_python3_binary() -> str |
| `_run_bootstrap_preamble` | `local_agent_runtime.py` | Run aq-context-bootstrap and return a compact preamble, or '' on any failure. |
| `_slim_schema` | `local_agent_runtime.py` | Return a token-minimal copy of an OpenAI function schema for model context. |
| `_streaming_payload` | `local_agent_runtime.py` | _streaming_payload(messages: list[dict]) -> dict |
| `_validate_arg_tokens` | `local_agent_runtime.py` | _validate_arg_tokens(args: list[str]) -> list[str] |

## Classes

| Class | File | Summary |
|-------|------|---------|
| `_FakeAsyncClient` | `test_local_agent_runtime.py` | class _FakeAsyncClient() |
| `_FakeProcess` | `test_local_agent_runtime.py` | class _FakeProcess() |
| `_FakeResponse` | `test_local_agent_runtime.py` | class _FakeResponse() |
| `_FakeStreamContext` | `test_local_agent_runtime.py` | class _FakeStreamContext() |
| `_FakeStreamResponse` | `test_local_agent_runtime.py` | class _FakeStreamResponse() |

## Related Documentation

- `.agent/CODEX.md`
- `docs/architecture/local-agent-task-eligibility.md`

## Coverage

- **Nodes**: 62 total (2 files, 55 functions, 5 classes)
- **Path prefix**: `ai-stack/agents/runtimes/`
- **Graph**: `.understand-anything/knowledge-graph.json`  (generated 2026-10-10T07:31:33Z)
