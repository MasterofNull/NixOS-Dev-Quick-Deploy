# AQ-OS v1 — Next-Cycle Delegation Handoff

**Prepared**: 2026-07-09 by claude-fable-5 · **Dispatch**: next dev cycle, Beat 0

## One-command dispatch (Beat 0 ratification round)
```bash
scripts/ai/aq-collab-round open --round aqos-v1 \
  --task "$(cat .agents/plans/aqos-v1/ROUND-PROMPT.md)" \
  --target .agents/plans/aqos-v1
# lanes: codex (headless, own login), antigravity (watched inbox, IDE OAuth), local (inlined task, generous timeout)
# aggregation stays OPEN — fold late local contributions (never-skip-local HARD rule)
scripts/ai/aq-collab-round collect --round aqos-v1     # poll + extract
scripts/ai/aq-collab-round aggregate --round aqos-v1   # typed aggregation (F1.5)
```
Antigravity inbox copy: `.agent/collaboration/antigravity-inbox/aqos-v1.md` (IDE OAuth lane, no keys).

## Expected lane outputs
`.agents/plans/aqos-v1/{claude,codex,antigravity,local}.md` per ROUND-PROMPT contract →
orchestrator writes `AGGREGATE.md` (consensus ≥3/4 ratifies) → PRD amended → Beat 1 slices dispatched per PLAN.md matrix.

## Immediately dispatchable before ratification (no PRD dependency)
- **Slice 3.1** (F2.5 wiring — standing HIGH in issues-backlog): claude, dedicated slice.
- **Slice 1.6** (schema/envelope research): antigravity research lane.
- Operator action carried over from fable-parity cycle: `sudo systemctl restart ai-switchboard` (activates FABLE_PARITY_BODY profile cards).

## Ground rules for all delegated work
1. PRD gate: PULSE plan line before any file edit.
2. Fable-parity behavior contract applies to every lane (auto-injected in payloads/profiles).
3. Activation Gate: no slice is DONE until integrated+ON+validated+observable+intervenable or dated deferral.
4. Rule 16: any canonical change lands in all 5 agent files same cycle (until WS1 canon compiler mechanizes this).
5. Local failures are training targets (WS8), never grounds for skipping the local lane.
