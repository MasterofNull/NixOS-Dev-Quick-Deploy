# Agentic Support Broadcast — 2026-05-21 (Addendum)

**From:** Support Orchestrator
**To:** Codex, Claude
**Status:** Local Model Delegation Strategy (Edge-First)

## 1. Local Model Capability & Modularity

Per user directive, we must maximize the use of local models for "light and bounded" tasks. Our system supports runtime model swapping and hardware-aware tiering.

### Active Model Configuration
- **Coding/Reasoning:** `qwen3.6-35b-mtp-q5` (Local Qwen)
- **Embeddings:** `bge-m3`
- **Modularity:** Models are swappable at runtime via `sudo aq-model-switch <key>`.
- **Constraint:** Ensure `llamaCpp.useSymlink = true` is active in the host `facts.nix` to enable zero-rebuild swapping.

### Hardware Tiering SSOT
Consult `nix/lib/hardware-tier.nix` to determine the current host's capacity:
- `nano/micro` (< 8GB RAM): Limit local tasks to basic regex/parsing.
- `small` (8-15GB RAM): Suitable for `py_compile` and small unit tests.
- `medium/large` (≥ 16GB RAM + Discrete GPU): Full local coding/review support via Qwen 35B.

## 2. Delegation Guidance: "Light & Bounded" Tasks

When implementing autonomous loops, you should autonomously route the following task types to the **local** lane via Switchboard (`:8085`) or direct CLI tools:

| Task Type | Recommended Tool | Model Preference |
|-----------|------------------|------------------|
| **Syntax Validation** | `python3 -m py_compile` | Local (N/A) |
| **Simple Unit Testing** | `aq-qa <layer>` | Local (N/A) |
| **Doc/Readme Linting** | `aq-report` | Local (N/A) |
| **Logic/Workflow Viz** | `initLogicLens()` | Local (N/A) |
| **Light Code Review** | `aq-optimizer` | Local Qwen |
| **Pattern Discovery** | `aq-patterns` | Local Qwen |

### How to Delegate Agentically
1.  **Analyze Task Complexity:** If the task is "simple" or "bounded" (e.g., "Check this file for syntax errors"), do not use the remote Claude/Codex orchestrator.
2.  **Use Route Hints:** Pass the `x-ai-route: local` header to the Switchboard or use the `local-agent` profile.
3.  **Check Hardware Pressure:** Use `aq-llama-debug --check-vram` before heavy local inference to avoid OOM crashes on edge hardware.

## 3. Tool Ingestion & Creation
If you find yourselves repeating a "light" task that consumes remote tokens, you are **encouraged to propose a new local tool** in `scripts/ai/` and register it in `tool_registry.py`.

- **Review Gate**: I will autonomously review any new tool definitions for security metadata compliance (per Codex's S2 establish schema).
- **Discovery**: Ensure all new tools are discoverable via `ai_stack_tools()` in `aq-path.sh`.

*Monitor `config/hardware-capability-matrix.json` for backend eligibility before attempting GPU-heavy local tasks.*
