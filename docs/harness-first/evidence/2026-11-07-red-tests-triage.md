# 2026-11-07 red-tests-triage

## Objective
Triage the red tests from the P2.1 tests sweep (docs/harness-first/evidence/2026-11-06-sweep-tests.md): per file decide real product bug, stale test, sandbox artifact or missing dependency; fix what is small and clear; list the rest with a diagnosis. No assertion was weakened to go green.

## Workflow/Session IDs
Branch fix/red-tests-triage, date 2026-11-07. Staged, not committed.

## Delegation Decision
Orchestrator: claude-opus. Implementer: Claude Sonnet 5.5 (Rule 17, bounded triage slice).

## Commands Executed
CI parity environment: a venv holding `config/ci-test-requirements.txt` (what test.yml installs; `config/ci-python-requirements.txt` is only pyyaml and is not what the test job uses), `CI=true`, `HOME`/XDG/`TMPDIR` redirected to scratch, a `~/.gitconfig` with `user.name ci`, `user.email ci@localhost`, `init.defaultBranch main` (the same git config test.yml sets). Each test run directly on the host, and the touched groups through `scripts/governance/run-ci-checks.sh --all --only <id>`.
Group results after the changes: tests-capability PASS, tests-delegate PASS, tests-dashboard PASS, tests-aq PASS, dashboard-routing-ratio-test PASS; `check-ci-test-coverage.sh` PASS (763 tests: 618 declared, 145 exempt; before: 762 tests, 613 declared, 149 exempt).

## Validation Evidence

| test | diagnosis | how verified | action |
|---|---|---|---|
| test-capability-lease.py | Sweep PASS was on host deps. Exemption reason (fails in clean venv, 53/54) is obsolete: passes 56/56 with the test job's requirements (needs `cryptography`, in ci-test-requirements.txt). With only pyyaml it fails by ModuleNotFoundError, which is not what the job installs. TIME_BOMB flag is benign: the test re-mints relative expiries; only golden-fixture checks use a pinned `now`. | clean venv + CI env; run-ci-checks tests-capability | exemption removed, registered in tests-capability |
| test-dashboard-compat-routes.py | Stale test. FastAPI 0.162 / Starlette 1.10 (CI installs unpinned) keeps `include_router()` children behind opaque `_IncludedRouter` entries without `.path`, so `app.routes` showed 13 paths and 20 "missing" routes (all present in the app). Host has fastapi 0.136 which flattens, hence "passes on host". Fix: registered = top-level paths union `app.openapi()["paths"]` (favicon is schema-hidden, so both are kept). Expected-route set unchanged. | failed then passed in the CI venv; passes on host | fixed, exemption removed, registered in tests-dashboard |
| test-aq-report-reliability-interpretation.py | Stale test. `aq-report format_text()` gained required `editor_rescue_windows_summary`; the call omitted it. Product signature is right (other callers pass it). Added `{"available": False}`. | CI venv: PASS | fixed, exemption removed, registered in tests-aq |
| test-dashboard-orchestration-sessions.py | Two layers. (1) Stale fake: product `close_http_session()` reads `session.closed` and calls `close()` on the shared session; the test's FakeClientSession lacked both (fixed). (2) UI half asserts ids/functions (`orchestrationSessionList`, `loadOrchestrationSessions`, `orch*` ids) that the dashboard consolidation 1acd19966 removed from dashboard.html; the proxy half now passes. Rewriting the UI contract against assets/dashboard.js is more than a small fix. | CI venv: proxy half passes, fails at first UI assert | fake fixed; stays exempt, reason rewritten; backlog line below |
| test-dashboard-phase5-7-integration.py | Same two layers: fake fixed; UI half asserts `fetchAISpecificMetrics`, `hybrid*` ids removed by 1acd19966. | as above | fake fixed; stays exempt; backlog line below |
| test-delegate-claude-model-routing.py | Not a product bug and not a sandbox artifact: non-hermetic test. The wrapper honours an inherited `AQ_DELEGATION_DIR`; `run-test-group.py` (and operator shells) set one, so registry writes land outside the test's temp repo and `registry()[-1]` raised IndexError. Fix: the test sets `AQ_DELEGATION_DIR` to its own temp repo. | reproduced via run-ci-checks tests-delegate (IndexError), fixed, rerun PASS; also PASS directly | fixed, exemption removed, registered in tests-delegate |
| test-execution-cell-perf-harness.py | Harness/product drift. Runner hardening (928a6fe32) made `allow_self_bind` explicit (default refuses with `self-bind-disabled`, systemd activation is the production path); the harness never opted in, so its runner thread died and every UDS round-trip returned FileNotFoundError (6 failed rows on host). Fix in the harness `_base_config`: `allow_self_bind=True` for its throwaway temp socket; runner behaviour unchanged. The sweep's "no disk-backed temp dir" was the sandbox. | host: 50/56 -> 56/56 | fixed; stays exempt, reclassified sandbox-env (needs bwrap, disk temp, delegated cgroup that CI lacks) |
| check-aq-report-metric-smoke.sh | Sandbox artifact (cause not isolated; sweep sandbox has no network/limited tmp); already a manifest check. | host, CI env: PASS | none |
| test-activation-signer.py | Sandbox artifact; the sweep error was the signer's directory-search permission check on the sweep's private temp tree. | host: PASS | none |
| test-aq-completions.sh | Sandbox artifact (cause not isolated; sweep error was a missing bash completion spec). | host: PASS | none |
| test-aq-tool.py | Sandbox artifact (no network for nix; already sandbox-env exempt). The file is mode 644, so `./` invocation gives Permission denied; run via python. | host: PASS | none |
| test-aq-worktree-reap.py | Sandbox/config artifact: pushes `main` to a throwaway origin, needs `init.defaultBranch main` which test.yml sets. | host with CI git config: PASS | none |
| test-check-checkout-fresh.sh | Same git default-branch artifact. | host with CI git config: 10/10 | none |
| test-dashboard-ai-metrics-switchboard-local-runtime.py | Sandbox artifact (cause not isolated). | host: PASS | none |
| test-dashboard-visual.sh | Live-service test: needs dashboard on :8889 and headless chromium. 22/23 pass on the host; the screenshot step aborts (chromium core dump). Reclassified from `slow` to `live-service`. | host against live dashboard | reason/class corrected |
| test-delegate-codex-quota-precheck.sh | Sandbox artifact (cause not isolated; sweep output showed the sub-assertion passing and a later one failing). | host: PASS | none |
| test-execution-cell-runner.py | Sandbox artifact (sweep: quarantined/tree-not-proven-absent); exempt sandbox-env. | host: 56/56 | none |
| test-factory-gate-install.py / test-factory-gate-retrofit.py | Sandbox artifact (cause not isolated; sweep error was the fixture's gate-bundle self-test exiting 1 under the sandbox). | host: PASS | none |
| test-write-region.py | Sandbox artifact (cause not isolated). | host: PASS | none |
| test-harness-hooks.py | Wall-clock bound at load: hooks cost ~60-90 ms idle (python start); one run reached 138 ms under load. Now best-of-7 against the unchanged 100 ms bound: noise cannot lower the minimum, a real regression raises every run. Three consecutive host runs OK at load average ~10. | host x3 | fixed; still exempt (unstable) until it runs green in CI a few times |
| test-dashboard-routing-ratio.js | Passes (16 cases). Undeclared because the gate and runner only know .py/.sh. Added a bash entry `test-dashboard-routing-ratio.sh` and a standalone check `dashboard-routing-ratio-test` (needs node, which ubuntu runners ship) invoked by test.yml. | host; run-ci-checks PASS | registered |

## Product bugs found
- None in product code. Every red that looked like a product bug was a stale/non-hermetic test or harness drift against deliberate product changes (runner self-bind hardening, `format_text` signature, shared http session, FastAPI router internals).
- Backlog-ready: [OPEN] TESTS-DASHBOARD-UI-CONTRACT test-dashboard-orchestration-sessions.py and test-dashboard-phase5-7-integration.py — UI assertions reference elements removed by dashboard consolidation 1acd19966; re-derive against assets/dashboard.js (loadOrchestrationSessions equivalents at ~7654/7729) and the current hybrid pool/optimization panels, or retire if the panels are intentionally gone (parity-equivalent only); Severity low; Action: dashboard owner.
- Observation: tests that read `app.routes` for included routers (other tests-dashboard members) are fine today but share the FastAPI 0.16x router-internals exposure.

## Exemptions
Removed (4): test-capability-lease.py, test-dashboard-compat-routes.py, test-aq-report-reliability-interpretation.py, test-delegate-claude-model-routing.py. Reclassified: test-execution-cell-perf-harness.py (sandbox-env), test-dashboard-visual.sh (live-service); reasons rewritten for test-harness-hooks.py and the two dashboard UI tests. Exempt count 149 -> 145.

## Rebuild / restart
None. Test, harness and manifest changes only; no Nix config or service changes.

## Residual Risk
The sandbox-artifact verdicts come from host runs, not a CI run; the four newly registered tests passed through `run-ci-checks.sh` in a venv built from ci-test-requirements.txt but have not run on a GitHub runner.
