## Objective
Harden `scripts/ai/aq-land` from real landings: resolve additive manifest conflicts structurally, ride out transient GitHub/network errors while waiting for checks, always show the blocker when tier0 or a commit fails, and let `aq-delegation-registry` see the shared registry from a worktree.

## Workflow/Session IDs
Branch fix/aq-land-hardening, worktree .agents/delegation/worktrees/land-harden. Seen on PRs #720-#730.

## Delegation Decision
Implementer: Claude Sonnet (Rule 17), dispatched by the orchestrator. Date: 2026-11-07. Independent review is still required before merge; this slice is staged, not committed or landed.

## Commands Executed
- python3 scripts/testing/test-aq-land.py
- python3 scripts/testing/test-delegation-dir-resolution.py
- bash scripts/governance/tier0.d/check-ci-test-coverage.sh
- python3 scripts/governance/check-activation-manifest.py
(result lines in the hand-off message; tier0 and run-ci-checks deliberately not run)

## Validation Evidence
- Manifest merge: the tested prototype moved to `scripts/ai/lib/merge_manifests.py`. On a conflicted `git merge` of origin/main, aq-land calls it: `config/ci-checks.json` and `config/activation-manifest.json` merge three-way by structure from the index stages (lists of identified objects by identity, deletions on one side honoured, scalars take the side that changed); `.github/workflows/test.yml` uses `git merge-file --union`. Any other conflicted path, a modify/delete conflict, a true scalar conflict, invalid JSON on a side, a duplicate identity in the result, conflict markers or invalid YAML in the workflow result: nothing is written, the merge is aborted, aq-land stops with the reason. A resolved merge is committed (hooks run) and is not a clean automatic merge, so `merge_only_update` rejects the old review and aq-land requests a fresh one (test: main moves into a manifest conflict during review, gemini is called twice, the PR body names the new head).
- Formatting: `json.dumps(indent=2, ensure_ascii=False) + "\n"` reproduces `config/ci-checks.json` and `config/activation-manifest.json` byte for byte, so no spurious diff; the merge test asserts the output is canonical.
- Transient errors: polling gh calls (`repo view`, protection, `pr view`, post-merge view) retry connection, DNS, timeout and 5xx failures with doubling backoff (`AQ_LAND_RETRY_S`, cap 60 s) until the checks deadline, printing one line per outage; a persistent failure stops with "still failing"; a 404 or other non-transient error stops at once.
- Blocker: tier0 and commit failures print up to five failing lines (FAIL/ERROR/Traceback, else the last lines) plus the path of the full output saved under the landing state directory.
- Registry: `aq-delegation-registry` default registry uses `resolve_delegation_dir` (honours `AQ_DELEGATION_DIR`, else the git main worktree); `--registry` still overrides. Tested from a real git worktree.
- New tests fail on the old code (9 failures and 2 errors in test-aq-land.py, registry assertion in test-delegation-dir-resolution.py); the non-transient-stop test passes on both, as it pins existing behaviour.

## Remaining Risks
- Transient detection is a message regex over gh output; an unlisted wording stops at once (safe, re-run resumes).
- Union merge of the workflow can place both sides' added lines in a valid but unintended order; YAML validity is checked, semantics are left to the fresh review and CI.
- Not run live against GitHub; stubs only.
