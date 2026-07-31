# Collaborative Round — c5-review

Opened: 2026-07-31T00:38:28Z
Target artifact (if a review round): .agents/plans/aqos-foundation-c/

## Task
ROLE: independent binding DESIGN reviewer for Foundation C C5 (OTel spans as source of truth). Read
.agents/plans/aqos-foundation-c/C5-DESIGN-AND-AUTHORIZATION.md. Read-only. Substitute for codex (down
to Aug-4). VERIFY anchors exist (scripts/ai/lib/trace.py span(), trace_collector.py optional-OTLP,
scripts/ai/aq-event/resume_projector) — no fabrication. Judge §8 obligations CLOSED/gap+fix: (1)
spans are EMIT-ONLY — nothing enforces on a span; C2/C3b/C4 behavior unchanged. (2) attrs low-card +
secret-free (no payloads/keys/prompts/raw-paths); malformed span dropped. (3) projections pure/
idempotent/reproducible; hand-edit drift caught. (4) flag-OFF byte-parity + shadow-first. (5) NO new
network egress (telemetry stays local); OTLP optional/offline-safe. (6) reuses real infra. C5 is
NON-ENFORCEMENT. Weigh Q-C5-1..3. OUTPUT: VERDICT PASS/FAIL/REQUEST_REVISION line 1, then findings by
severity + ref + fix, + Q verdicts.

## Protocol
Each agent writes its OWN file here — `codex.md`, `local.md`, `antigravity.md`, `claude.md`.
NEVER append to a shared file. The orchestrator aggregates into `AGGREGATE.md`.
- local[Qwen] runs long — the round stays OPEN for it; never skipped.
- antigravity (Antigravity IDE, real Gemini via its OWN OAuth) picks up the task from the inbox
  `.agent/collaboration/antigravity-inbox/c5-review.md` and writes `antigravity.md`. No API keys.
