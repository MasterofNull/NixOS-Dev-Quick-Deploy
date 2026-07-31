# Collaborative Round — c6-review

Opened: 2026-07-31T00:38:29Z
Target artifact (if a review round): .agents/plans/aqos-foundation-c/

## Task
ROLE: independent binding DESIGN reviewer for Foundation C C6 (epoch-revocation control + F2.5
scheduler seam). Read .agents/plans/aqos-foundation-c/C6-DESIGN-AND-AUTHORIZATION.md. Read-only.
Substitute for codex (down to Aug-4). ENFORCEMENT-TIER (scheduler seam). VERIFY anchors: F2.5
slot_scheduler/wait_for_slot LIVE in scripts/ai/lib/dispatch.py (135/502); resolve_current_epoch
+ config/capability-lease-epoch in capability_lease_gate.py; epoch_stale in capability_lease.py — no
fabrication. Judge §7 obligations CLOSED/gap+fix: (1) epoch bump atomic+monotonic+audited+fail-closed;
unreadable epoch => deny everywhere. (2) scheduler seam deny-closed (refuse-on-doubt), flag-OFF
byte-parity, NO non-lease-request regression. (3) non-self-healing preserved (no auto-reissue,
monotonic, forward-only). (4) seam COMPOSES with the shipped executor checks (defense in depth), not
replaces/weakens. (5) F2.5 anchors real. (6) bump authority = owner/operator kill switch, governed+
audited. Weigh Q-C6-1..4 (esp. Q-C6-4: does executor-check + scheduler-seam + control-surface satisfy
F3 obligation-3 end-to-end, closing Cycle 6). OUTPUT: VERDICT PASS/FAIL/REQUEST_REVISION line 1, then
findings by severity + ref + fix, + Q verdicts.

## Protocol
Each agent writes its OWN file here — `codex.md`, `local.md`, `antigravity.md`, `claude.md`.
NEVER append to a shared file. The orchestrator aggregates into `AGGREGATE.md`.
- local[Qwen] runs long — the round stays OPEN for it; never skipped.
- antigravity (Antigravity IDE, real Gemini via its OWN OAuth) picks up the task from the inbox
  `.agent/collaboration/antigravity-inbox/c6-review.md` and writes `antigravity.md`. No API keys.
