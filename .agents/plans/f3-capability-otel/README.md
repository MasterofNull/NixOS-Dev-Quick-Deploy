# Collaborative Round — f3-capability-otel

Opened: 2026-07-07T18:43:59Z
Target artifact (if a review round): .agents/plans/f3-brief.md

## Task
F3 DESIGN: CapabilityLease contract + OTel observability + signed A2A envelope (factory-critique #3 + codex CapabilityLease insight). Read .agents/plans/f3-brief.md. Design: the CapabilityLease schema unifying all 5 auto-selection layers (deny-by-default, monotonic least-privilege, revocation; zero_trust becomes one lease); OTel span model (turn/tool-call spans + attributes) + emit/read points; signed A2A task envelope + heartbeat + output contract for the antigravity node (no keys, local signing); automatic rollback via worktree snapshot before write. Rank top 3. No implementation.

## Protocol
Each agent writes its OWN file here — `codex.md`, `local.md`, `antigravity.md`, `claude.md`.
NEVER append to a shared file. The orchestrator aggregates into `AGGREGATE.md`.
- local[Qwen] runs long — the round stays OPEN for it; never skipped.
- antigravity (Antigravity IDE, real Gemini via its OWN OAuth) picks up the task from the inbox
  `.agent/archive/antigravity-inbox-20260709/f3-capability-otel.md` and writes `antigravity.md`. No API keys.
