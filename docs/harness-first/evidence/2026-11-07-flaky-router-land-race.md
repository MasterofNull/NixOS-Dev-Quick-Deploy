# 2026-11-07 flaky-router-land-race

## Objective
Fix three small issues: (1) the router "load-bearing" concurrent-reclaim check flaked on CI (PR #723) because it asserted that a timing race WILL occur; (2) `aq-land` lost a 10-minute review when main moved and the branch tracked origin/main, because pre-push read main as the branch's upstream; (3) tier0's focused-CI gate hid real failures behind `>/dev/null 2>&1` ("failed" was misread as load).

## Workflow/Session IDs
Branch fix/flaky-router-and-land-race, date 2026-11-07. Staged only; not committed, tier0 not run.

## Delegation Decision
Orchestrator: claude-opus. Implementer: Claude Sonnet (Rule 17, bounded slice with checkable tests).

## Commands Executed
- `nice python3 scripts/testing/test-agent-agnostic-router.py` x30 with four busy-loop CPU hogs running
- `python3 scripts/testing/test-aq-land.py` on new and on the old (HEAD) `scripts/ai/aq-land`
- `bash scripts/testing/test-tier0-focused-ci-output.sh`
- `bash scripts/governance/tier0.d/check-ci-test-coverage.sh`

## Changes
1. `scripts/testing/test-agent-agnostic-router.py`: the negative control now forces the interleaving with events (a wrapper on `_load_claim` parks straggler B after its reclaim re-check read until racer A has run a full acquire). Lock removed: B renames A's fresh claim away and both win, every time. Lock present: B parks holding the lock, A blocks, exactly one winner. The 40x8 stress test of the locked path is unchanged. No product-code seam added; the wrapper patches an existing module function.
2. `scripts/ai/aq-land`: before pushing, if the branch's upstream is not `origin/<branch>`, `git branch --unset-upstream`; the existing `push -u` then sets the right one. `.githooks/pre-push` and its env var untouched.
3. `scripts/governance/tier0-validation-gate.sh`: `gate_focused_ci_checks` captures output to a temp file and on failure prints each `[focused-ci] FAIL` line with up to 3 preceding lines (`print_focused_ci_failures`); pass/fail behaviour unchanged; temp file removed on both paths. New test `scripts/testing/test-tier0-focused-ci-output.sh`, registered as check `tier0-focused-ci-output-test` in `config/ci-checks.json` and `.github/workflows/test.yml`.

## Validation Evidence
- RESULT router test under load: 30/30 passes (`nice`, 4 parallel busy loops). Load-bearing lines PASS: unlocked forced interleaving gives 2 holders, locked gives 1.
- RESULT test-aq-land.py new code: 38 tests OK (includes new `test_push_survives_main_moving_when_branch_tracks_origin_main`; existing `test_main_moves_clean_merge_keeps_review` still passes, so the clean-merge-after-move path and review reuse work).
- RESULT test-aq-land.py old aq-land: 38 tests, FAILED (failures=1), the new test: `STOP push: ... pre-push: behind origin/main by 1`.
- RESULT test-tier0-focused-ci-output.sh: PASS.
- RESULT check-ci-test-coverage.sh: PASS (767 tests: 618 declared, 149 exempt).

## Risks/Blockers
- The land test uses a stand-in pre-push hook that models the real sync check (fetch upstream, reject if behind) and advances main once just before it; the real `.githooks/pre-push` was not run in the test.
- In aq-land's own loop, a move during the review is normally absorbed by the merge-after-move path; the failing window is a move after the last `main_advanced` check, which is what the test forces.
- Not verified: a real-remote `aq-land` run; the full CI workflow run of the new check.

## Other flake candidates (not changed)
Wall-clock assertions: `test-aidb-library-catalog-sync-fetch.py:173`, `test-deployment-monitoring-alerting-e2e.py:362,417,522`, `test-context-store-performance.py:71,88,116` (0.05s/0.1s/0.01s, the tightest), `test-run-event-metrics.py:283`, `test-local-delegation-artifact.py:458` (1.0s), `test-timeout-guard-behavior.py:274`. Timing-dependent signal test: `test-qa-provider-probe-adoption.py:617`.

## Other tier0 gates that swallow all output on failure (not changed)
`gate_script_headers` (~line 860), `gate_config_dir_lint`, `gate_unattended_sudo_readiness`, `gate_canon_compiler_determinism`, `gate_evidence_collector` (each `>/dev/null 2>&1`, message only).
