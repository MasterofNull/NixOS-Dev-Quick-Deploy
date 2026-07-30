# Collaborative Round — c3b-r1-review

Opened: 2026-07-30T04:37:47Z
Target artifact (if a review round): .agents/plans/aqos-foundation-c/

## Task
ROLE: independent binding DESIGN reviewer for Foundation C slice C3b, stage R1 (pure grant schema
+ classification). Read-only — no edits, no commits. This is a DESIGN review (no code yet). You are
substituting for codex (usage-limited); codex will run a confirmatory audit on return, so be
rigorous and specific. IMPORTANT: verify every claim against the ACTUAL code — do not approve prose;
if the doc names an API or field, confirm it exists before accepting it.

READ:
- .agents/plans/aqos-foundation-c/C3B-R1-DESIGN-AND-AUTHORIZATION.md  (under review)
- .agents/plans/aqos-foundation-c/C3B-DESIGN-AND-AUTHORIZATION.md (R0) + C3B-R0-REVIEW-OPUS.md
  (the SF-1/SF-3 findings this R1 folds)
- Ground against real code: scripts/ai/lib/capability_lease.py (canonical_payload, sign, verify,
  resolve_key), scripts/ai/lib/capability_lease_issuance.py (current signed lease fields),
  ai-stack/switchboard/capability_lease_gate.py (resolve_current_epoch ~172, DEFAULT_EPOCH_PATH
  config/capability-lease-epoch ~84), config/first-party-tools.json (the tool set — but note its
  effect flags are asserted INACCURATE vs real handlers).

TEST THESE OBLIGATIONS (§8 of the doc) — for each, state CLOSED or a concrete gap with the exact
§ref + fix:
1. Grant schema (§2) is closed; every missing/unknown/malformed field denies. Any field that could
   be defaulted or skipped?
2. SF-1 signing (§3): is Ed25519 asymmetric correctly specified so a compromised/key-less RUNNER
   cannot forge a grant (gate holds private, runner holds only public)? Is key separation from the
   lease HMAC real? Is there any unsigned/symmetric fallback? Is the no-grant degrade correct?
   Verify `cryptography` ed25519 is actually importable in this repo's env.
3. Replay (§5): is the uniqueness domain grant_id (global), with reserved→committed|failed? Any
   race or task-scoping regression?
4. Epoch (§5): is resolve_current_epoch / config/capability-lease-epoch the real source, and does
   current_epoch is None → deny (never skip)? Confirm the anchor exists.
5. SF-3 classification (§4): is it conservative and manifest-DISTRUSTING (no tool trusted from
   write:False/net:False)? Does every network/subprocess/multi-effect/unaudited tool deny? Check the
   §4.3 table against the real handlers (e.g. is store_memory really network? is run_command
   multi-effect?). Any tool wrongly allowed?
6. Path classification (§4.2): pure + component-aware containment (not string-prefix)? Every escape
   class (abs/.., symlink, NUL, non-NFC, casefold-collision, prefix-not-containment) denied?
7. Verify functions (§5): pure, deny-closed, never-raise; only all-pass yields VerifiedGrant?
8. Golden vectors (§6): do they cover every deny path with exact typed outcomes? Any missing case?
9. Scope containment (§1, §7): does R1 correctly introduce NO socket/clone/bwrap/Nix/FS surface?

ALSO: is there any NEW fail-open? Is the R1→R2 handoff (§7) clean? Are there fabricated/nonexistent
API references in the doc (verify capability_lease + gate anchors actually exist)?

OUTPUT: `VERDICT: PASS` / `VERDICT: FAIL` / `VERDICT: REQUEST_REVISION` on the FIRST line, then
findings by severity (BLOCKING / SHOULD-FIX / NICE-TO-HAVE) with exact §ref + concrete fix. No
review outcome authorizes build or activation.

## Protocol
Each agent writes its OWN file here — `codex.md`, `local.md`, `antigravity.md`, `claude.md`.
NEVER append to a shared file. The orchestrator aggregates into `AGGREGATE.md`.
- local[Qwen] runs long — the round stays OPEN for it; never skipped.
- antigravity (Antigravity IDE, real Gemini via its OWN OAuth) picks up the task from the inbox
  `.agent/collaboration/antigravity-inbox/c3b-r1-review.md` and writes `antigravity.md`. No API keys.
