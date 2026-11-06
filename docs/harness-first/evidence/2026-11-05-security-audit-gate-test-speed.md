## Objective
Make scripts/testing/test-security-audit-gate.sh fast and hermetic. It took about 67 s alone and up to 123 s under load, exceeding the 120 s per-test timeout in scripts/testing/run-test-group.py (rc=124) and blocking pushes that run tests-misc-s-z. No assertion or case was removed or weakened; the runner timeout is unchanged and the test is not exempted.

## Workflow/Session IDs
Backlog item TEST-SECURITY-AUDIT-GATE-NEAR-TIMEOUT. Branch fix/security-audit-gate-test-speed.

## Delegation Decision
Implementer: Claude Sonnet (Rule 17). Date: 2026-11-05. Slice bounded to scripts/testing/test-security-audit-gate.sh.

## Commands Executed
- Profiled with bash -x and an EPOCHREALTIME PS4, summing time per source line. About 85 invocations of security-audit.sh run; the ~25 before line ~88 inherited the real DASHBOARD_SCAN_SCRIPT and SECRETS_ROTATION_PLAN_SCRIPT (a live 127.0.0.1 dashboard curl plus a secrets-tree walk). Only the cases after that point stubbed them. The 48-case scanner x failure-mode table then ran serially, each case about 0.2 s idle and 0.6-2 s under load (fork-heavy jq pipeline).
- Cause 1: ok-dashboard.sh / ok-secrets.sh stubs are now created at the top and exported as the default DASHBOARD_SCAN_SCRIPT / SECRETS_ROTATION_PLAN_SCRIPT. Previously-stubbed later sections keep their explicit overrides, and the former `unset` now restores the stubs. The first ~25 cases assert only on blocking/warning text and exit codes of the npm and pip backends, which the dashboard and secrets scanners do not influence.
- Cause 2: the 48 table cases each use their own $T/tc-<scanner>-<mode> directory, so they now run concurrently (8 at a time, TABLE_JOBS to override). Each writes a verdict file, and results are checked and printed in the original order. The same assertion runs on every case, and any missing verdict fails the test.
- python3 scripts/testing/run-test-group.py tests-misc-s-z
- ./scripts/governance/run-ci-checks.sh --changed --base refs/remotes/origin/main

## Validation Evidence
- Before: about 108 s wall, measured at load average 15 (same machine, same time window as the after run); 115.9 s under bash -x.
- After, two runs: 20.4 s and 19.8 s at load average 9-10 from unrelated processes (a 16-core host that never went idle during this slice).
- tests-misc-s-z: "run-test-group tests-misc-s-z: 81/81 passed".
- run-ci-checks: "run-ci-checks: 11 pass, 0 fail, 0 warn" (tests-misc-s-z 115.4 s of the group, run in parallel with the other checks).
- Negative proof: in a scratch copy (not in the worktree), the final `exit 3` on degraded coverage in security-audit.sh was disabled. The test then fails: "FAIL: degraded did not fail unit-mode run rc=0", exit 1. With that assertion also removed from the scratch test, the next one fails: "FAIL: missing npm did not exit 3 rc=0".
- security-audit.sh is exercised for real in every case. Only its external backends (pip-audit, npm, dashboard scan, secrets plan) are stubbed, as they already were in every case that asserts on them.

## Rollback Plan
git revert the commit; the test returns to its previous serial, unstubbed form.

## Residual Risk
The real dashboard and secrets scanners are no longer invoked by the early cases. No case in this file asserted on them; they have their own tests. Wall time still scales with host load because each audit run forks many jq processes; remaining sequential cases (about 35 runs) could be parallelised further if load rises.

## Hint Feedback
None recorded.
