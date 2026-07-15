# Collaborative Round — unified-program

Opened: 2026-07-13T17:49:47Z
Target artifact (if a review round): .agents/plans/unified-program

## Task
Independent ratification review of the AQ-OS unified program package at commit aa2e4452. SUBJECTS: (1) .agents/plans/UNIFIED-PROGRAM-PLAN.md — consolidation of all four AQ-OS corpora + L-series + Track V into one spine (precedence, state ledger, traceability, loose threads, owner decisions Q1-Q9); (2) .agent/PROJECT-VERIFIED-FACTORY-PRD.md — Track V, 9 slices VF-1..VF-9; (3) .agent/PROJECT-CHECK-KERNEL-PRD.md — CheckSpec SSOT + aq check runner + section-6 amendments to the Antigravity ARE plan; (4) .agent/PROJECT-LOCAL-AI-FACTORY-CODEX-FABLE-SYNTHESIS.md as parent architecture (owner decision Q1). PRODUCE in your own file: per-subject score 1-10 with specific defects (file+section refs); APPROVE/REVISE per owner decision Q1-Q9 (plan section 6); answers to CK PRD section 9 questions (interim runner: focused-CI vs minimal aq check; ratchet unit: directory vs module; biome vs eslint); VF PRD section 3 disposition challenges; slices your lane claims per lane eligibility. END with explicit verdict APPROVE / REQUEST_REVISION / BLOCKED per subject plus overall. RULES: do not read other lanes' files; claude-fable-5 authored subjects 1-3 and abstains from scoring its own artifacts; evidence over assertion — cite file:line where you contest; codex lane is offline until 2026-07-15 and the round stays OPEN for its late fold-in. Load skills: multi-agent-collab, context-efficiency, system-dev.

## Protocol
Each agent writes its OWN file here — `codex.md`, `local.md`, `antigravity.md`, `claude.md`.
NEVER append to a shared file. The orchestrator aggregates into `AGGREGATE.md`.
- local[Qwen] runs long — the round stays OPEN for it; never skipped.
- antigravity (Antigravity IDE, real Gemini via its OWN OAuth) picks up the task from the inbox
  `.agent/collaboration/antigravity-inbox/unified-program.md` and writes `antigravity.md`. No API keys.
