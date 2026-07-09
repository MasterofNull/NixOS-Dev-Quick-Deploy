# Collaborative Round — f1-round-state-machine

Opened: 2026-07-07T18:40:24Z
Target artifact (if a review round): .agents/plans/f1-brief.md

## Task
F1 DESIGN: durable, typed round STATE MACHINE + contribution contract to replace aq-collab-round's ad-hoc conventions (the #1 change from the unanimous factory-critique). Read the full brief at .agents/plans/f1-brief.md. Design concretely: the state table (CREATED..CLOSED + transitions/invariants), round.json manifest schema, the TYPED contribution envelope (verdict enum + required_changes/risks/tests/anchors + model provenance), idempotent open/collect/aggregate, quorum+timeout (late-local admissible), a deterministic aggregation algorithm, and golden-ROUND tests. Rank your top 3 design decisions. No implementation yet.

## Protocol
Each agent writes its OWN file here — `codex.md`, `local.md`, `antigravity.md`, `claude.md`.
NEVER append to a shared file. The orchestrator aggregates into `AGGREGATE.md`.
- local[Qwen] runs long — the round stays OPEN for it; never skipped.
- antigravity (Antigravity IDE, real Gemini via its OWN OAuth) picks up the task from the inbox
  `.agent/archive/antigravity-inbox-20260709/f1-round-state-machine.md` and writes `antigravity.md`. No API keys.
