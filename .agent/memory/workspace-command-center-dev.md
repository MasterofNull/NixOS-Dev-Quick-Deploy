# SOTA Agentic Workspace & AI Command Center — Architecture & Memory Record

**Document ID**: `.agent/memory/workspace-command-center-dev.md`  
**Created**: 2026-09-26  
**Status**: ACTIVE & OPERATIONAL  
**Branch**: `feat/sota-agentic-workspace-gui`  
**Related Documents**: [`.agent/PROJECT-AGENTIC-WORKSPACE-PRD.md`](file:///home/hyperd/Documents/NixOS-Dev-Quick-Deploy/.agent/PROJECT-AGENTIC-WORKSPACE-PRD.md), [`docs/operations/aq-workspace.md`](file:///home/hyperd/Documents/NixOS-Dev-Quick-Deploy/docs/operations/aq-workspace.md)

---

## 1. Vision & Core Purpose

`aq-workspace` and the AI Command Center (`dashboard.html` / `:8889`) constitute the primary human-agent collaboration powerhouse for the AQ-OS platform. Designed to eliminate external IDE dependencies, the platform provides a unified terminal multiplexer environment (Zellij) alongside a real-time web command center for steering multi-model swarms, monitoring sub-agents, inspecting thought streams, and tracking APU hardware telemetry.

---

## 2. Terminal Workspace Architecture (`aq-workspace`)

### 2.1 Launch & Session Lifecycle Management
- **Single-Command Entry**: `aq-workspace` starts or cleanly attaches to the workspace for the current working directory.
- **Intelligent Lifecycle**:
  - If no session exists: Spawns fresh session via `zellij --layout <kdl> --session <name>`.
  - If session exists and is `EXITED`: Automatically purges the dead session and recreates it with the SOTA layout.
  - If session is active: Attaches cleanly via `zellij attach <name>`.
  - Reset command: `aq-workspace reset` force-clears any zombie sessions and initializes a clean multi-tile layout.
- **Terminal Capability Guard**: Enforces `TERM="xterm-256color"` to ensure ncurses, rich, and interactive TUIs (like Codex and Claude Code) render with full 256-color support and never encounter `TERM="dumb"` traps.

### 2.2 Dual-Board Swarm Layout (`config/zellij/aq-agentic-workspace.kdl`)
- **Left Board (52% Width)**: 4-Quadrant Main Model Cockpit:
  - Top-Left: **Local Qwen3-35B** on APU (`:8080` / `:8003`) with active context hydration.
  - Top-Right: **Claude 3.7 / Fable-5** (Claude Code CLI / Switchboard `:8085`).
  - Bottom-Left: **OpenAI Codex / GPT-6 Astra** (Codex CLI / Coordinator `:8003`).
  - Bottom-Right: **Google Gemini 3.8-Flash** (Switchboard `:8085` streaming adapter).
- **Right Board (48% Width)**: Interactive Sub-Agent Console & Delegation Tree:
  - Top (40%): **Sub-Agent Delegation Hierarchy Tree** (`aq-fleet-monitor --tree`) displaying live parent-child delegation chains, runtime status, and elapsed duration.
  - Bottom (60%): **Interactive Sub-Agent Console & Steering** (`aq-subagent-interactive`) enabling real-time prompt injection (`/steer`), sub-agent cancellation (`/cancel`), and manual delegation (`/spawn`).

### 2.3 Interactive Agent Launcher (`scripts/ai/aq-agent-launcher`)
- Serves as the supervisor for every model pane in the multiplexer.
- Presents a crisp status banner with live auth status detection (`get_auth_status`).
- On-demand activation: Waits for operator input (`[1] Launch/Resume`, `[2] Fresh Session`, `[3] Dev Shell`, `[4] Sign In`) rather than flooding the APU and remote APIs with 15 concurrent unprompted calls.
- Persistent supervisor loop: If an agent process exits or times out, the Zellij pane stays open with an interactive restart/shell menu rather than collapsing the pane.

---

## 3. Web Command Center Architecture (`dashboard.html` / `assets/dashboard.js`)

1. **Executive Situational Awareness & Synthesis Layer**:
   - 3 Unified Operational Pillars (Foundational Integrity & Security, Execution Velocity & Precision, Resource Economics & Sovereignty).
   - End-to-End Value Stream Pipeline (Ingestion → Orchestration → Inference → Verification → Deployment).
2. **Radial Vital Gauges & Progressive Disclosure**:
   - 4 SVG Master Dial Gauges: Factory Health & Integrity (100/100 calibrated), Compute Sovereignty (% local APU), Hardware Vitals & Thermal (APU temp + memory headroom), Context Precision & Memory (AIDB facts + vector precision).
   - `#telemetrySubMenuDrawer`: 3-tab collapsible drawer housing all 14 raw sensors, 7d/30d historical benchmarks, and live JSON telemetry streams with one-click export.
3. **Subsystem Hero Strips**:
   - Top-level context primers, vital tiles, and collapsible technical blueprints across all 11 dashboard tabs.
4. **Live Human-in-the-Loop Steering Console**:
   - Real-time action triggers (`[STEER]`, `[PAUSE]`, `[RESUME]`, `[KILL]`), quick-dispatch toolbar with role selector, and live `<think>` Note-to-Self streaming viewer.
5. **Terminal Workspace Bridge**:
   - Integrated quick-launcher ribbon in the Agent Fleet panel with click-to-copy commands for `aq-workspace`.

---

## 4. Model Configurations, Ports & Backends (SSOT)

| Model Lane | Backend Route | Port | Engine / Runtime | Capabilities |
| :--- | :--- | :--- | :--- | :--- |
| **Local Qwen** | `http://127.0.0.1:8080/v1/chat/completions` | `8080` | `llama-server` (llama.cpp) | Qwen3-35B GGUF Q4_K_M, 12 APU GPU layers, 8,192 ctx, zero network |
| **Hybrid Coordinator** | `http://127.0.0.1:8003/v1/chat/completions` | `8003` | Python FastAPI + UAG | Model routing, task classification, memory broker, AIDB bridge |
| **Switchboard** | `http://127.0.0.1:8085/v1/chat/completions` | `8085` | Switchboard Proxy | Profiles: `claude-fable-5-1`, `gemini-3.8-flash`, `deepseek-reasoner` |
| **AIDB Memory** | `http://127.0.0.1:8002/api/` | `8002` | PostgreSQL + pgvector + Qdrant | Semantic RAG, fact stores, lessons registry, knowledge graphs |
| **Dashboard API** | `http://127.0.0.1:8889/api/` | `8889` | FastAPI async metrics collector | Live WebSocket streams, health score computation, OSI layer checks |

---

## 5. Development Commit Progression

| Commit | Summary | Key Surfaces |
| :--- | :--- | :--- |
| `f2d37709` | SOTA multi-tiled agentic workspace & modernized GUI | `aq-workspace`, `aq-coordinator-repl`, `aq-fleet-monitor`, `aq-cockpit-monitor`, `dashboard.html` |
| `c1c5da48` | Dual-board multi-model windows & interactive steering | Left/Right board KDL layout, `aq-subagent-interactive`, executive synthesis layer |
| `538a4b28` | Radial vital gauges & progressive disclosure drawer | 4 SVG radial dial gauges, `#telemetrySubMenuDrawer`, live historical benchmark tables |
| `0781d9fd` | Health score rebase to 100/100 & subsystem hero strips | APU memory/temp calibration, 10 panel hero strips, PyYAML import safeguard |
| `8286cc34` | Direct CLI agent launcher & dashboard quick bar | `aq-agent-launcher`, auto-resume & auth detection, workspace ops guide |

---

## 6. Verification Commands & Diagnostics

```bash
# Verify AI Stack and Cockpit health snapshot
aq-workspace status

# Run automated workspace test suite (12 tests)
python3 scripts/testing/test-aq-workspace.py

# Launch or reset the interactive SOTA workspace in terminal
aq-workspace reset

# Directly launch targeted native CLI agent panes
aq-workspace claude
aq-workspace codex
aq-workspace local
aq-workspace gemini

# Verify Dashboard API status and health score
curl -s http://127.0.0.1:8889/api/metrics/health-score
```
