# Binding Acceptance — reclaim-TOCTOU fix (aq-slice-claim)

**Verdict: PASS**

## Reviewer identity & routing
- Reviewer: `fable-5` (session flagship), acting as independent binding-acceptance.
- Implementer: `claude-subagent-router-reclaim-toctou` (Sonnet). Reviewer did NOT
  write the code — independence preserved (Rule 18: binding acceptance = any
  independent flagship, not a fixed lane).
- **Lane substitution (recorded):** first-choice acceptance lane Codex is
  quota-exhausted until 2026-07-29; `aq-role-route` next-eligible pick Gemini is
  not autonomously reachable this session; Opus reviewer (afe1fd4e) terminated on
  a session limit mid-review (infra stop, not a verdict); local Qwen is outside
  its measured capability envelope for subtle multi-thread concurrency reasoning.
  Next eligible independent flagship = the session's own Fable. Substitution logged
  here per the agnostic-routing "route to next eligible + record" rule.

## Subject (staged, uncommitted at review time)
- `scripts/ai/aq-slice-claim` — sha256 `f2f37e869222d7d005be466621a4f07cc50ba85b5e0bf7aefef572602c2548f8`
- `scripts/testing/test-agent-agnostic-router.py` — sha256 `f5cf9c53f77a26153da108e2ef46f35ab2d8e0c3ed9c623a74d7bb2946cfc6c0`
- Ceiling = exactly these 2 files. The 7 Codex C0.6-T-track files (dashboard.js,
  aistack.py, aq-tui-dashboard, agent_ops_projection.py, phase0.py,
  test-agent-ops-projection.py, test-agent-ops-local-direct-health-web.py) are NOT
  in the staged diff — confirmed. Codex track untouched.

## What was verified
1. **Invariant (traced, not assumed).** Ownership is conferred *only* by a
   successful `O_CREAT|O_EXCL` create, and that create runs under the same
   per-slice advisory `flock` (`_locked_claim`) as every reclaim. `_reclaim_stale`
   only clears an expired file — it never grants ownership. Adversarial
   interleavings all resolve to a single holder:
   - two reclaimers on one expired claim → only one renames it away (rename under
     lock, serialized); the other's lock-protected re-read sees `None`/fresh and
     no-ops;
   - reclaim-then-foreign-create → the reclaimer's re-create fails `O_CREAT|O_EXCL`
     and it correctly reports the other holder ("Lost the reclaim race" path);
   - straggler after the world moved on → lock-protected re-read sees gone/non-expired
     and no-ops, never evicting speculatively.
2. **release is owner-gated** (`cmd_release` refuses `not-holder`) — a stale
   straggler cannot unlink a live claim. unlink-vs-rename is per-dir-entry atomic
   (documented, correct); reclaim handles the `FileNotFoundError` fail-closed.
3. **Independent stress (reviewer-run, not the implementer's numbers).** Driving
   the real `_write_claim_exclusive` / `_reclaim_stale` / `_load_claim` primitives:
   300 iterations × 12 racing threads against one already-expired claim →
   **0 double/zero-holder failures**; surviving claim file always owned by the
   single reported winner.
4. **Negative control is load-bearing (decisive).** Neutralizing `_locked_claim`
   to a no-op reproduces the bug at **227/300** runs; restoring it → 0/300. The
   fix is both correct and necessary, and the test that guards it is non-vacuous.
5. `py_compile` clean; full `test-agent-agnostic-router.py` suite PASS (incl. the
   in-tree concurrent-reclaim test + its negative control).

## Disposition
PASS. Clear to commit via `tier0-validation-gate.sh --staged-isolated` (isolates
the Codex track's in-flight dirty edits from validation), then release the
`router-reclaim-toctou` slice claim.
