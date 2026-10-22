# Plan: SOTA Durable Agent Sweeper & Impeccable Cockpit/Canvas Interface

- **Target Plan ID**: `PLAN-DURABLE-AGENTS-SOTA-UI-20261019`
- **Owner**: hyperd
- **Orchestration**: Antigravity (Gemini) / Claude (Opus)
- **Status**: Ready for Slice Dispatch

---

## Slice Inventory

### Slice 1: Durable Sweeper Core & Classifier Contract (`durable-sweeper-core`)
- **Objective**: Create the core schema, state storage, and classification prompt for the proactive sweeper.
- **Files**:
  - `config/schemas/durable-sweeper-state.schema.json`
  - `scripts/ai/aq-durable-sweeper`
  - `prompts/intelligence/hype-facts-signal.prompt.txt`
  - `scripts/testing/test-durable-sweeper.py`
- **Verification**: Unit tests verifying state save/resume, deterministic classification, and fail-closed timeout.

### Slice 2: Cockpit Telemetry Bridge & Thought Stream Card (`cockpit-telemetry-bridge`)
- **Objective**: Ensure the sub-agent interactive console and cockpit never render empty windows. Pipe thoughts, tool calls, and status codes to a live stream view.
- **Files**:
  - `scripts/ai/aq-cockpit-monitor`
  - `scripts/ai/aq-subagent-interactive`
  - `assets/cockpit/stream-card.html` (or terminal TUI equivalent)
  - `docs/operations/AQ-COCKPIT-STREAM-GUIDE.md`
- **Verification**: Live test in Zellij showing active thoughts and tool status during execution.

### Slice 3: Human Intervention Dock & Steering Modal (`human-intervention-dock`)
- **Objective**: Allow the human operator to pause, inject prompts, or skip steps directly from the cockpit without killing the process.
- **Files**:
  - `scripts/ai/aq-human-intervention`
  - `config/zellij/aq-agentic-workspace.kdl`
  - `scripts/testing/test-human-intervention.py`
- **Verification**: Verify that injecting an intervention updates the agent's active memory and pulse log immediately.

### Slice 4: Declarative Systemd Timer & Dashboard Integration (`durable-agent-systemd`)
- **Objective**: Declaratively package the durable sweeper into NixOS systemd user services and add a live card to the dashboard.
- **Files**:
  - `nix/modules/services/durable-agent.nix`
  - `assets/dashboards/cards/durable-agent-card.html`
- **Verification**: `nixos-rebuild dry-run` passes; service starts and reports status to the dashboard.
