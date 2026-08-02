# Collaborative Round — c3a2-review

Opened: 2026-07-31T00:48:55Z
Target artifact (if a review round): .agents/plans/aqos-foundation-c/

## Task
ROLE: independent binding DESIGN reviewer for Foundation C C3a-2 (delegate broker + signed-A2A
verify-before-write). Read .agents/plans/aqos-foundation-c/C3A-2-DESIGN-AND-AUTHORIZATION.md. Read-only.
ENFORCEMENT-TIER. Substitute for codex (down to Aug-4). VERIFY anchors: R1 execution_grant/attenuate,
R2 execution_cell_clone quarantine, scripts/ai/aq-antigravity-inbox _locked/_task_lock/receipt — no
fabrication. Judge §9 obligations CLOSED/gap+fix: (1) NO fail-open — every reject class (bad sig/stale
epoch/past deadline/replayed token/path escape/schema-invalid/dead heartbeat/key-unavailable) => no
authoritative write; deny-closed on unavailability. (2) signer chronology sound: LOCAL broker attests a
locally-recomputed digest AFTER reading quarantine; NO remote key; no remote-identity claim smuggled.
(3) verify-before-write real: remote writes quarantine ONLY, authoritative path committed via a C3b
cell, never remote-written. (4) replay uniqueness on the SIGNED composite key (child_lease_id,
idempotency_token) — NOT inbox task-ID; atomic; reserved->committed|failed crash recovery. (5) heartbeat
deterministic (signed monotonic seq + SIGNED allowed_gap; dead denies). (6) child ⊆ parent monotonic
attenuation; flag-OFF byte-parity (delegate stays deny); NO key handled/forwarded; inbox transport-only.
Weigh Q-C3a2-1..3. Any NEW fail-open, key leak, or remote-writes-authoritative-path hole? OUTPUT:
VERDICT PASS/FAIL/REQUEST_REVISION line 1, then findings by severity + ref + fix, + Q verdicts.

## Protocol
Each agent writes its OWN file here — `codex.md`, `local.md`, `antigravity.md`, `claude.md`.
NEVER append to a shared file. The orchestrator aggregates into `AGGREGATE.md`.
- local[Qwen] runs long — the round stays OPEN for it; never skipped.
- antigravity (Antigravity IDE, real Gemini via its OWN OAuth) picks up the task from the inbox
  `.agent/collaboration/antigravity-inbox/c3a2-review.md` and writes `antigravity.md`. No API keys.
