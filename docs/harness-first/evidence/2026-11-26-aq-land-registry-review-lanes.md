# aq-land: registry-governed review lanes (opus, sonnet)

## Objective

Owner directive 2026-11-26: "why is codex the only reviewer for gate changes? fix that." Root cause: `scripts/ai/aq-land` hardcoded `LANES = {gemini, codex, local}` and never read `config/lane-eligibility-registry.json`, which grants `reviewer` to codex, gemini, opus and sonnet. With the author excluded, local excluded for trust-critical changes and gemini on quota, only codex remained. This slice adds opus and sonnet as review lanes through `delegate-to-claude`, gated by a live registry grant and by author independence.

## Workflow/Session IDs

Headless implementer slice, branch worktree `agent-a6bd219f8235deaa2`. Author lane: Simurg@claude/sonnet-5-5. Not committed; staged for the orchestrator.

## Delegation Decision

Bounded single-script change plus tests, dispatched to a Claude sonnet implementer (Rule 17, explicit model override). The Claude background-worker hash fix is owned by another lane and was not touched.

## Commands Executed

- `python3 scripts/testing/test-aq-land.py` (new class `RegistryLanes`, 10 tests)
- `python3 scripts/testing/test-aq-review-receipt.py`
- `python3 scripts/testing/test-lane-eligibility.py`
- `python3 scripts/testing/test-delegate-to-claude-lifecycle.py` (new foreground output-hash test)
- `python3 -m py_compile`, `ruff check`, `basedpyright` on touched files (aq-land at baseline: 6 ruff, 18 pyright diagnostics, all pre-existing)
- `python3 scripts/governance/check-cross-surface-contract.py`

Design:
- Lanes `opus` (`--model-tier flagship_fallback`) and `sonnet` (`--model-tier balanced`) call `delegate-to-claude --role review --wait` with a 2400 s hard limit and no stall limit (`claude -p` prints only its final answer). A `--budget-check-only` precheck runs first, as for codex.
- Registry reader: `aq-lane-eligibility._load_registry` / `_check`, loaded in-process; honours `AQ_LANE_ELIGIBILITY_REGISTRY`. Gemini, codex, opus and sonnet need a non-expired `reviewer` grant or are skipped with `no live registry grant for reviewer (<status>)`. `local` has no reviewer grant and keeps its existing behaviour (not checked). Registry unreadable: opus and sonnet are skipped (fail closed); gemini, codex and local behave exactly as before.
- Independence: author `claude` (generic) excludes opus and sonnet. A specific model (`sonnet`, `opus`, `haiku`, `fable`, or a `claude-<model>` string) excludes only its own lane; the other Claude lane becomes a same-vendor fallback.
- Default order `gemini,codex,opus,sonnet,local`; same-vendor lanes are always placed after every other remote lane and ahead of local. `AQ_LAND_SAME_VENDOR_FALLBACK=0` disables them.
- Recording: review record carries `same_vendor_fallback: true` and `reviewer_model`; the PR body Review record gets `same_vendor_fallback: true` and `Reviewer-model: <lane>` lines plus a lane note. Reviewed-by is `claude` (the registry agent the receipt verifier binds to).
- Failure-event detail limit raised 240 to 600 chars so the added skip reasons do not truncate lane notes.

## Validation Evidence

- test-aq-land.py: all 8 test classes OK (RegistryLanes: author=claude skips opus+sonnet; author=sonnet with gemini+codex down selects opus with the flag; fallback switch off leaves no lane; expired and missing grants skip with reason; expired codex grant skips codex; unreadable registry gives original three lanes; trust-critical still excludes local; claude budget refusal falls through).
- test-aq-review-receipt.py: 44 OK. test-lane-eligibility.py: all PASS. test-delegate-to-claude-lifecycle.py: 8 OK.
- Receipt hash finding: the foreground (`--wait`) path of `delegate-to-claude` already stamps `output_sha256`, `output_bytes` and `output_recorded_at` in `record_terminal` on `done` (via `lib/registry-update.py stamp`). No fix needed; the new test proves it. The skipped hash is in the background-worker path (`lib/claude-background-worker.sh`), owned by another lane.
- Not run live: no real opus/sonnet review through aq-land; stubs only.

## Rollback Plan

Set `AQ_LAND_SAME_VENDOR_FALLBACK=0` to disable same-vendor review, or pass `--lanes gemini,codex,local` to restore the previous lane set. Full rollback: revert the commit.

## Residual Risk

Same-vendor review (author and reviewer both Anthropic) is weaker independence; it is recorded in the review record and PR body and is last in order before local. With the default author lane `claude`, opus and sonnet are never used: the owner must pass `--author-lane sonnet|opus|haiku` for the new lanes to apply. The receipt `reviewer_lane` is `claude` for both lanes; the reviewer model is only in the aq-land record and PR body, not in the receipt. Registry expiry now also gates gemini and codex (a lapsed grant skips the lane). Canon wording: no canonical rule text names codex/gemini/local as the reviewers (WORKFLOW-CANON.md Rule 18 is lane-agnostic; role-matrix.md lines 165-166 describe per-lane role summaries), so no canon edit was made.

## Hint Feedback

No aq-hints were consulted for this slice; the lane-eligibility registry reader (`aq-lane-eligibility`) was found by searching the repo and reused.
