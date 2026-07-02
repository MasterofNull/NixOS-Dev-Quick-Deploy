---
doc_type: reference
title: "Wiki: Local Agent"
subsystem: local-agent
generated: 2026-07-02T01:49:23.498923Z
graph_generated: 2026-07-01T16:10:40Z
graph_nodes: 71
---

# Local Agent

> Local Qwen3-35B agent runtime, outer loop, grounding, task state management

*Auto-generated from `knowledge-graph.json`. Do not edit manually.*  
*Refresh: `aq-wiki --update`  ·  Full regeneration: `aq-wiki --init --force`*

## Key Files

| File | Summary | Complexity |
|------|---------|------------|
| `code_executor.py` | Sandboxed multi-language code executor (563 lines). Defines Language and SecurityLevel enu | complex |
| `discovery_agent.py` | Opportunity discovery agent (393 lines). Scans issue backlog, health spider events, delega | complex |
| `monitoring_agent.py` | System health monitoring agent (589 lines). Checks llama.cpp, hybrid-coordinator, AIDB ser | complex |
| `self_improvement.py` | Self-improvement engine (572 lines). Scores task execution quality across multiple dimensi | complex |
| `git_tools.py` | git_tools.py (385 lines) in builtin_tools. | complex |
| `cross_model_critique.py` | cross_model_critique.py (244 lines) in local-agents. | complex |
| `agent_executor.py` | Core agent execution engine (2059 lines). Defines Task, AgentType, AgentPerformance data m | moderate |
| `ai_coordination.py` | AI coordination tool handlers (1570 lines). Provides 24 handler functions registered with  | moderate |
| `code_execution.py` | Code execution tool handlers. Wraps CodeExecutor to expose run_python, run_bash, run_javas | moderate |
| `computer_use.py` | Computer use tool handlers for GUI automation. Registers screenshot, mouse_move, mouse_cli | moderate |
| `file_operations.py` | File operation tool handlers. Registers read_file, write_file, list_files, search_files, f | moderate |
| `github_tools.py` | GitHub integration tool handlers. Wraps gh CLI to provide search_code, list_issues, create | moderate |
| `shell_tools.py` | Shell tool handlers. Provides run_command (with optional nsjail sandbox via NsjailSandbox) | moderate |
| `testing_tools.py` | Testing tool handlers. Provides run_tests (via pytest) and check_test_coverage as agent to | moderate |
| `collective_memory.py` | Collective memory abstraction backed by Redis (blackboard pattern) and AIDB. Provides Coll | moderate |
| `tool_registry.py` | Central tool registry (816 lines). Defines ToolDefinition (with JSON schema generation), T | moderate |
| `agent_spawner.py` | agent_spawner.py (718 lines) in local-agents. | moderate |
| `candidate_lifecycle.py` | candidate_lifecycle.py (145 lines) in local-agents. | moderate |
| `eval_sandbox.py` | eval_sandbox.py (134 lines) in local-agents. | moderate |
| `experience_replay.py` | experience_replay.py (155 lines) in local-agents. | moderate |
| `harness_paths.py` | harness_paths.py (189 lines) in local-agents. | moderate |
| `training_ingest.py` | training_ingest.py (657 lines) in local-agents. | moderate |
| `trust_scoring.py` | trust_scoring.py (117 lines) in local-agents. | moderate |
| `__init__.py` | Package initializer for the local-agents module. Imports and wires all builtin tool catego | simple |
| `remediator_agent.py` | Thin remediation agent stub (26 lines). Wraps LocalAgentExecutor to execute remediation ta | simple |

## Key Functions

| Function | File | Summary |
|----------|------|---------|
| `delegate_to_remote_handler` | `ai_coordination.py` | Tool handler that delegates tasks to remote agents (Gemini/Codex) via delegate-to-antigrav |
| `_refresh_active_tools` | `agent_executor.py` | Dynamically refreshes the active tool set mid-execution based on tool result content. Enab |
| `register_ai_coordination_tools` | `ai_coordination.py` | Registers all 24 AI coordination tool handlers (delegate_to_remote, store_memory, query_co |
| `store_memory_handler` | `ai_coordination.py` | Tool handler for persisting agent memories to AIDB (Qdrant) with normalized collection rou |
| `query_context_handler` | `ai_coordination.py` | Tool handler for RAG-style context retrieval from AIDB/Qdrant collections via hybrid-coord |
| `get_unified_stack_health_handler` | `ai_coordination.py` | Tool handler returning a unified health status snapshot for llama.cpp, AIDB, hybrid-coordi |
| `run_python_impl` | `code_execution.py` | Executes Python code via CodeExecutor with sandbox and resource limits. Returns ExecutionR |
| `run_bash_impl` | `code_execution.py` | Executes Bash commands via CodeExecutor with configurable security level. |
| `screenshot_handler` | `computer_use.py` | Captures desktop screenshot using pyautogui or X11 fallback, returns base64-encoded PNG. |
| `read_file_handler` | `file_operations.py` | Reads file contents with path validation, optional line range, and size limits. Enforces s |
| `write_file_handler` | `file_operations.py` | Writes content to file with path validation, directory creation, and sandbox enforcement. |
| `run_command_handler` | `shell_tools.py` | Executes shell commands with optional nsjail sandbox, timeout, and output truncation. Retu |
| `_run_pytest` | `testing_tools.py` | Runs pytest with JSON output plugin and parses results into structured pass/fail/error sum |
| `initialize_builtin_tools` | `__init__.py` | Entry point that registers all builtin tool categories into the ToolRegistry. Called at pa |
| `get_executor` | `agent_executor.py` | Module-level singleton factory for LocalAgentExecutor. Returns cached instance or creates  |
| `register_code_execution_tools` | `code_execution.py` | Registers run_python, run_bash, run_javascript, and validate_code tools with ToolRegistry. |
| `register_computer_use_tools` | `computer_use.py` | Registers screenshot, mouse_move, mouse_click, keyboard_type, keyboard_press, and get_scre |
| `register_file_tools` | `file_operations.py` | Registers read_file, write_file, list_files, search_files, file_exists, and edit_file tool |
| `register_github_tools` | `github_tools.py` | Registers github_search_code, github_list_issues, github_create_pr, github_get_file, and g |
| `register_shell_tools` | `shell_tools.py` | Registers run_command, get_system_info, and check_service tools with ToolRegistry. |

## Classes

| Class | File | Summary |
|-------|------|---------|
| `CodeExecutor` | `code_executor.py` | Multi-language code executor with resource limits and sandbox environment. Creates isolate |
| `DiscoveryAgent` | `discovery_agent.py` | Proactively discovers improvement opportunities by scanning issue backlog, health spider J |
| `MonitoringAgent` | `monitoring_agent.py` | Continuous monitoring agent that checks llama.cpp, hybrid-coordinator, AIDB, memory, disk, |
| `SelfImprovementEngine` | `self_improvement.py` | Engine that scores task executions across QualityDimensions, stores results in SQLite, col |
| `Task` | `agent_executor.py` | Dataclass representing a task unit. Holds objective, context, complexity, quality requirem |
| `AgentPerformance` | `agent_executor.py` | Tracks per-agent performance metrics: task counts, success/failure/fallback rates, executi |
| `LocalAgentExecutor` | `agent_executor.py` | Central execution orchestrator for local agent tasks (1622 lines). Manages llama.cpp HTTP  |
| `NsjailSandbox` | `shell_tools.py` | Builds nsjail argv for sandboxed shell command execution. Configures network isolation, fi |
| `SecurityScanner` | `code_executor.py` | Pattern-based static code scanner. Compiles regex patterns for dangerous operations (subpr |
| `CollectiveMemory` | `collective_memory.py` | Multi-agent shared memory via Redis blackboard pattern. Supports blackboard_set/get/getall |
| `QualityScore` | `self_improvement.py` | Dataclass holding per-dimension quality scores with weighted overall score calculation and |
| `ToolDefinition` | `tool_registry.py` | Dataclass describing a registered tool: name, description, parameters schema, handler, cat |
| `ToolRegistry` | `tool_registry.py` | Central registry for all agent tools. Manages registration/unregistration, SQLite-backed a |
| `AgentType` | `agent_executor.py` | Enum defining agent backend types: LOCAL, REMOTE, HYBRID. Used for routing decisions in Lo |
| `TaskStatus` | `agent_executor.py` | Enum defining task lifecycle states: PENDING, RUNNING, COMPLETED, FAILED, DEGRADED. |

## Related Documentation

- `.agent/LOCAL-AGENT.md`
- `docs/architecture/local-agent-agentic-capabilities.md`

## Coverage

- **Nodes**: 71 total (25 files, 22 functions, 24 classes)
- **Path prefix**: `ai-stack/local-agents/`
- **Graph**: `.understand-anything/knowledge-graph.json`  (generated 2026-07-01T16:10:40Z)
