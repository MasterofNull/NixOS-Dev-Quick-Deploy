# AQ-OS SOTA Agentic Workspace (`aq-workspace`)

Status: ACTIVE & OPERATIONAL
Owner: AI Stack Maintainers / Operator
Last Updated: 2026-09-26

`aq-workspace` is the single-command entrypoint for the AQ-OS state-of-the-art agentic development environment. Inspired by the setups of IndyDevDan, Pi Agent, and Herdr, it provides a persistent, multi-tiled terminal workspace uniting interactive model coordination, real-time sub-agent fleet monitoring, live thought streaming, and system telemetry—completely eliminating the need to run an external IDE for agent collaboration.

---

## 1. Quick Start

From **any** directory in the terminal, run:

```bash
# Launch or attach to the tiled workspace for the current project directory:
aq-workspace

# Automatically resume previous sessions across all agent panes:
aq-workspace resume

# Directly launch dedicated remote agent windows:
aq-workspace claude             # Claude 3.7 / Fable-5 (Switchboard :8085)
aq-workspace codex              # OpenAI Codex / GPT-6 (Coordinator :8003)
aq-workspace local              # Local Qwen3-35B on APU (:8080 / :8003)
aq-workspace gemini             # Google Gemini 3.8-Flash (Switchboard :8085)

# Or run with a custom session name:
aq-workspace my-session

# Launch the unified single-window Rich TUI fallback (no multiplexer required):
aq-workspace --tui

# Inspect AI stack health and live telemetry:
aq-workspace status

# List active agentic workspace sessions:
aq-workspace list

# Terminate a workspace session:
aq-workspace kill [session-name]
```

---

## 2. Multi-Tiled Architecture

The default workspace uses a native **Zellij** layout (`config/zellij/aq-agentic-workspace.kdl`):

```
┌──────────────────────────────────────────────┬────────────────────────────────┐
│                                              │ 󰓅 Sub-Agent Fleet Matrix       │
│                                              │   • Active & recent workers    │
│                                              │   • Live thought stream (N2S)  │
│ 󰚩 Coordinator & Steering REPL                 │   • Tool execution status      │
│   • Multi-turn streaming chat                ├────────────────────────────────┤
│   • Model routing (/model, /route)           │ 󰒋 Telemetry Cockpit            │
│   • Sub-agent dispatch (/dispatch)           │   • 6 Service health probes    │
│   • Real-time steering (/steer, /kill)       │   • APU/GPU VRAM & Context %   │
│   • Interactive tool cards                   │   • Token throughput rate      │
│                                              │   • Ops PULSE.log ticker       │
└──────────────────────────────────────────────┴────────────────────────────────┘
```

### Workspace Tabs
- **Tab 1: `󰚩 Agentic Workspace`**: Primary 3-pane layout (Coordinator Console + Fleet Matrix + Telemetry Cockpit).
- **Tab 2: `󰓅 Fleet Matrix`**: Full-screen 2x2 grid tailing live inputs, outputs, and thought streams across all active workers.
- **Tab 3: `󰒋 Operations & Mesh`**: Detailed system diagnostics, A2A safeguard audits, and process tables.
- **Tab 4: ` Scratch Shell`**: Clean local terminal in the project directory with harness environment pre-loaded.

---

## 3. Coordinator & Steering REPL Controls

The coordinator console (`aq-coordinator-repl`) supports rich slash commands:

| Command | Action | Example |
| :--- | :--- | :--- |
| `/model <name>` | Switch active model route on the fly | `/model local` (Qwen3-35B), `/model claude`, `/model codex`, `/model gemini` |
| `/dispatch <role> "<task>"` | Dispatch a background sub-agent worker | `/dispatch implementer "Add unit test for auth router"` |
| `/fleet` | List all running and recent sub-agents with PIDs and status | `/fleet` |
| `/steer <task_id> "<msg>"` | Inject live human guidance/intervention into running agent | `/steer local-20260926-081239 "Refactor the parser instead"` |
| `/inspect <task_id>` | View full live output tail and thoughts for a task | `/inspect local-20260926-081239` |
| `/kill <task_id>` | Cancel a running sub-agent task safely | `/kill local-20260926-081239` |
| `/status` | Print instant AI stack and service health diagnostics | `/status` |
| `/pulse` | View recent system operations from `PULSE.log` | `/pulse` |
| `/clear` | Clear console screen | `/clear` |
| `/exit` | Exit the coordinator REPL | `/exit` |

---

## 4. Sub-Agent Fleet Matrix (`aq-fleet-monitor`)

The fleet monitor pane automatically:
- Tracks tasks registered in `.agents/delegation/registry.jsonl`.
- Tails live output streams from `.agents/delegation/streams/<task_id>.stream`.
- Highlights **Note-to-Self (N2S)** internal thoughts (`<think>...`) in italic cyan.
- Displays tool execution badges (`⚡ [TOOL]`) and token economics (tokens in + tokens out).
- Offers quick intervention command syntax for running tasks.

---

## 5. Telemetry Cockpit (`aq-cockpit-monitor`)

Monitors all core AI subsystem health with sub-second probes:
- **Switchboard** (`http://127.0.0.1:8085/health`)
- **Hybrid Coordinator** (`http://127.0.0.1:8003/health`)
- **Llama.cpp Engine** (`http://127.0.0.1:8080/health`)
- **AIDB Memory** (`http://127.0.0.1:8002/health`)
- **Qdrant Vector DB** (`http://127.0.0.1:6333/`)
- **Redis Cache** (`tcp://127.0.0.1:6379`)

Also renders live model profile metadata, measured token throughput rates, APU shared VRAM vs system RAM allocation, and real-time operations ticker from `PULSE.log`.

---

## 6. Dedicated Streaming Remote Agent Windows (`aq-agent-window`)

All agent panes in the workspace are powered by `aq-agent-window`, which connects directly to the harness remote model routing plane (Switchboard `:8085` and Hybrid Coordinator `:8003`) with live token streaming, Note-to-Self thought formatting, sub-agent delegation tracking, and dynamic model switching:

- **Claude 3.7 / Fable-5**: Switchboard `:8085` under `remote-reasoning` profile with Anthropic adapter.
- **OpenAI Codex / GPT-6 Astra**: Coordinator `:8003` / Switchboard `:8085` under `remote-coding` profile with OpenAI adapter.
- **Local Qwen3-35B APU**: llama.cpp `:8080` / Switchboard `:8085` under `continue-local` profile.
- **Google Antigravity / Gemini 3.8-Flash**: Switchboard `:8085` under `remote-gemini` profile and Antigravity IDE OAuth lane.

### Agent Window Capabilities
- **Live Token Streaming**: Real-time SSE token stream with elapsed duration and measured throughput (tok/s).
- **Sub-Agent Delegation Tracking (`/subagents`)**: Inspect active and recent sub-agents spun off by this lane, including live operation streams (`[TOOL OPERATION]`, `[THOUGHT]`, `[STATUS]`).
- **Sub-Agent Dispatch (`/delegate <lane> "<task>"`)**: Spin off autonomous sub-agents directly from within the agent's interactive window.
- **Dynamic Model Switching (`/model <name>`)**: Switch the window's backend route dynamically at runtime (e.g. `/model deepseek-r1`).
- **History Persistence**: Preserves multi-turn interaction history across restarts in `~/.aq_agent_<model>_history`.

---

## 7. Single-Window TUI Fallback Mode

For environments without Zellij or when connected over constrained SSH / mobile terminals, the unified fallback mode renders the 3-pane layout directly in a single terminal window using Rich:

```bash
aq-workspace --tui
```

---

## 8. Keyboard Navigation (Zellij)

- `Alt + h/j/k/l` or `Alt + Arrows`: Move focus between tiled panes.
- `Alt + n`: Next tab (`Workspace` → `Fleet Matrix` → `Operations` → `Scratch Shell`).
- `Alt + p`: Previous tab.
- `Alt + f`: Toggle fullscreen on the focused pane.
- `Ctrl + q`: Detach safely from the workspace session (leaves background agents running).
- `Ctrl + b` then `d`: Detach (when using tmux-compatible bindings).
