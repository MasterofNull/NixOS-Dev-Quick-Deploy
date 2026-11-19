# aq-land merge freshness (slice G0) 2026-11-19

## Objective
Stop a PR from merging on CI results produced against an older main. Root cause: main protection has `required_status_checks.strict=false` with only `review-disposition` required, and `aq-land` `wait_and_merge()` pinned only the PR head (`--match-head-commit`); the resumed `settled()` path reaches the same function and had no main-freshness check. Owner decision 4 (greenlight-gating DESIGN, Revision 3): build G0 in aq-land, leave GitHub strict off, log the extra CI wait per merge, reassess after a sample.

## Workflow/Session IDs
Slice G0, branch fix/aq-land-merge-freshness, plan `.agents/plans/greenlight-gating-20261119/DESIGN.md` (Revision 3).

## Delegation Decision
Bounded single-file change plus tests, done by a Sonnet sub-agent under orchestrator dispatch (Rule 17). No review or merge performed by the implementer.

## Commands Executed
- `python3 scripts/testing/test-aq-land.py MergeFreshness` (4 new tests, stubbed gh and a local bare origin)
- `python3 scripts/testing/test-aq-land.py`, `test-aq-land-outcome.py`, `test-aq-land-pre-review-gate.py`
- `scripts/governance/tier0-validation-gate.sh --pre-commit`

## Validation Evidence
Before merging (shared by the normal and resumed paths) `update_if_behind()` fetches origin, reads `mergeStateStatus,baseRefOid,headRefOid`, and treats the PR as behind when status is BEHIND, the base differs from origin/main, or head does not contain origin/main. If behind it runs `gh pr update-branch`, waits for the head to change, then reuses the existing review binding: the new head must satisfy `review_valid()` (a clean automatic merge of main onto the reviewed head, the same rule used when aq-land merges main locally); otherwise STOP and a fresh review is needed. No receipt is minted or edited. The local branch fast-forwards to the new head and the existing check loop re-waits CI on it. Rounds are bounded by `--max-updates` (env `AQ_LAND_MAX_UPDATES`, default 3); exhaustion stops with "still behind origin/main after N update(s)" and no merge. One JSON line per merge goes to `<delegation>/outputs/aq-land/merge-freshness.jsonl`: `{pr, at, was_behind, updates, extra_ci_wait_s, merged}` (a bound-exhausted stop logs merged=false).
Tests: up-to-date PR merges with no update; BEHIND PR updates, re-waits, merges; resumed settled() path updates and keeps its single review; bound exhausted stops without merge. Existing aq-land suites unchanged and passing.
Unverified: real `gh pr update-branch` behavior (stubbed); GitHub may report mergeStateStatus CLEAN while behind under strict=false, which is why the git ancestry check is the primary signal.

## Rollback Plan
Revert the commit. The jsonl log is append-only and harmless. `--max-updates 0` makes any behind PR stop instead of updating.

## Residual Risk
Each update costs one extra CI cycle and can race with other merges (bounded by the retry option). An update-branch merge commit that is not a clean merge of main forces a new review. The sample in merge-freshness.jsonl is what decides strict branch protection.

## Hint Feedback
aq-hints not consulted; the design and aq-land source were read directly. No hint feedback to submit.
