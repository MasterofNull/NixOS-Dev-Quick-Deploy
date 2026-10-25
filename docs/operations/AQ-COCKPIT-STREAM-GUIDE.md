---
Status: Active
Owner: hyperd
Last Updated: 2026-10-25
---

# AQ-Cockpit Stream & Operator Guide

The **AQ-Cockpit** provides real-time, non-blocking visibility and steering over active multi-agent swarms in the NixOS AI development factory.

## Key Capabilities

1. **Live Thought & Operation Streaming**:
   - Displays real-time thought streams, tool execution arguments, and results without blank panes.
   - Run `scripts/ai/aq-subagent-interactive --once` for instant command-line state snapshots.
   - Run `scripts/ai/aq-cockpit-monitor` for the rich TUI system dashboard.

2. **Operator Steering & Intervention**:
   - `[p] Pause`: Halts sub-agent turn progression safely at the current step boundary.
   - `[r] Resume`: Continues execution from last state checkpoint.
   - `[s] Steer`: Injects guidance text directly into active agent context via the coordination bus.

3. **Telemetry & Economics**:
   - Sub-millisecond tracking across Switchboard (8085), Coordinator (8003), Llama.cpp (8080), AIDB (8002), and Qdrant (6333).
   - Real-time token consumption, VRAM pressure, and throughput monitoring.
