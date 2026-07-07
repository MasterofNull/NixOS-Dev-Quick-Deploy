# Collaborative Round — f2-local-scheduler

Opened: 2026-07-07T18:43:58Z
Target artifact (if a review round): .agents/plans/f2-brief.md

## Task
F2 DESIGN: local model-stacking + measured slot scheduler (factory-critique #2). Read .agents/plans/f2-brief.md. Design: model-tier→task routing (resident 4B/phi-4-mini + 8B + 35B session-mode), slot scheduler (MLFQ+aging queue classes, back-pressure/typed local-delayed), VRAM pool manager (4GB APU), GBNF+grammar-cache, prefix/KV reuse, acceptance metrics, declarative Nix wiring. Rank top 3. No implementation.

## Protocol
Each agent writes its OWN file here — `codex.md`, `local.md`, `antigravity.md`, `claude.md`.
NEVER append to a shared file. The orchestrator aggregates into `AGGREGATE.md`.
- local[Qwen] runs long — the round stays OPEN for it; never skipped.
- antigravity (Antigravity IDE, real Gemini via its OWN OAuth) picks up the task from the inbox
  `.agent/collaboration/antigravity-inbox/f2-local-scheduler.md` and writes `antigravity.md`. No API keys.
