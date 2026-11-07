## Objective
Place each gate where it can do its job (slice S2 of delivery-loop-simplification, Decision 6). Local `tier0 --pre-commit` becomes deterministic, offline, bounded and relevant to the staged change; pre-push keeps push safety only; CI keeps the exhaustive suites; live-state checks move to the stages that can run them (`--pre-deploy` via aq-deploy-current, `--maintenance`, ai-stack-health-monitor).

## Workflow/Session IDs
Slice S2, branch fix/gates-placement (from origin/main 26c8dcfe5). Design: .agents/plans/delivery-loop-simplification/DESIGN.md. Backlog: FACTORY-DELIVERY-LOOP-TOO-HEAVY, QA-MACHINE-MODE-EMPTY-OUTPUT, recurring QA 0.10.66 health-monitor alert.

## Delegation Decision
Implementer: Claude Sonnet (Rule 17). Orchestrator: claude-opus. Date: 2026-11-06. Inventory of every check: .agents/delegation/outputs/s2-gates/inventory.tsv.

## Commands Executed
- Baseline: `tier0-validation-gate.sh --pre-commit` with a doc staged: rc=0, 593 s (load ~8), QA phase 0 alone about 368 s.
- Reproduced 0.10.66 under the monitor's sandbox with `systemd-run --user -p NoNewPrivileges=true -p PrivateTmp=true -p ProtectHome=read-only -p ProtectSystem=strict` and no XDG_RUNTIME_DIR.
- After: see Validation Evidence.

## Validation Evidence
Placement by criteria (full table in inventory.tsv):

| Check | Was | Now | Owner that runs it |
|---|---|---|---|
| QA phase 0 (216 checks, 368 s) | pre-commit | --pre-deploy, --maintenance, --ci | aq-deploy-current step 9 (`aq-qa 0 --machine`, AQ_CONFINE_REQUIRE_CONTEXT=1); ai-stack-health-monitor every 15 min; CI parity-scorecard runs `tier0 --ci` (host-only checks demoted to SKIP) |
| 18 harness regression suites (60 s cap) | every commit | code/config staged only, 180 s cap; always at --ci | CI test.yml manifest-tests tests-* groups run all 18 |
| script header standards `--all` (28 s) | pre-commit | staged scripts at pre-commit, `--all` elsewhere | pre-push quick-deploy-lint (changed range), tier0 --ci |
| config-directory-lint, canon determinism | every commit | when config/ or canon inputs are staged | tier0 --ci, tests group for canon, tier0.d/check-canon-drift always |
| pre-push ci-merge-parity + run-ci-checks --changed | pre-push | CI; opt-in `PRE_PUSH_CI_PARITY=1` | test.yml manifest-tests, syntax and other jobs |
| pre-push nix eval | pre-push | CI; same opt-in | nix-build.yml (flake check, toplevel build), test.yml nix eval |
| pre-push sync, quick-deploy-lint | pre-push | pre-push (kept) | quick-deploy-lint is the sole owner of 14 scripts that ci-checks.json ci_exempt lists as "run locally by pre-push" |
| owner-acceptance (check-pm-tracker, fetches origin/main, fail-closed) | pre-commit | pre-commit keeps the offline subset (pinned digest, strict parse, allowlist subset of baseline); full check at pre-push, CI (`tier0 --ci`), --pre-deploy, --maintenance | unreachable origin is still a FAIL, shown by a seeded test; never passes offline |
| pre-push identity, pushed-range gitleaks, conflict probe | partly | pre-push (new or split out) | CI cannot rewrite pushed history or see a secret before publication |

Gap found and closed: manifest check `workflow-failure-masks` (check-workflow-masks.py) was referenced by no workflow and ran only through pre-push `--changed`. Removing the CI repeat from pre-push would have left it unrun, so test.yml now runs it (`--only workflow-failure-masks`).

Root causes:
- Flaky 0.16.2: a live HTTP probe missing from tier0 LIVE_SERVICE_CLASS_IDS; added.
- 0.10.54 and the 30 s caps: phase 0 hard-coded subprocess timeouts; they now scale 1x to 4x with load (AQ_QA_TIMEOUT_SCALE overrides).
- 0.10.66 false alert: the monitor's unit has no XDG_RUNTIME_DIR. Launcher resolves it (host_scope_env) but test-aq-confine.py's own `systemctl --user show` calls did not, so only the cgroup-scope assertion failed (211 pass, 1 fail). With the unit's four sandbox properties and XDG set it passes 212/0; unset, it fails the same way every time. Fixed at the producer (test uses the launcher's env). The NoNewPrivileges/ProtectHome sandbox is not the cause. The check also now skips with an explicit reason when the user manager is unreachable, and fails (never skips) under AQ_CONFINE_REQUIRE_CONTEXT=1, which tier0 --pre-deploy and aq-deploy-current set. CI confine-tests.yml runs the suite unchanged.
- `aq-qa 0 --machine` empty output: the machine reporter printed FAIL rows only, so a green run printed nothing. It now prints failures with reasons and always a `SUMMARY phase=N P passed · F failed · S skipped` line. aq-deploy-current treats a missing SUMMARY as failure.
- tier0 documented `--ci` (used by harness-runner) and `--maintenance` but parsed neither. Both are now parsed; `--ci` keeps MODE=--pre-commit but runs phase 0 so CI keeps its coverage.

Result lines. FINAL = run on the final staged tree (after the check-pm-tracker.sh and pre-push edits); EARLIER = run before the last edits of unrelated files, with no later change to what they test.
- FINAL: `tier0-validation-gate.sh --pre-commit`, real code staged, load 16.3: `rc=0 elapsed=264s`, `[tier0] Passed: 65`, `[tier0] Failed: 0`, `[tier0] OK: All Tier 0 gates passed`. Slow gates: harness suites 100s, focused CI checks 68s, config lint 14s. QA phase 0 and canon determinism printed explicit SKIP lines.
- FINAL: `test-tier0d-gate-mutation.py`: `gate-mutation: 36/36 passed, 0 skipped, 0 failed; 14 gates mutated here, 9 covered elsewhere`.
- FINAL (after the pm-tracker edit): `test-tier0-gate-placement.py`: `SUMMARY: 0 failed`, doc-only `tier0 --pre-commit` 52s at load about 10, real 2m34s; includes the seeded owner-acceptance cases.
- FINAL: `run-ci-checks.sh --changed --base refs/remotes/origin/main`: `27 pass, 0 fail, 0 warn`.
- FINAL: `check-ci-test-coverage.sh`: `PASS (760 tests: 610 declared, 150 exempt)`.
- FINAL: `test-pm-tracker-owner-acceptance.py`: `Ran 54 tests ... OK`; `test-aq-confine.py`: `212 checks ran, 0 failed, 0 behavioral groups skipped`.
- EARLIER baseline: `tier0 --pre-commit` doc staged, unchanged tree: `rc=0 elapsed=593s load=8.31`.

## Rollback Plan
Revert the commit. No data or config migration. No Nix change, so no rebuild; the monitor and aq-qa run from the repo checkout, which the owner syncs with the usual checkout update.

## Residual Risk
A code commit no longer gets QA phase 0 locally; a regression only phase 0 sees (not tier0.d, focused checks, CI) is found at the next monitor run (15 min), at aq-deploy-current, or in CI. Skipped gates are explicit SKIP lines naming their owners. Pre-push no longer repeats CI suites, so a CI-only failure costs one CI round; PRE_PUSH_CI_PARITY=1 restores the old behavior. Doc/receipt-only commits skip the 18 code suites (CI still runs them). Pre-existing: manifest check gitleaks-tree is run in CI as an inline gitleaks step with the same config, not through ci-gitleaks.sh.

## Hint Feedback
No hints were consulted.

## Review Round 1 Fixes (Codex FAIL: 1 HIGH, 1 MEDIUM)
- HIGH, containment skip hid a failure under the monitor: `scripts/health/ai-stack-health-monitor.py` now sets `AQ_CONFINE_REQUIRE_CONTEXT=1` for its aq-qa subprocess, and `tier0 --maintenance` sets it as well (with `--pre-deploy`). An unreachable user manager is now a failed monitor result. No Nix unit change, so no rebuild; the monitor runs from the repo checkout. The skip remains for ad-hoc interactive runs only.
- MEDIUM, pre-push read only the first ref: the hook now consumes every update line; deletions are skipped individually and each non-deletion range gets identity, secret, conflict and lint checks. The owner-acceptance check runs once when anything is published.
- New tests in test-tier0-gate-placement.py: `health monitor runs aq-qa with AQ_CONFINE_REQUIRE_CONTEXT=1`, `unreachable user manager under the monitor environment is a failed monitor result`, `pre-push rejects a bad publish that follows a delete`, `pre-push rejects a bad second ref after a clean first ref`, plus accept cases (clean publish, delete-only).
- Regression check: run against the previous staged versions of the hook and monitor, the four rejection tests FAIL (monitor env was None, the unreachable case read `skip`, both pre-push cases exited 0); on the fixed tree they pass.
- Healthy case under the monitor's real sandbox (`systemd-run --user` with NoNewPrivileges, PrivateTmp, ProtectHome=read-only, ProtectSystem=strict, XDG_RUNTIME_DIR unset, AQ_CONFINE_REQUIRE_CONTEXT=1): `RESULT PASS` for 0.10.66.
- FINAL-tree result lines after these fixes: `test-tier0-gate-placement.py` `SUMMARY: 0 failed` (doc-only tier0 --pre-commit 46s, total 2m19s); `test-tier0d-gate-mutation.py` `36/36 passed, 0 skipped, 0 failed`; `check-ci-test-coverage.sh` `PASS (760 tests: 610 declared, 150 exempt)`; `test-hook-git-env-isolation.py` `PASS`; `test-pm-tracker-owner-acceptance.py` `OK`; `run-ci-checks.sh --changed --base refs/remotes/origin/main` `27 pass, 0 fail, 0 warn`.

## Review Round 2: review-receipts branch (S1 landing)
- `.githooks/pre-push`: an update whose remote ref is exactly `refs/heads/review-receipts` (no pattern) gets identity and secret scan only, on its own commits (range `<remote sha>..<head>` or `<head> --not --remotes`; never origin/main). No conflict probe, lint, parity, owner check; a receipts-only push also skips the global upstream sync check (the working branch is irrelevant). Any other ref in the same push still gets all checks; a mixed push still runs sync.
- Tests (test-tier0-gate-placement.py): root commit by `aq-review-receipt <aq-review-receipt@noreply.invalid>` to review-receipts passes from a branch behind its upstream; the same commit to another branch fails the conflict probe; a secret in a receipts commit is caught (gitleaks); a receipts push plus a bad branch fails; a lookalike ref (`review-receipts-x`) gets full checks. Against the previous hook the receipts-accept and mixed/secret cases fail.
- FINAL-tree result lines: placement test `SUMMARY: 0 failed` (doc-only tier0 --pre-commit 43s, total 2m16s); mutation `36/36 passed, 0 skipped, 0 failed`; `check-ci-test-coverage.sh` `PASS (760 tests: 610 declared, 150 exempt)`; `test-hook-git-env-isolation.py` PASS; `test-pm-tracker-owner-acceptance.py` OK; `run-ci-checks.sh --changed --base refs/remotes/origin/main` `27 pass, 0 fail, 0 warn`.

## Review Round 3 Fixes (verified review findings)
- HIGH, code treated as non-code: `TIER0_STAGED_NONCODE_ONLY` (tier0-validation-gate.sh, start-up block) is now set only when every staged path is under docs/, .agent/, .agents/ or a root `*.md` AND none ends `.py .sh .nix .yml .yaml`, none is under `*/scripts/`, and none has an executable mode (old or new mode 100755). It is the only caller of that pattern in the file (grep for the docs/.agent/.agents prefixes found no other). Test: a staged `.agent/skills/x/scripts/a.py` runs the harness regression suites (no SKIP); the doc-only case still skips.
- MEDIUM, delete-only push: the pre-push sync check now runs only for a manual run with no stdin (`PUSH_SEEN == 0`) or when a non-receipts ref is published. A delete-only push publishes nothing and skips sync. Tests: a delete-only push from a branch behind its upstream passes; an empty stdin still runs the sync check and is refused when behind.
- MEDIUM, conflict probe: a branch that does not merge cleanly into origin/main now produces a `WARNING` and does not block (GitHub reports conflicts on the PR; stacked branches are legitimate). Stage-ownership comment updated. Test changed from "fails the conflict probe" to "only warns"; the lookalike-ref test now uses a bad-identity commit so it still proves the full checks run on a lookalike ref.
- Attestation patch from the closed PR applied cleanly with `git apply --index` (26 lines in `.agent/ACTIVATION-AUDIT.md`).
- Not acted on (checked false): missing `pull-requests: read` permission; `tier0 --ci` running nowhere (runs via tests.yml parity-scorecard-gate); forged owner acceptance reaching main; `0 failed` regex matching `10 failed`.
