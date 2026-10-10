---
doc_type: reference
title: "Wiki: Local Agent"
subsystem: local-agent
generated: 2026-10-10T08:04:22.503894Z
graph_generated: 2026-10-10T07:31:33Z
graph_nodes: 498
---

# Local Agent

> Local Qwen3-35B agent runtime, outer loop, grounding, task state management

*Auto-generated from `knowledge-graph.json`. Do not edit manually.*
*Refresh: `aq-wiki --update`  ·  Full regeneration: `aq-wiki --init --force`*

## Key Files

| File | Summary | Complexity |
|------|---------|------------|
| `agent_executor.py` | Local Agent Executor - Workflow Integration | complex |
| `agent_spawner.py` | Agent Spawner — Multi-Agent Team Orchestration | complex |
| `ai_coordination.py` | Built-in AI Coordination Tools for Local Agents | complex |
| `computer_use.py` | Built-in Computer Use Tools for Local Agents | complex |
| `file_operations.py` | Built-in File Operation Tools for Local Agents | complex |
| `tool_registry.py` | Tool Registry and Calling Infrastructure for Local Agents | complex |
| `training_ingest.py` | training_ingest.py — Telemetry → fine-tuning dataset pipeline. | complex |
| `__init__.py` | Local Agent Tool Calling Infrastructure | moderate |
| `code_execution.py` | Code Execution Tools | moderate |
| `git_tools.py` | Built-in Git Tools for Local Agents | moderate |
| `github_tools.py` | GitHub tools for local agents — thin wrappers over the `gh` CLI. | moderate |
| `shell_tools.py` | Built-in Shell Command Tools for Local Agents | moderate |
| `testing_tools.py` | Testing tools for local agents — pytest wrappers with structured output. | moderate |
| `code_executor.py` | Code Execution Sandbox | moderate |
| `collective_memory.py` | Collective Memory — Phase 18: Agent Mesh | moderate |
| `context_assembler.py` | Local Context Supply Chain — Slice 0.1: the assembler. | moderate |
| `context_cache.py` | Embed-backed semantic context cache — Slice 2a library. | moderate |
| `cross_model_critique.py` | Cross-Model Critique — Phase 157 | moderate |
| `decompose_loop.py` | decompose_loop.py — DECOMPOSE-CONDENSE loop for over-budget local-model tasks. | moderate |
| `discovery_agent.py` | Discovery Agent - Proactive System & Codebase Analysis | moderate |
| `experience_replay.py` | Experience Replay — Phase 18: Agent Mesh | moderate |
| `harness_paths.py` | Harness Paths — Single Source of Truth for Agentic Data Paths | moderate |
| `llm_cassette.py` | LLM record/replay cassette — deterministic, instant replay of local-agent inference. | moderate |
| `loop_state.py` | loop_state.py — Durable loop state management for aq-loop. | moderate |
| `monitoring_agent.py` | Monitoring Agent - Autonomous System Health Management | moderate |

## Key Functions

| Function | File | Summary |
|----------|------|---------|
| `LocalAgentExecutor._call_llama` | `agent_executor.py` | Call local llama.cpp server using SSE streaming. |
| `LocalAgentExecutor._execute_with_tools` | `agent_executor.py` | Execute task with tool use loop. |
| `LocalAgentExecutor._get_system_prompt` | `agent_executor.py` | Get system prompt for agent type with tool descriptions. |
| `LocalAgentExecutor.execute_task` | `agent_executor.py` | Execute a task using local agent with tool use. |
| `_verify_edit_quality` | `agent_executor.py` | Cheap static checks on ONE edit's diff — no LLM, no test run. |
| `discover_objectives_handler` | `ai_coordination.py` | Research the codebase and propose ranked objectives for user approval. |
| `register_ai_coordination_tools` | `ai_coordination.py` | Register all AI coordination tools in the registry |
| `register_code_execution_tools` | `code_execution.py` | Register code execution tools with registry. |
| `register_computer_use_tools` | `computer_use.py` | Register all computer use tools in the registry |
| `register_file_tools` | `file_operations.py` | Register all file operation tools in the registry |
| `write_region_handler` | `file_operations.py` | Replace lines [start_line, end_line] (1-indexed, inclusive) of file_path with new_text. |
| `run_command_handler` | `shell_tools.py` | Execute a safe shell command. |
| `CodeExecutor.execute` | `code_executor.py` | Execute code in sandbox. |
| `assemble_context` | `context_assembler.py` | Front-load prior knowledge for a local task — two tiered retrieval |
| `ToolRegistry.execute_tool_call` | `tool_registry.py` | Execute a tool call with safety checks and audit logging. |
| `generate_prompt_extensions` | `training_ingest.py` | Convert accumulated training signals into a model-agnostic YAML prompt |
| `initialize_builtin_tools` | `__init__.py` | Initialize tool registry with all built-in tools. |
| `LocalAgentExecutor.__init__` | `agent_executor.py` | __init__(self, llama_endpoint: str=os.environ.get('LLAMA_CPP_URL', os.environ.get('LLAMA_U |
| `LocalAgentExecutor._fallback_to_remote` | `agent_executor.py` | Fallback to remote agent (hybrid coordinator). |
| `LocalAgentExecutor._prm_steer_alternative` | `agent_executor.py` | FE-1: after a behavioral-verify failure, request ONE alternative edit, |

## Classes

| Class | File | Summary |
|-------|------|---------|
| `LocalAgentExecutor` | `agent_executor.py` | Executes tasks using local llama.cpp agents with tool use. |
| `CodeExecutor` | `code_executor.py` | Safe code execution sandbox. |
| `DiscoveryAgent` | `discovery_agent.py` | Proactively discovers improvement opportunities by scanning issue backlog, health spider J |
| `MonitoringAgent` | `monitoring_agent.py` | Autonomous monitoring agent that checks system health and triggers remediation. |
| `SelfImprovementEngine` | `self_improvement.py` | Continuous improvement engine for local agents. |
| `ToolRegistry` | `tool_registry.py` | Central registry for tools available to local agents. |
| `TrainingIngestor` | `training_ingest.py` | Reads production telemetry and extracts training samples for the local model. |
| `AgentPerformance` | `agent_executor.py` | Performance tracking for an agent |
| `Task` | `agent_executor.py` | Task for agent execution |
| `AgentState` | `agent_spawner.py` | Manages agent instance state persisted to disk |
| `CandidateLifecycleManager` | `candidate_lifecycle.py` | class CandidateLifecycleManager() |
| `SecurityScanner` | `code_executor.py` | Security scanner for code validation. |
| `CollectiveMemory` | `collective_memory.py` | Shared state for multi-agent teams. |
| `EvalSandboxExecutor` | `eval_sandbox.py` | Static, deterministic candidate evaluator. |
| `ExperienceReplay` | `experience_replay.py` | Retrieves semantically relevant past collaboration records from AIDB. |

## Related Documentation

- `.agent/LOCAL-AGENT.md`
- `docs/architecture/local-agent-agentic-capabilities.md`

## Coverage

- **Nodes**: 498 total (34 files, 415 functions, 49 classes)
- **Path prefix**: `ai-stack/local-agents/`
- **Graph**: `.understand-anything/knowledge-graph.json`  (generated 2026-10-10T07:31:33Z)
