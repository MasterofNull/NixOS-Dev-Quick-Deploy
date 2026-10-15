# aq-confine W2-S3 prerequisites evidence (2026-10-15)

## Objective
Close the four S2a code-review blockers for enabling W2-S3: (1) real memory/process bound via a transient systemd user scope, (2) CI job `confine-tests.yml`, (3) tier0/phase0 wiring of `AQ_CONFINE_REQUIRE=1`, (4) aq-health-spider listing of aq-confine high alerts. Review: `aq-confine-S2a-CODE-REVIEW.md`; design `.agents/plans/sota-rounding/aq-confine-DESIGN.md` sections 6, 10.

## Workflow/Session IDs
Slice W2-S3 prerequisites; branch `feat/aq-confine-w2s3-prereqs` (worktree `.agents/delegation/worktrees/confine-prereqs`); implementer sub-agent (Sonnet 5.5, Rule 17 default tier). Staged, not committed; full tier0 not run.

## Delegation Decision
Orchestrator dispatched to a Sonnet-tier implementer (Rule 17). Independent review before commit remains required.

## Commands Executed
- `AQ_CONFINE_REQUIRE=1 python3 scripts/testing/test-aq-confine.py` (3 consecutive runs; `UPDATE_GOLDEN=1` once to regenerate goldens)
- `python3 -m pytest -q scripts/testing/test-health-spider-loop-regression.py`
- `bash scripts/governance/tier0.d/check-ci-manifest-coverage.sh`
- `python3 scripts/testing/test-functional-prompt-eval.py`, `test-capability-integration-wiring.py` (regression of consumers)
- phase0 `_check_aq_confine_behavioral` invoked directly, once healthy and once with `BWRAP_PATH=/nonexistent`

## Validation Evidence
- Scope limits: profile key `cgroup` {memory_max bytes, tasks_max, allow_rlimit_only=false} is schema-required and validated (floor 16 MiB / 8 tasks). Launch argv is `systemd-run --user --scope --quiet --collect --unit=aq-confine-<run> -p MemoryMax=<n> -p MemorySwapMax=0 -p TasksMax=<n> -- prlimit ... bwrap ...`; RLIMIT_AS/NPROC kept. Defaults: worktree-rw 3 GiB/300, readonly-analysis 2 GiB/128, eval-untrusted 512 MiB/64.
- Fail closed: before launch `scope_probe()` creates a real scope and reads back `memory.max`, `pids.max`, `memory.swap.max`; any mismatch or failure returns exit 70 `setup-failed` reason `cgroup-scope-unavailable` and the child never runs (tests: missing systemd-run, stub exiting 1, stub that ignores limits). `allow_rlimit_only` profile flag (default off) permits rlimit-only (tested).
- Behavioral tests (all PASS): live `aq-confine-<run>.scope` shows MemoryMax/MemorySwapMax=0/TasksMax from profile; allocation past MemoryMax killed (exit 137/143) with a following run unaffected; fork past TasksMax=16 fails with EAGAIN (< 16 forks of 60 attempted); scopes gone (`LoadState=not-found`) after normal, OOM and pids runs; telemetry records `cgroup.scoped`.
- Initial suite: 201 checks, 0 failed (baseline before change: 179); see Review Follow-ups for the final 204.
- Also fixed: a run killed by SIGTERM/other signal (rc < 0) used to exit with a negative code; now `child-failed` reason `signaled-<n>`, exit 128+n.
- Goldens regenerated: three `--explain` goldens gain the systemd-run prefix only.
- CI: `.github/workflows/confine-tests.yml` (checkout pinned to the repo's v5 SHA, `permissions: contents: read`, path-filtered, 20 min timeout): installs bubblewrap, prints sysctls and an `unshare --user` control, probes bwrap, loads an inline scoped AppArmor userns profile for `/usr/bin/bwrap` only if the probe fails (exists-guarded system binds), starts `user@UID.service` for scopes, runs the suite with `AQ_CONFINE_REQUIRE=1`; red with `::error::` if confinement or scopes cannot be created. `config/ci-checks.json` ci_exempt gained `scripts/testing/test-aq-confine.py` and `scripts/ai/lib/confine.py` (reasons recorded); `check-ci-manifest-coverage.sh` -> PASS.
- tier0 wiring: new phase0 row 0.10.66 (`phase0.py` and `_aq-qa-bash`) runs the suite with `AQ_CONFINE_REQUIRE=1` unless `CI` is set (same mechanism as 0.10.64). Healthy: PASS (23 s). With `BWRAP_PATH=/nonexistent`: FAIL naming the test groups.
- Health-spider: `_confine_alerts_check()` lists pending `aq-confine` high alerts as `aq_confine_alert` anomalies (zone `aq-confine`), counted in each cycle and emitted as `health_spider_aq_confine_alert` events; new pytest passes (6 passed); real attention-queue round trip returned the pushed alert.

## Review Follow-ups (PASS_WITH_FOLLOWUPS, applied)
- Probe collision (MEDIUM): `scope_probe` uses a unique unit name per call (pid, counter, random), is serialized by a lock, and caches successes for 60 s but failures only 5 s (`SCOPE_FAIL_TTL_S`). Tests: 6 concurrent probes all succeed; expired failure re-probes.
- OOM (LOW): scope gets `-p OOMPolicy=kill`; a watcher polls the scope's `memory.events` fd (the scope disappears with its last process) and a nonzero `oom_kill` yields status `child-failed`, reason `oom-killed`, exit 137, with no ref promotion. Test asserts the reason on the MemoryMax allocation case.
- CI profile (LOW): kept `flags=(unconfined)` + `userns` scoped to `/usr/bin/bwrap`. The restrict-style profile could not be validated (no apparmor_parser on this NixOS host, no hosted runner), so an unvalidated stricter profile would risk a red job for the wrong reason. Documented in the workflow comment; follow-up is to adopt it after a hosted-runner run.
- Requirement note: every profile requires a reachable systemd user manager with memory+pids delegation; otherwise launches fail closed (exit 70 `cgroup-scope-unavailable`) unless `allow_rlimit_only`. Also stated in the profile schema description. W2-S3 (oncalld as a system service) needs a decided mechanism before enabling.
- Final suite: `SUMMARY: 204 checks ran, 0 failed, 0 behavioral groups skipped (preflight: ok)` on 3 consecutive runs.

## Rollback Plan
Revert the PR. Profiles without `cgroup` are rejected by the new schema, so revert profiles, schema, library and goldens together; no live caller depends on it yet except `functional_eval` (verified passing).

## Residual Risk
- CI workflow is unexecuted (no GitHub runner here); the user-manager and controller-delegation step on hosted Ubuntu is UNVERIFIED and may need adjustment on first run; it fails loudly rather than skipping.
- Scope requires a reachable systemd user manager with memory+pids delegation. Callers running as system services (W2-S3 oncalld) have no user manager and must either run a per-service manager, use a system-scope variant, or set `allow_rlimit_only` with an owner decision; this is a W2-S3 design item.
- MemoryMax kill is delivered via the cgroup OOM killer and surfaces as exit 137/143, not a distinct `oom` reason.
- Rule 15: observable (health-spider listing, telemetry), intervenable (`--kill`); integration/turn-on still deferred to S2b/W2-S3 (2026-10-31). Tracker/PULSE/RESUME not updated by the implementer.

## Hint Feedback
No aq-hints consulted for this slice; design doc and review file were the sources. Friction: the `grep -rn --include=*` zsh glob failure and the pass-through of `ctx` tools are the only tooling notes; nothing to report to aq-rsi.
