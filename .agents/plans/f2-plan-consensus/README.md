# Collaborative Round — f2-plan-consensus

Opened: 2026-07-08T03:48:39Z
Target artifact (if a review round): .agents/plans/f2-impl-plan.md

## Task
PLAN-CONSENSUS review of the F2 implementation plan (inlined). The F2 DESIGN is 4/4 ratified — do NOT re-design; assess whether this IMPLEMENTATION PLAN faithfully realizes it and is safely phased. Decide: (1) Is the Phase-A (rebuild-free: F2.1 MLFQ+aging scheduler, F2.2 GBNF cache, F2.3 local-delayed back-pressure, F2.4 model-tier routing) / Phase-B (rebuild-gated: F2.5 fast-lane :8082 + VRAM pool + Nix, F2.6 35B-on-CPU A/B bench) split correct — is anything in Phase A actually rebuild-dependent, or vice versa? (2) Does F2.1's MLFQ+aging+preemption correctly realize the ratified 3-band scheduler without starvation? (3) Is the GBNF cache key sha256(schema+zero_trust_state) right + does it correctly share F3's zero_trust namespace? (4) Does local-delayed back-pressure integrate with F1 quorum so never-skip-local holds (a delayed lane stays admissible)? (5) Is routing pure/testable without real inference? (6) Biggest RISK in the fast-lane :8082 + VRAM-pool infra (F2.5) on the 4GB APU — and is the 35B-on-CPU flip correctly gated as measure-before-adopt not assumed? Rank your top 3 plan changes. Write your OWN file .agents/plans/f2-plan-consensus/<AGENT>.md only.

## Protocol
Each agent writes its OWN file here — `codex.md`, `local.md`, `antigravity.md`, `claude.md`.
NEVER append to a shared file. The orchestrator aggregates into `AGGREGATE.md`.
- local[Qwen] runs long — the round stays OPEN for it; never skipped.
- antigravity (Antigravity IDE, real Gemini via its OWN OAuth) picks up the task from the inbox
  `.agent/collaboration/antigravity-inbox/f2-plan-consensus.md` and writes `antigravity.md`. No API keys.
