# Codex review queue

**Purpose:** durable queue of validated implementation candidates awaiting **binding independent
acceptance by codex** on its quota return (2026-07-25). Established under owner operating-model
directive 2026-07-19 (PULSE `[owner] [operating-model-directive]`).

## Operating model (while codex is quota-exhausted, until 2026-07-25)

- **Implementer lane stays open** — cheap-tier (Sonnet/Haiku) implementers run continuously; the
  pipeline does not idle on the codex outage.
- **Design / rebind / authorization reviews** stay on Claude flagship (Opus/Fable, fresh sessions)
  so slices can be activated and implemented without waiting for codex.
- **Binding implementation-candidate acceptance is reserved for codex.** A validated candidate is
  left **staged (uncommitted)** in the working tree; its acceptance-authorization doc (committed,
  freezing exact candidate hashes + criteria) is the durable review artifact.
- **Orchestrator (Fable) spot-review** catches obvious breakage before staging; it is NOT binding
  acceptance and never substitutes for the codex gate.
- **Commit only after codex PASS.** On return, codex executes each queued acceptance authorization;
  the orchestrator runs Tier-0, stages, and commits each candidate that earns codex PASS. A codex
  REQUEST_REVISION returns that slice to a bounded revision cycle.

## Queue

| # | Slice | Candidate paths | Acceptance authorization (frozen) | Status |
|---|-------|-----------------|-----------------------------------|--------|
| 1 | QPPR A2 dashboard-projection | qa_runner.py, aistack.py, dashboard.html, assets/dashboard.js, test-dashboard-qa-provider-probe.py (5) | superseded by fresh-flagship acceptance | **COMMITTED `265f5390`** — owner redirected acceptance to fresh Claude flagship (2026-07-20); first round caught a poller-cadence bug, bounded revision fixed it, revised candidate PASSED and committed. Codex confirmatory audit optional on return. |
| 2 | delegate-to-codex quota pre-check | delegate-to-codex, test-delegate-codex-quota-precheck.sh, .gitignore (3) | superseded by fresh-flagship acceptance | **COMMITTED `d087408e`** — same lane; first round caught a PIPESTATUS bug masking failed runs as success, bounded revision fixed it (reviewer proved the new test catches it against pre-fix bytes), committed. Codex confirmatory audit optional on return. |

**Queue status 2026-07-20:** both entries resolved via fresh Claude-flagship binding acceptance
(owner `[acceptance-lane-directive]`), not the codex wait. The staged-for-codex model remains
documented above for any future slice where the owner chooses to queue for codex instead.

## Notes for codex on return

- Verify each candidate's on-disk hashes against its acceptance-authorization doc before reviewing;
  a mismatch means the working tree drifted and the entry must be re-staged, not accepted.
- Already committed this session (NOT in this queue — landed via Claude-flagship acceptance before
  this operating model took effect): B2-M1A-AM2 `4747344b`, C1C-AM3 `1cca8c57`, A1-AM3 `3396f9df`.
  These are available for post-hoc codex audit if desired but are not blocking.
