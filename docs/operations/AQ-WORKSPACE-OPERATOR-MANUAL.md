---
Status: Active
Owner: hyperd
Last Updated: 2026-10-21
---

> Historical-preservation note (2026-11-15): this imported manual's active
> status and command examples were captured on 2026-10-21. They are retained
> as operating context, not as current deployment-readiness evidence. Validate
> the current `scripts/maintenance/aq-deploy-current` workflow before use.

# AQ-OS Multi-Agent Workspace Operator Guide & Manual

This guide explains how to navigate, steer, and interact with the AI stack's multi-agent windowed workspace (`aq-workspace`), floating panes, sub-agent streams, and human-in-the-loop alert queues.

---

## 1. Quick Start

To launch the multi-agent workspace:
```bash
aq-workspace
```
Or attach to an existing session with automatic resumption across all lanes:
```bash
aq-workspace resume
```

To run in standalone terminal mode (without Zellij multiplexer):
```bash
aq-workspace --tui
```

---

## 2. Workspace Layout & Screen Zones

The workspace opens with the **Dual-Board Swarm Layout**:

```
┌───────────────────────────────────────┬───────────────────────────────────────┐
│              LEFT BOARD               │              RIGHT BOARD              │
│       Main Orchestrator Lanes         │     Sub-Agents & Steering Console     │
├───────────────────┬───────────────────┼───────────────────────────────────────┤
│ Qwen3-35B (Local) │ Claude 3.7 / Fable│ Sub-Agent Delegation Hierarchy Tree   │
│ (llama.cpp :8080) │ (Anthropic CLI)   │ (live active agent graph)             │
├───────────────────┼───────────────────┼───────────────────────────────────────┤
│ OpenAI Codex      │ Google Gemini     │ Interactive Sub-Agent Console         │
│ (Coordinator)     │ (agy CLI)         │ (stream tool calls, inject steering)  │
└───────────────────┴───────────────────┴───────────────────────────────────────┘
```

- **Left Board (Main Lanes)**: Direct interactive CLI panes for each model family.
- **Right Board (Sub-Agents)**:
  - **Top-Right (`aq-fleet-monitor --tree`)**: Live tree view of all spawned sub-agents and their hierarchy.
  - **Bottom-Right (`aq-subagent-interactive`)**: Live stream of terminal output, tool calls, and human-in-the-loop steering REPL.

---

## 3. Keyboard Shortcuts & Navigation

| Shortcut | Action | Description |
|---|---|---|
| **`Alt + Arrow Keys`** or **`Alt + h/j/k/l`** | **Navigate Panes** | Move cursor/focus between Left Board (Main Models) and Right Board (Sub-Agents). |
| **`Alt + f`** | **Fullscreen Toggle** | Maximize active pane to full window (press again to restore split). |
| **`Ctrl + p` then `w`** | **Floating Panes Toggle** | Show / hide floating overlay windows. |
| **`Ctrl + p` then `e`** | **Embed / Float Mode** | Pop a tiled pane out into a floating window, or snap it back. |
| **`Alt + n` / `Alt + p`** | **Next / Prev Tab** | Switch between full workspace tabs (Swarm Board, Claude, Codex, Gemini, Local, Monitors). |
| **`Ctrl + q`** | **Safe Detach** | Exit the terminal UI without stopping agents. All agents and background tasks continue running. |

---

## 4. Interacting with Sub-Agents & Steering (Human-in-the-Loop)

When an alert triggers, open or focus the **Interactive Sub-Agent Console** (`aq-subagent-interactive`):

```bash
aq-subagent-interactive
```

### In-Console Commands:
- **Select Sub-Agent**: Type `/select <number_or_id>` to attach to a running or blocked sub-agent.
- **Inject Steering / Guidance**: Type `/steer <your message or guidance here>`. This directly injects your instructions into the sub-agent's prompt context.
- **Cancel or Terminate**: Type `/cancel` or `/kill` to abort a runaway or stuck sub-agent.
- **Spawn New Task**: Type `/spawn <lane> "<task description>"`.
- **View Live Stream**: As the sub-agent invokes tools (`run_command`, `write_to_file`, `semgrep`), thoughts and outputs stream in real time.

---

## 5. Direct Commands for Targeted Work

You don't have to launch the full workspace if you want to inspect or interact with a single component:

| Task | Command |
|---|---|
| Attach directly to Sub-Agent Steering | `aq-workspace subagents` or `aq-subagent-interactive` |
| View Sub-Agent Tree Monitor | `aq-workspace tree` |
| Open Local Qwen3-35B CLI Window | `aq-workspace local` |
| Open Claude CLI Window | `aq-workspace claude` |
| Open OpenAI Codex CLI Window | `aq-workspace codex` |
| Open Google Gemini / Antigravity CLI | `aq-workspace gemini` |
| Check Swarm Telemetry & Health | `aq-workspace status` |
| View Local Training Loop & Benchmark | `aq-workspace training` |
| List Active Workspace Sessions | `aq-workspace list` |
| Safely Kill Stale Sessions | `aq-workspace reap` |

---

## 6. Local Training Loop & Continuous Eval Visibility

The local APU inference slot is continuously monitored by the **Local Training Loop** (`aq-local-training-loop`).

When a training cycle is active:
- **Telemetry Cockpit (`aq-workspace status`)**: Displays a dedicated `[Local Training Loop & Continuous Eval]` panel reporting loop state (`● EVAL_WAIT` / `○ IDLE`), active case ID, run ID, and certified benchmark accuracy (e.g. `11/12 (91.7%)`).
- **Interactive Steering Console (`aq-subagent-interactive`)**: Automatically surfaces a warning banner indicating the training run is holding the local slot, explaining any slot contention or queued evaluations.
- **Dedicated Training Tab in Zellij**: Press `Alt + n` to navigate to the **"Training & Continuous Eval"** tab to view the live benchmark status alongside the telemetry cockpit and sub-agent console.
- **Direct CLI Check**: Run `aq-workspace training` or `aq-local-training-loop --status` at any time to inspect past and in-progress training cycles.
