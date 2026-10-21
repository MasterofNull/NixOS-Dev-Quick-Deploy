# Evidence: Live Wiring of Durable Sweeper & Remote Lane Egress Friction Gate

**Date**: 2026-10-21
**Lane**: headless orchestrator
**Objective**: Connect newly merged operational components into active execution paths and live system inputs per Rule 23 (NO DECORATIVE CODE).

## 1. Durable Sweeper Integration
- **Producer / Service**: `scripts/ai/aq-durable-sweeper` (systemd user timer: `aq-durable-sweeper.timer`).
- **Live Input Source**: Connected to `.agents/plans/frontier-evidence-intake/BACKLOG.jsonl`.
- **Ground-Truth Metric**:
  - Successfully ingested 16 real evidence backlog items on initial sweep.
  - Classified items into verified facts and candidate signals stored at `~/.local/share/aq-durable-agent/sweeper-state.json`.

## 2. Remote Lane Egress Friction Gate Integration
- **Producer / Gate**: `scripts/ai/lib/remote_lane_egress.py` (`config/remote-lane-egress.json`).
- **Wired Callers**:
  - `scripts/ai/delegate-to-claude`
  - `scripts/ai/delegate-to-codex`
  - `scripts/ai/delegate-to-gemini`
- **Execution Safety**:
  - Implemented safe exit-code handling (`|| rc=$?`) so non-fatal warning/hold logs do not trip `set -e` in delegation shells.
  - Passes full worktree isolation test fixture: `python3 scripts/testing/test-worktree-isolation.py`.
