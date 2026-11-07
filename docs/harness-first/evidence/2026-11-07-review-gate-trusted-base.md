## Objective
Close the trust gap in the required `review-disposition` check: it ran on `pull_request`, so the workflow and the checker scripts came from the PR's own merge ref and a PR could edit the code that judges it. Plus three follow-ups: retire the `aq-land` activation deferral, add `--rev` to `aq-deploy-current`, and wire `check-flake-age.sh` into `--maintenance`.

## Workflow/Session IDs
Branch fix/review-gate-trusted-base. Backlog: GATE-FOLLOWUP. Depends on PR #720 (first real `aq-land` landing).

## Delegation Decision
Implementer: Claude Sonnet (Rule 17), dispatched by the orchestrator. Date: 2026-11-07. Review by an independent lane is still required before merge.

## Commands Executed
- python3 scripts/testing/test-review-disposition-check.py
- python3 scripts/testing/test-aq-deploy-current-rev.py
- python3 scripts/testing/test-aq-update.py
- bash scripts/testing/test-check-flake-age.sh
- python3 scripts/testing/test-tier0d-gate-mutation.py
- bash scripts/governance/tier0.d/check-ci-test-coverage.sh
- python3 scripts/governance/check-workflow-masks.py
- python3 scripts/governance/check-activation-manifest.py
(result lines in the hand-off message)

## Validation Evidence
Design (GitHub rules): a `pull_request` workflow's definition comes from the PR merge ref, so a PR can rewrite it. `pull_request_target` runs the definition and the default checkout from the base branch, but carries a token that can be write-scoped and must never execute PR code.
- `.github/workflows/review-disposition.yml` now triggers only on `pull_request_target` (opened, edited, synchronize, reopened), `permissions: contents: read, pull-requests: read`, one action (`actions/checkout`, pinned, no `ref:`/`repository:`, `persist-credentials: false`, `fetch-depth: 0`), no secrets beyond the Actions token. Both run steps execute `scripts/governance/*.py` from the base checkout.
- No PR code executes: the checker fetches `refs/pull/<N>/head` as git objects for `rev-parse`, `cat-file`, `merge-tree`, `show` only (no checkout, hooks or scripts). Recorded in a comment in the workflow.
- `pull_request_review` is dropped: GitHub runs that event from the PR merge ref, which would reopen the hole. The checker reads the PR body and the `review-receipts` branch, never GitHub reviews, so nothing is lost. `edited` covers body edits (the re-trigger that matters).
- Checker under `pull_request_target`: the payload carries the same `pull_request.number`, `pull_request.head.sha`, `repository.full_name` fields; the checker reads live state from the API and compares the payload head with the live head (stale run). Tested with a pull_request_target-shaped payload (fork head repo, extra fields). The merge rule fetches `main` and `+refs/pull/<N>/head` itself; the public repo allows that anonymously, so dropping persisted credentials costs nothing. If the repo became private those fetches would need a credential and the check would fail closed.
- Static test (`WorkflowTrustBoundary` in test-review-disposition-check.py): trigger is exactly `pull_request_target`; no `github.event.pull_request.head`, `head_ref`, `refs/pull`, `refs/merge`; no `ref:`/`repository:` override; run steps only `python3 scripts/governance/<x>.py "$GITHUB_EVENT_PATH"`; no `./`, `bash`, `source`, `git checkout|merge|pull`; only actions/checkout; persist-credentials false; every permission read/none; no secrets. The pre-change workflow (pull_request, pull_request_review, no persist-credentials) fails it.
- `check-workflow-masks.py` passes unchanged; no linter in this repo flags `pull_request_target` for this workflow, so no exemption was added. (The factory-kit `ci_policy.py` rule applies to generated kit workflows, not this file.)
- `config/activation-manifest.json`: `aq-land` deferral removed. live_caller `scripts/maintenance/aq-update` (it invokes `aq-land` as its land stage); health signal `scripts/ai/aq-land:cp_path` (the per-landing checkpoint); observed_by names the checkpoint and receipt files. No dashboard panel yet, stated in the entry.
- `scripts/maintenance/aq-deploy-current --rev <40-hex>`: after the ff-only pull, exits 1 with nothing built unless HEAD equals the revision; a malformed or empty value exits 2 (an empty value is not treated as absent). No flag: unchanged. `aq-update` passes its verified target. Tests: test-aq-deploy-current-rev.py (real script in a throwaway checkout with a local bare origin; moved main is refused, exact match proceeds, no-flag unchanged, bad values rejected) and test-aq-update.py asserts the deployer receives `--rev <synced head>`. Registered under the `tests-aq` group in config/ci-checks.json.
- `scripts/governance/tier0.d/check-flake-age.sh`: runs the 48h input-age guard, failing only under `--maintenance`, skipping (with a printed line) in every other mode, per the Rule 19 gate corollary. Live now: it fails under `--maintenance` with 3 inputs younger than 48h (enable-container-tests, nixified-ai, nixos-hardware); that is the real signal, not a defect. Tested in test-check-flake-age.sh with a stubbed guard; test-tier0d-gate-mutation.py lists it as covered there.
- `gate_deploy_batch_size` stays advisory: sweep-gates.py has no exemption mechanism for tier0 functions (only `ci_exempt` for scripts), so no entry was added and nothing was changed. It remains a CANNOT_FAIL finding in the sweep.

## Bootstrap (transition): Option A, two-step
Main still has the old `pull_request` workflow, and `pull_request_target` uses main's copy, so this PR's own new workflow cannot report for it. This PR therefore keeps `pull_request` (same event types) beside `pull_request_target`: the `pull_request` run uses this PR's merge-ref copy of the same job, named exactly `review-disposition`, with the same read-only `contents`/`pull-requests` permissions and no explicit head checkout (default merge-ref checkout only). That run is the old, PR-modifiable path, so it is NOT a trust upgrade for this PR; it exists only so the required check reports. `pull_request_review` stays out: both remaining triggers fire on opened/edited/synchronize/reopened, so every PR still gets a check run; dropping the review event loses nothing because the checker reads the body and receipts branch, not reviews.
The hole stays open until the follow-up PR, which removes the `pull_request` trigger and flips `TARGET_ONLY` in the static test. Prepared, not applied: `.agents/delegation/outputs/landing/review-target-only.patch` (apply with `patch -p1`; verified with a dry run, and the test file passes after applying it in a scratch copy). After this PR merges, later PRs get both runs until the follow-up merges; the target run is the trusted one.
Static test in this PR: `pull_request_target` present, `pull_request` tolerated only while `TARGET_ONLY = False`, `pull_request_review` or any other trigger rejected, no head/merge ref or `ref:` checkout, no write permission, `persist-credentials: false`, job name `review-disposition`. A test also asserts the final form rejects a `pull_request` trigger.
Unverified: (1) whether GitHub's required-checks rollup fails when one of two same-named check runs fails during the two-trigger window; (2) check-run head binding below.
From GitHub's documented behaviour (not verified live here): checks created by a `pull_request_target` workflow are attached to the PR's head commit sha and appear on the PR, so a required context named `review-disposition` is satisfied by it. Evidence that is documented: required checks match on the check/job name against the PR head sha, and `pull_request_target` workflows are commonly used as required checks. The first real PR after merge is the proof.

## Rollback Plan
Revert the commit. The required check name is unchanged, so branch protection needs no edit; reverting restores the `pull_request` workflow. The other changes are independent and revert cleanly.

## Residual Risk
The checker is now judged by main's copy, so a change to it takes effect only after it merges, and anyone who can push to main or edit branch protection can still change the rules. Identity stays declarative and receipts detection-grade (WR-REVIEW-1). Not verified: a live run under `pull_request_target`; it can only happen after merge. The exact proof is the `review-disposition` check on the first PR opened or pushed after this merges (check run name `review-disposition`, event `pull_request_target`, checkout sha = main tip), and a test PR that edits `scripts/governance/check-review-disposition.py` to `return 0` must still fail it.

## Hint Feedback
No hints were consulted.
