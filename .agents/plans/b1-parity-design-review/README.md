# Collaborative Round — b1-parity-design-review

Opened: 2026-07-23T23:39:43Z
Target artifact (if a review round): .agents/plans/local-inference-b1-parity/CHAT-BATCH-PARITY-DESIGN-PACKET.md

## Task
INDEPENDENT DESIGN REVIEW of the Foundation B1 chat/batch parity (shadow) design packet (inlined). Rule on: (1) is this genuinely DISTINCT from L2B-B — i.e. the cross-adapter equivalence PROOF the PRD gates L3/L4 on, not already done? (2) §6.1 — batch uses importable build_llama_payload but aq-chat's builders are class methods on a different coordinator/switchboard path; is 'harness-drive aq-chat with stubbed I/O' feasible at a 2-file ceiling, or is a thin aq-chat builder extraction a required prerequisite slice? (3) which chat-SSE vs batch-buffered streaming differences are contract-legitimate vs true divergences the oracle must fail on? (4) offline oracle vs live-shadow for the B1-exit item? Write your verdict to .agents/plans/b1-parity-design-review/<AGENT>.md. Be decisive; terminal VERDICT: APPROVE-FOR-AUTHORIZATION | REVISE — reason.

## Protocol
Each agent writes its OWN file here — `codex.md`, `local.md`, `antigravity.md`, `claude.md`.
NEVER append to a shared file. The orchestrator aggregates into `AGGREGATE.md`.
- local[Qwen] runs long — the round stays OPEN for it; never skipped.
- antigravity (Antigravity IDE, real Gemini via its OWN OAuth) picks up the task from the inbox
  `.agent/collaboration/antigravity-inbox/b1-parity-design-review.md` and writes `antigravity.md`. No API keys.
