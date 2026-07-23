# Binding Acceptance — router/claim dispatch integration (router-dispatch-integration)

**Verdict: PASS**

## Reviewer identity & routing
- Reviewer: `fable-5` (session flagship). Implementer:
  `claude-subagent-router-dispatch-integration` (Sonnet). Reviewer did NOT write
  the implementation — independent of the code under review.
- **Independence caveat (recorded):** reviewer also authored the DESIGN packet, so
  independence is weaker than ideal (checking an implementation against the
  reviewer's own design). Compensated with extra scrutiny + an explicit design
  self-critique below. A fully independent lane was unavailable: Codex quota
  cooldown ACTIVE (`.agents/delegation/.codex-quota-cooldown`, to Jul 29), Opus
  reviewer session-limited earlier this session, Gemini not autonomously reachable,
  local Qwen outside envelope for this reasoning. Substitution recorded per Rule 18;
  queue this slice for Codex confirmatory audit on its return
  (`AGENT-CATCHUP-QUEUE.md`).

## Subject (staged)
- `scripts/ai/lib/dispatch_consult.py` (new) — sha256 `b28358cf581177748591b2e14426b6dd3e901feca32d1a2eb8dde940857d8ec4`
- `scripts/ai/lib/dispatch.py` (edit) — sha256 `a7a65b919a4a5cbd7fc2022f9d7218e8d0a11943415551f3e9e9296d39db2541`
- `scripts/testing/test-dispatch-consult.py` (new) — sha256 `1cfbbd0d248d47a169b86a9aee624822d0b20df962f28a15df224d2b3d763767`
- Ceiling = these 3 code files (+ this doc + the design doc as record). The 7
  Codex C0.6-T files show as dirty in the tree but that is PRE-EXISTING state from
  the parallel Codex track — this slice did not touch them (confirmed: only the 3
  above appear in this slice's diff).

## What was verified (reviewer-run, not trusting reported numbers)
1. **Fail-open is load-bearing (decisive).** Independent negative control: point
   both tool paths at a nonexistent binary. `_fail_open=True` (production) →
   `ok=True, degraded=True` (dispatch proceeds); `_fail_open=False` (same input) →
   `blocked=True, ok=False`. The flag alone flips the outcome — the fail-open
   branch is real, not vacuous. This is the single most important property: the
   consult layer can never jam a live dispatch through its own failure.
2. **Only a healthy `already-held` blocks.** Traced `consult_before_dispatch`:
   every tool-error/timeout/unparseable/non-`already-held` claim reason funnels
   through `_degrade_or_block(fail_open=True)` → proceed. `already-held` from a
   healthy claim tool is the one unconditional block, surfacing `current_owner`.
3. **No cross-release.** `release_after_dispatch` no-ops when there is no
   `claim_token`/`claim_owner` (blocked or never-acquired), and `aq-slice-claim
   release` itself refuses `not-holder` — a blocked consult can't release another
   owner's claim. Context manager releases on BOTH normal exit and exception, only
   when not blocked.
4. **Substitution surfaced, not applied.** Router substitution populates
   `routed_lane`/`substituted`/`reason`, but the claim is acquired under the
   caller's own `requested_lane` — the module never silently redirects a dispatch.
   Correct: the claim reflects who actually does the work. Endorsed.
5. **Read-only paths never consult.** `list/status/check/monitor/repair-*/watch/
   cancel/kill-all` don't reach `dispatch_task`, so no claim files created.
6. `py_compile` clean; `test-dispatch-consult.py` 8/8; `test-local-delegation-
   artifact.py` 12/12 (no regression); subprocess via absolute paths, no shell=True.

## Design self-critique (author reviewing own design — on the record)
- **Accepted tradeoff:** `corrupt-claim-refuse` and `cas-error` are treated as
  fail-open (dispatch proceeds without coordination) rather than blocking. This is
  intentional and consistent with the fail-open/advisory contract — the layer must
  never jam dispatch on its own or the claim tool's failure, and `aq-slice-claim`
  itself fail-closes internally. Documented here so a future reviewer sees it was a
  deliberate choice, not an oversight. If stricter coordination is ever wanted, that
  is a new policy decision, not a bug in this slice.
- **Bounded scope is honest:** only the local lane is wired (reference
  integration). Codex/Gemini/Antigravity shims adopting the consult lib are
  explicit follow-up slices, not silently dropped.

## Disposition
PASS. Commit via `tier0-validation-gate.sh --staged-isolated` (isolate Codex track
dirt), push, release `router-dispatch-integration` claim. Queue for Codex
confirmatory audit on return.
