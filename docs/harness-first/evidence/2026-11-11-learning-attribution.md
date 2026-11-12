# Evidence: learning-label attribution (2026-11-11)

## Objective
Stop the hybrid coordinator's interaction tracker from treating every non-success outcome or zero rating as agent fault. Caller-declared attribution (`agent_error`, `infrastructure_error`, `infeasible`, `cancelled`, `unknown`) is stored with the raw observation and one sink policy gates reward, penalty, context update, pattern extraction, procedural memory and fine-tuning export. Intent: `.agent/PROJECT-LEARNING-ATTRIBUTION-PRD.md`. Branch `fix/learning-attribution`.

## Workflow/Session IDs
- Implementer: Codex session (implementation of the slice; session ended before its independent review completed).
- Verification and landing prep: Claude sub-agent (Sonnet 5.5), 2026-11-11.
- Plan tracker: `.agents/plans/learning-attribution/tracker.json`.

## Delegation Decision
Implementation was delegated to Codex (cheapest eligible lane, Rule 17). This verification pass ran tests, reviewed the diff and prepared the branch only; it did not commit, push or run tier0. Independent review of the diff is still owed by a non-author lane.

## Commands Executed
```bash
export PYTHONPATH=$PYTHONPATH:$(pwd)/ai-stack:$(pwd)/ai-stack/mcp-servers/hybrid-coordinator
python3 -m pytest ai-stack/mcp-servers/hybrid-coordinator/tests/test_interaction_tracker_attribution.py \
  ai-stack/mcp-servers/hybrid-coordinator/tests/test_mcp_handlers_dispatch.py -m "not integration" -q
git fetch origin && git merge refs/remotes/origin/main   # fast-forward to 5a97e5be0
python3 scripts/ai/aq-pm-tracker .agents/plans/learning-attribution --check
bash scripts/testing/check-harness-first-evidence-template.sh
```
Invocation mirrors the `unit-tests (hybrid-coordinator)` job in `.github/workflows/tests.yml` (same PYTHONPATH and `-m "not integration"`), narrowed to the two files.

## Validation Evidence
- Attribution and dispatch tests: 44 passed (before and after merging origin/main).
- `live_source_manifest` in `scripts/testing/fixtures/local-inference-l2b-payload-golden.json`: neither `interaction_tracker.py` nor `mcp_handlers.py` is pinned, so no hash refresh.
- Not run: tier0, full hybrid-coordinator suite, live MCP path.

## Rollback Plan
Revert the commit. Stored `attribution`, `attribution_supplied` and `learning_eligible` payload fields are additive; records lacking `learning_eligible` are excluded from fine-tuning export after this change, so a revert restores the previous export behavior.

## Residual Risk
- Attribution is caller-declared and unverified. It is not independent provenance; authenticated attribution and forged-spool integrity are deferred (see PRD).
- Legacy callers that omit attribution and report `success`/`partial` still count as positive learning, with no verification of the success claim.
- Historical interactions lack `learning_eligible` and drop out of the fine-tuning dataset.
- The coordinator runs from Nix-pinned source: a rebuild (`aq-deploy-current`, owner-run) is required before this takes effect. Runtime activation is not done.
- Independent review pending.

## Hint Feedback
No aq-hints query was made in this verification pass; no hint feedback to record.
