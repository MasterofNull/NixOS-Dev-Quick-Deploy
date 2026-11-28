# Stale known-failing exemption guard

## Objective

`config/ci-checks.json` `test_exempt` entries with class `known-failing` were never rechecked, so `test-ai-stack-health-monitor.py` stayed outside CI after 974f2a608 fixed its cause. Add `tier0.d/check-stale-known-failing.py`, which runs those entries and fails when one now passes.

## Workflow/Session IDs

- Implementer: Claude Sonnet 5.5 sub-agent (headless, worktree agent-abad284170fda867f). Orchestrator session id not supplied.

## Delegation Decision

Bounded single-gate change plus one hermetic test, routed to a Claude Sonnet implementer by the orchestrator.

## Commands Executed

- `python3 scripts/testing/test-tier0-stale-known-failing.py`
- `python3 scripts/governance/tier0.d/check-stale-known-failing.py --maintenance` (real manifest)
- `python3 scripts/testing/test-tier0d-gate-mutation.py`
- `bash scripts/governance/tier0.d/check-ci-test-coverage.sh`
- `GITHUB_BASE_REF=main bash scripts/testing/check-harness-first-pr-evidence-gate.sh`
- `python3 scripts/governance/check-cross-surface-contract.py`, `ruff check`, `basedpyright`

## Validation Evidence

The gate loads `check-host-only-tests.py` by path and reuses its staged-file listing, `triggered()` selection, runner and manifest/root handling, so the two gates share the `HOST_ONLY_ROOT`, `HOST_ONLY_STAGED` and `HOST_ONLY_MANIFEST_FILE` overrides; only the timeout and budget are its own (`STALE_KF_TIMEOUT`, `STALE_KF_BUDGET`). `--pre-commit` runs only triggered entries, `--maintenance`/`--pre-deploy` run all, `--ci` and `TIER0_CI=1` skip. A passing entry FAILs with "known-failing exemption is stale"; a failing or timed-out entry PASSes with its first output line; exit 77 or a missing `needs` tool SKIPs.

Hermetic test (11 cases: stale FAIL, still-failing PASS, non-staged skip, module-under-test trigger, other class ignored, exit 77, missing needs, `--ci`, `TIER0_CI`, timeout, git failure) passes. The gate is registered as `tier0-stale-known-failing-gate` in the manifest and the workflow `--only` list, and mapped in `COVERED_ELSEWHERE` of `test-tier0d-gate-mutation.py`.

A `--maintenance` run on the real manifest checked 47 known-failing entries: 41 still fail, 6 pass (stale), 0 skipped. The stale entries (left unchanged; follow-ups): `test-ai-stack-health-monitor.py`, `test-claude-dispatch-payload-safety.py`, `test-delegate-to-claude-lifecycle.py`, `test-llm-router-integration.py`, `test-qa-provider-probe-lifecycle.py`, `test-scope-gate.py`. Until those are removed and declared as checks, `--maintenance` and any commit staging those scripts or their modules will FAIL by design.

Follow-up in the same slice: five of the six stale entries were handled (the sixth, `test-ai-stack-health-monitor.py`, is removed by another slice). `test-claude-dispatch-payload-safety.py`, `test-delegate-to-claude-lifecycle.py` and `test-qa-provider-probe-lifecycle.py` each passed 3 of 3 local runs and are now declared CI checks (`claude-dispatch-payload-safety-test`, `delegate-to-claude-lifecycle-test`, `qa-provider-probe-lifecycle-test`, job `manifest-tests`, with `--only` lines in the workflow). `test-scope-gate.py` needs `nix build` of `harness-contracts` plus `cargo test`, so it moved to `sandbox-env` with `needs: [nix, cargo]`. `test-llm-router-integration.py` only printed "FAIL" and exited 0, so its pass was not a real pass (it cannot gate); it now exits 1 on a routing mismatch (Test 2 still mismatches) and stays `known-failing`. That test also wrote `routing_metrics.db` into the repo root via `get_router()`; it now sets `AQ_ROUTING_METRICS_DB_PATH` to a temp dir (verified: the root DB files were not touched by a run). A second `--maintenance` run flags only `test-ai-stack-health-monitor.py`.

## Rollback Plan

Revert the commit; the gate file, its test, the manifest entry, the workflow line and the mutation map entry go together.

## Residual Risk

The six stale entries must be un-exempted in a follow-up (each needs a declared check and a CI-stability look). Entries whose test only passes on this host may be wrongly flagged stale if CI cannot run them; the follow-up should confirm CI stability before declaring.

## Hint Feedback

None.
