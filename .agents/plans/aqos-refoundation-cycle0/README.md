# Collaborative Round — aqos-refoundation-cycle0

Opened: 2026-07-10T04:03:54Z
Target artifact (if a review round): .agents/plans/aqos-refoundation-cycle0

## Task
Read .agents/prompts/AQOS_OWNER_NEXT_CYCLE_META_PROMPT.md and act as the complete required expert team. Produce an independent evidence-led proposal only: product definition, current-state authority map, clean-sheet architecture critique, ranked parity gaps, threat controls, Cycle 0 PRD slices, validation matrix, retirement plan, and verdict. Do not read other lane proposals. Do not implement code. Load reference skills multi-agent-collab, context-efficiency, system-dev.

## Protocol
Each agent writes its OWN file here — `codex.md`, `local.md`, `antigravity.md`, `claude.md`.
NEVER append to a shared file. The orchestrator aggregates into `AGGREGATE.md`.
- local[Qwen] runs long — the round stays OPEN for it; never skipped.
- antigravity (Antigravity IDE, real Gemini via its OWN OAuth) picks up the task from the inbox
  `.agent/collaboration/antigravity-inbox/aqos-refoundation-cycle0.md` and writes `antigravity.md`. No API keys.
