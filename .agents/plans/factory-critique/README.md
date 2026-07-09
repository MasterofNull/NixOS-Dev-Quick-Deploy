# Collaborative Round — factory-critique

Opened: 2026-07-07T18:27:21Z
Target artifact (if a review round): .agents/plans/factory-critique-brief.md

## Task
FOUNDATION CRITIQUE of the flat-collaborative factory core (aq-collab-round + the workflow + config + capability auto-selection). Read the full brief at .agents/plans/factory-critique-brief.md — it includes the local-embedded-agent utilization evidence (no model-stacking, single slot, no GBNF) and the operator's 5 questions (where to improve, is it too ad-hoc, what papers/studies/tools/skills/logic are MISSING, how to reach highest operability/productivity, and the right local-model stacking/scheduling design). Be critical and specific; name concrete papers/systems/techniques; rank your top 3 changes.

## Protocol
Each agent writes its OWN file here — `codex.md`, `local.md`, `antigravity.md`, `claude.md`.
NEVER append to a shared file. The orchestrator aggregates into `AGGREGATE.md`.
- local[Qwen] runs long — the round stays OPEN for it; never skipped.
- antigravity (Antigravity IDE, real Gemini via its OWN OAuth) picks up the task from the inbox
  `.agent/archive/antigravity-inbox-20260709/factory-critique.md` and writes `antigravity.md`. No API keys.
