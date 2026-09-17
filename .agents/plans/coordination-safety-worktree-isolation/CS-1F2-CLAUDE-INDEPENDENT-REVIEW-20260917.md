# CS-1F2 (coordination-safety corrective) — Claude independent review

Reviewer: Claude Opus 4.8 (independent, non-author of CS-1F2; I authored/landed the original CS-1 e8a905e8,
so I'm well-placed to verify the corrective). For: Codex (owner-appointed integrator). Subject reviewed =
current working-tree CS-1F2 implementation (NOT hash-bound yet — see "blocker on exact-subject binding").

## Verdict: REQUEST_REVISION (one real blocker + one doc nit) — do NOT commit yet

The corrective is substantively SOUND and correctly fixes the three audit findings on my CS-1:
- **Validated paths/branch/worktree** — `wt_validate` resolves real paths (`pwd -P`, symlink-safe), asserts
  `wt == repo/.agents/delegation/worktrees/<task_id>` and `!= repo` (rejects shared + path-escape), checks the
  worktree is registered (`git worktree list`) and on branch `delegate/<task_id>`. Called before handback. ✓
- **Fail-closed for editing** — `--shared` on an editing/agent dispatch `die`s ("shared editing is not
  authorized"); `wt_create` failure `die`s ("refusing editing dispatch") — no silent shared fallback. ✓
- **No forced teardown; retention on all outcomes** — `wt_teardown` is now a no-op; worktree + private branch
  + patch retained on success AND failure. ✓
- **Handback captures committed + uncommitted work from the immutable base** — `refs/delegate-base/<id>` is
  pinned at create; handback diffs `base..HEAD` (`--binary --full-index`), verifies the commit, and returns
  failure on any partial step (add/commit/export). ✓
- **Fixture coverage** is thorough: shared-editing denied, path-escape/other-lane/wrong-branch rejected,
  immutable-base-doesn't-move, committed+uncommitted+new+binary export, retention-on-export-failure,
  foreground/background failure propagation. ✓

### BLOCKER — the hermetic fixture FAILS (so the PRD's own gate isn't met)
`python3 scripts/testing/test-worktree-isolation.py` → `AssertionError: foreground must save its session`
(line 196), reproducible hermetically (all deps stubbed; no external service). Assertions 191–194 pass
(failure IS propagated: registry `status: failed` + `terminal_reason: worktree_handback_failed` + audit
`error_resolution`), but the foreground worktree-handback-failure path does not save a session:
`record_worktree_handback_failure()` calls `_update_registry(...)` + `audit_event_end(...)` but NOT
`audit_save_session(...)`, which the success path does and the fixture (+ the "retain operator failure
visibility" criterion) requires.
**Bounded fix:** add `audit_save_session "local-${MODE}"/"safe" "$task_id" "$PROMPT" "$OUTPUT_FILE"` (matching
the success/normal-failure branches) to the foreground handback-failure path, for BOTH delegate scripts (the
fixture exercises CODEX and LOCAL). Then the fixture must pass before commit.

### Doc nit (fix in the same batch)
`scripts/ai/lib/worktree-isolation.sh` header comment (≈line 32) still says `wt_create` returns 1 "so the
caller can fall back to the shared checkout" — stale: the callers now fail-closed on editing. Update the
comment to match (isolation failure refuses an editing dispatch; it does not fall back).

## Blocker on exact-subject binding (integration coordination)
I could only content-review, not exact-subject-bind, because the shared checkout is mid-flux: `delegate-to-*`
show `MM` (staged ≠ working) and the CS-1F2 files are staged together with unrelated concerns
(local-latency PRD, dashboard.js, _aq-qa-bash, response-contract task_registry). For the final bound
acceptance, Codex (integrator) should freeze the **exact CS-1F2 subject** — stage precisely
{worktree-isolation.sh, delegate-to-codex, delegate-to-local, test-worktree-isolation.py, phase0.py+_aq-qa-bash
QA registration, PROJECT-COORDINATION-SAFETY-CORRECTIVE-PRD.md, tracker.json} with no `MM` divergence and
separate from the latency-F1 slice — and I'll bind a PASS to that exact `git diff --cached` sha once the
above fix lands and the fixture is green.

## Summary for the integrator
CS-1F2 is one bounded fix (session-save on the foreground handback-failure path) + one comment update away
from commit-ready. The core corrective logic is correct. Fix → fixture green → freeze exact subject → I bind
the acceptance → you (integrator) commit.
