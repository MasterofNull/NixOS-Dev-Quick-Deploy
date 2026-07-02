---
doc_type: reference
title: "Wiki: Ai Scripts"
subsystem: ai-scripts
generated: 2026-07-02T01:49:23.502996Z
graph_generated: 2026-07-01T16:10:40Z
graph_nodes: 225
---

# Ai Scripts

> Agent CLI scripts: aq-loop, aq-wiki, delegate-to-*, aq-qa, aq-hints, aq-agent-loop

*Auto-generated from `knowledge-graph.json`. Do not edit manually.*  
*Refresh: `aq-wiki --update`  ·  Full regeneration: `aq-wiki --init --force`*

## Key Files

| File | Summary | Complexity |
|------|---------|------------|
| `dispatch.py` | Core AI task dispatch module. Implements multiple runner strategies (DirectRunner, HybridR | complex |
| `task_registry.py` | Persistent file-based task registry with fcntl locking for multi-process safety. Tracks di | complex |
| `adk-discovery-workflow.sh` | adk-discovery-workflow.sh (314 lines) in ai. | complex |
| `autonomous-coordinator-local.sh` | autonomous-coordinator-local.sh (300 lines) in ai. | complex |
| `autonomous-coordinator-simple.sh` | autonomous-coordinator-simple.sh (254 lines) in ai. | complex |
| `autonomous-coordinator.sh` | autonomous-coordinator.sh (207 lines) in ai. | complex |
| `bash-completion.sh` | bash-completion.sh (227 lines) in ai. | complex |
| `cli-enhanced.sh` | cli-enhanced.sh (309 lines) in ai. | complex |
| `optimize-and-validate.sh` | optimize-and-validate.sh (352 lines) in ai. | complex |
| `ralph-orchestrator.sh` | ralph-orchestrator.sh (298 lines) in ai. | complex |
| `test-ux-improvements.sh` | test-ux-improvements.sh (466 lines) in ai. | complex |
| `update-llama-cpp.sh` | update-llama-cpp.sh (237 lines) in ai. | complex |
| `ai-validate-and-commit` | ai-validate-and-commit (205 lines) in ai. | complex |
| `aq` | aq (258 lines) in ai. | complex |
| `aq-agent-loop` | aq-agent-loop (418 lines) in ai. | complex |
| `aq-bitnet-benchmark.py` | aq-bitnet-benchmark.py (370 lines) in ai. | complex |
| `aq-bitnet-feasibility.py` | aq-bitnet-feasibility.py (296 lines) in ai. | complex |
| `aq-cache-warm` | aq-cache-warm (342 lines) in ai. | complex |
| `aq-collaborate` | aq-collaborate (448 lines) in ai. | complex |
| `aq-context-bootstrap` | aq-context-bootstrap (463 lines) in ai. | complex |
| `aq-context-card` | aq-context-card (342 lines) in ai. | complex |
| `aq-delegate` | aq-delegate (348 lines) in ai. | complex |
| `aq-drop-daemon` | aq-drop-daemon (249 lines) in ai. | complex |
| `aq-editor-rescue` | aq-editor-rescue (419 lines) in ai. | complex |
| `aq-federated-learning` | aq-federated-learning (375 lines) in ai. | complex |

## Key Functions

| Function | File | Summary |
|----------|------|---------|
| `_embedded_assist_prefetch` | `dispatch.py` | Prefetches code-assist suggestions from the switchboard before the main dispatch completes |
| `_validate_code_blocks` | `dispatch.py` | Extracts fenced code blocks from LLM output text and lints/type-checks each one (python: p |
| `dispatch_task` | `dispatch.py` | Top-level dispatch orchestrator. Selects runner based on config.mode, optionally prefetche |
| `main` | `dispatch.py` | CLI entry point. Parses arguments, auto-classifies mode/tokens/task-type when not specifie |
| `_emit_training_event` | `dispatch.py` | Emits a JSONL training event record (query, response, token counts, role, timestamp) to th |
| `_build_parser` | `dispatch.py` | Builds the argparse CLI parser with subcommands: dispatch (run a task), list, status, chec |
| `_cmd_watch` | `dispatch.py` | CLI watch command implementation. Tails the output file, displays real-time progress (tok/ |
| `_scale_timeout` | `dispatch.py` | Computes effective request timeout by scaling against max_tokens, capped by an explicit ov |
| `_write_progress` | `dispatch.py` | Atomically writes a JSON progress file (tokens out, elapsed, tok/s, ETA, status) using a t |
| `classify_tokens` | `dispatch.py` | Classifies the token budget tier (small/medium/large/xlarge) from prompt content using key |
| `classify_mode` | `dispatch.py` | Determines the dispatch mode (direct/hybrid/agent/ralph) from prompt keywords. Local-first |
| `classify_task_type` | `dispatch.py` | Classifies prompt into task type category (code/analysis/plan/review/general) using keywor |
| `_load_grounding` | `dispatch.py` | Reads and returns the grounding text from the repo grounding file. Returns empty string if |
| `_prepend_grounding` | `dispatch.py` | Injects grounding text as a system message into the messages list before the first user tu |
| `_augment_prompt_with_grounding` | `dispatch.py` | Appends grounding context to a plain prompt string. Used by AgentRunner which takes a stri |
| `_compute_agent_wall_clock` | `dispatch.py` | Computes wall-clock timeout for AgentRunner subprocess calls, scaling by max_calls and cap |
| `_service_ok` | `dispatch.py` | Health-checks a service URL (HTTP GET) to verify it is reachable before dispatch. Returns  |
| `_detect_code_lang` | `dispatch.py` | Heuristically detects programming language (python/nix/bash) from the first 400 chars of t |
| `wait_for_slot` | `slot_scheduler.py` | Polls the llama.cpp /slots endpoint in a loop until at least one slot reports state=idle.  |
| `normalize_role` | `task_config.py` | Maps role alias strings (e.g. 'impl', 'reviewer') to canonical role names (implementer, re |

## Classes

| Class | File | Summary |
|-------|------|---------|
| `DirectRunner` | `dispatch.py` | Runs a prompt directly against llama.cpp via streaming SSE HTTP. Waits for an inference sl |
| `AgentRunner` | `dispatch.py` | Invokes the aq-agent-loop subprocess for agentic (multi-tool) tasks. Augments the prompt w |
| `TaskRegistry` | `task_registry.py` | File-backed multi-process-safe task registry using fcntl advisory locking. Maintains a JSO |
| `HybridRunner` | `dispatch.py` | Routes the prompt through the hybrid-coordinator HTTP endpoint. Posts a JSON body with rol |
| `RalphRunner` | `dispatch.py` | Sends prompt to the Ralph (RAG/Qdrant-backed) endpoint. Returns the retrieved answer with  |
| `TaskConfig` | `task_config.py` | Frozen dataclass encapsulating all dispatch parameters: mode, role, max_tokens, timeout_se |

## Related Documentation

- `docs/agent-guides/47-AGENT-TOOL-CONTRACT.md`

## Coverage

- **Nodes**: 225 total (189 files, 21 functions, 6 classes)
- **Path prefix**: `scripts/ai/`
- **Graph**: `.understand-anything/knowledge-graph.json`  (generated 2026-07-01T16:10:40Z)
