# PRD & Implementation Plan: SOTA Agentic Workspace (`aq-workspace`)

**Document ID**: `PROJECT-AGENTIC-WORKSPACE-PRD`  
**Author**: Antigravity IDE  
**Status**: APPROVED & IN-FLIGHT  
**Target Delivery**: 2026-09-26  
**Related**: IndyDevDan / Pi Agent / Herdr / AQ-OS Agentic Workspace  

---

## 1. Problem Statement & Vision

Modern agentic engineering requires rapid orchestration, multi-model cooperation (local models + flagships), live tool-call transparency, real-time telemetry, and seamless human-in-the-loop intervention. Currently, interacting with harness agents requires juggling multiple standalone CLI tools (`aq-chat`, `local-orchestrator`, `aq-tui-dashboard`, `aq-loop`, `delegate-to-*`), or relying on external IDEs for agent visualization.

**The Vision**:
Deliver a single-command entrypoint (`aq-workspace`) that transforms any directory into a high-performance, tiled, beautiful, and intuitive agentic command center. The workspace brings all human-to-agent, agent-to-agent (A2A), and agent-to-human touchpoints into a unified terminal workspace with zero IDE dependency.

---

## 2. Core Requirements & Architecture

### 2.1 Single-Command Invocation (`aq-workspace`)
- Works from any working directory (`cd /path/to/project && aq-workspace`).
- Automatically provisions session name (e.g., `aq-<basename>`) in Zellij.
- If Zellij is available and TTY is interactive, launches the SOTA tiled workspace layout.
- If Zellij is unavailable, or `--tui` / `--standalone` is passed, runs the unified Rich single-window TUI.
- Supports CLI management flags:
  - `aq-workspace` — start / attach to active workspace
  - `aq-workspace attach [name]` — attach to existing workspace
  - `aq-workspace list` — list active agentic workspaces
  - `aq-workspace kill [name]` — terminate workspace
  - `aq-workspace --tui` — run full-screen unified Rich TUI directly

### 2.2 Tiled Workspace Layout (Zellij KDL: `config/zellij/aq-agentic-workspace.kdl`)
- **Tab 1: "󰚩 Agentic Workspace"** (Primary Cockpit):
  - **Left Primary (60% width)**: `aq-coordinator-repl` (Interactive REPL, streaming tokens, model switcher, tool cards, subagent dispatch, intervention prompt).
  - **Top-Right (40% width, 55% height)**: `aq-fleet-monitor` (Live sub-agent fleet, streaming worker output, thoughts/Note-to-Self, tool progress).
  - **Bottom-Right (40% width, 45% height)**: `aq-cockpit-monitor` (System telemetry, model VRAM/APU, tok/s, context window %, service health, PULSE ops ticker).
- **Tab 2: "󰓅 Fleet Matrix"**:
  - Full-screen multi-pane grid (`aq-tui-dashboard --matrix`) displaying live streams across all running agents.
- **Tab 3: "󰒋 A2A Mesh & Telemetry"**:
  - Full-screen detailed diagnostics (`aq-tui-dashboard`) + A2A audit log.
- **Tab 4: " Scratch Shell"**:
  - Working shell in current directory with harness CLIs pre-loaded.

### 2.3 Interactive Coordinator REPL (`scripts/ai/aq-coordinator-repl`)
- Built with `prompt_toolkit` and `rich`.
- **Model Switching**: `/route` or `/model` with tab completion:
  - `local` (Local Qwen-35B on llama.cpp :8080)
  - `claude` (Claude Fable / 3.7 via switchboard :8085 / coordinator :8003)
  - `codex` (OpenAI Codex via coordinator :8003)
  - `gemini` (Gemini direct / Antigravity IDE lane)
- **Sub-Agent Dispatch**: `/dispatch <lane> "<task>"`:
  - Spawns background sub-agents, writes to `.agents/delegation/registry.jsonl`, streams thoughts to `.agents/delegation/streams/`, and shows status badges.
- **Human-in-the-Loop Interventions**:
  - `/steer <task_id> "<message>"`: injects guidance into running task.
  - `/pause <task_id>`: pauses task.
  - `/resume <task_id>`: resumes task.
  - `/kill <task_id>`: cancels task.
  - `/approve <task_id>`: grants permission for gated tool calls.
  - `/inspect <task_id>`: inspects live output.
- **Live Tool Cards**:
  - Pretty-printed panels showing tool name, arguments, execution duration, and outcome status badge (✓ PASS, ✗ FAIL, ⏳ RUNNING).

### 2.4 Sub-Agent Fleet Monitor (`scripts/ai/aq-fleet-monitor`)
- Real-time Rich monitor displaying:
  - Active and recent delegations from `.agents/delegation/registry.jsonl`.
  - Live thought stream / Note-to-Self extraction from active stream files.
  - Animated activity indicators.
  - Live progress bars for multi-step agent execution.

### 2.5 System Cockpit Monitor (`scripts/ai/aq-cockpit-monitor`)
- Real-time Rich telemetry displaying:
  - Live health probes for Switchboard (8085), Hybrid Coordinator (8003), Llama.cpp (8080), AIDB (8002), Redis (6379), Qdrant (6333).
  - APU/GPU VRAM, RAM utilization, active model profile, tok/sec throughput.
  - Context window usage gauge (0 - 100%).
  - Recent A2A Safeguards audit events (ALLOW / WARN / BLOCK).
  - Live PULSE ticker (last 4 entries from `PULSE.log`).

### 2.6 Unified Single-Window TUI Mode (`aq-workspace --tui`)
- Rich `Live` + `Layout` full-screen application providing the same 3-pane layout for environments where Zellij is not available or desired.

---

## 3. Implementation Steps & Validation Gates

1. **Step 1**: Implement `scripts/ai/aq-cockpit-monitor` (live telemetry, service health, context meters, pulse ticker).
2. **Step 2**: Implement `scripts/ai/aq-fleet-monitor` (live fleet tracking, thought streaming, note-to-self, task status).
3. **Step 3**: Implement `scripts/ai/aq-coordinator-repl` (interactive REPL, prompt_toolkit, model routing, subagent dispatch, intervention controls, tool cards).
4. **Step 4**: Author Zellij configuration & layout in `config/zellij/aq-agentic-workspace.kdl`.
5. **Step 5**: Create master launcher `scripts/ai/aq-workspace` with auto-detection, session management, and fallback.
6. **Step 6**: Add test suite `scripts/testing/test-aq-workspace.py` to validate CLI arguments, layout syntax, and non-interactive runs.
7. **Step 7**: Test live in terminal and verify all 53 tier-0 validation gates.
