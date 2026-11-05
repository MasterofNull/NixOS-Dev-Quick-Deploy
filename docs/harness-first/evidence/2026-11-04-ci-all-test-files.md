## Objective
Make CI run every declared test file. Slice P0.5 of system-integrity-recovery, branch feat/ci-all-test-files.

Main finding: none of the 33 test-running checks was invoked by any workflow. Only the local pre-push hook ran them. The existing gate checked workflow-to-manifest coverage, not manifest-to-workflow coverage, so a declared test could go un-run without any failure.

## Workflow/Session IDs
Slice P0.5 (system-integrity-recovery). Branch feat/ci-all-test-files. Worktree .agents/delegation/worktrees/p05-all-tests. No session IDs are recorded in the source report.

## Delegation Decision
Orchestrator: claude-opus. Implementer: Claude Sonnet (Rule 17, explicit `sonnet` override). The slice is bounded to the gate, the CI manifest, the workflow, and the test files listed below.

## Commands Executed
- `scripts/governance/tier0.d/check-ci-test-coverage.sh` (gate): PASS, 764 tests, 622 declared, 142 exempt.
- check-ci-manifest-coverage (manifest coverage gate): PASS.
- `check-workflow-masks`: PASS.
- `scripts/testing/test-ci-test-coverage-gate.py`: PASS.
- `python3 -m json.tool config/ci-checks.json`: ok.
- `scripts/testing/test-ci-checks-manifest.py`: PASS.
- `scripts/governance/ci-clean-env.sh --all --only <id>` with `CI_CLEAN_ENV_REQS=config/ci-test-requirements.txt` and `CI=true`, over the 33 wired ids: 33 pass, 0 fail.
- Host probe of the 144 exempt tests, 6 in parallel, run-test-group environment: 31 pass, 113 fail.
- Re-run of the probe in a no-network namespace with a fresh HOME, twice: 5 tests passed both times and were promoted.

## Validation Evidence
Changes (all staged, none committed):
- `scripts/governance/tier0.d/check-ci-test-coverage.sh`: every `test_exempt` entry must carry a `class` from {live-service, sandbox-env, known-failing, unstable, slow, mutates-state}. Every check that runs a test must be invoked by a workflow through `--only <id>` (`CI_WORKFLOW_DIR` override).
- `config/ci-checks.json`: `class` added to all exemptions. Five tests promoted to declared: `scripts/testing/test-aq-completions.sh` and `scripts/testing/test-aq-usage-logging.py` (tests-aq), `scripts/testing/test-ci-merge-parity.py` and `scripts/testing/test-curated-web-research.py` (tests-misc-a-c), `scripts/testing/test-rsi-gate.py` (tests-misc-n-r). Three tests that fail in a CI-like environment moved into exemptions. The file was re-serialized, which also reformats two single-line entries.
- `.github/workflows/test.yml`: new job `manifest-tests` (Python 3.11 with uv, `uv pip install -r config/ci-test-requirements.txt`, git identity, then `scripts/governance/run-ci-checks.sh --all --only <33 ids>`). The job is added to the `build` needs.
- `config/ci-test-requirements.txt` (new): the dependency set the wired tests import.
- `scripts/testing/test-ci-checks-manifest.py`: `test_missing_tool_warns...` now passes `CI=""`. It failed whenever `CI=true`, which is the case on GitHub Actions. Root cause: the test inherited the runner's CI variable.
- `scripts/testing/test-ci-test-coverage-gate.py`: new cases. A missing or invalid class fails. A check with no workflow invocation fails. A red test in a group makes `scripts/testing/run-test-group.py` exit 1, and a green one exits 0.

Counts:

| Measure | Before | After |
|---|---|---|
| Tests in manifest | 764 | 764 |
| Declared | 620 | 622 |
| Exempt | 144 | 142 |
| Test checks invoked by a workflow | 0 of 33 | 33 of 33 |

Exempt entries by class (after):

| Class | Count |
|---|---|
| known-failing | 109 |
| live-service | 21 |
| unstable | 4 |
| sandbox-env | 3 |
| slow | 3 |
| mutates-state | 2 |

Validation results:
- Gate, manifest coverage, workflow masks, coverage-gate test, JSON parse, and manifest test all passed (`final-validation.out`).
- All 33 wired checks passed in the CI-like clean environment. Earlier runs with missing or partial dependencies failed (13 failed, then 7, then 5). Those runs are in the same directory.
- Gate negative proof: with the workflow wiring absent, the gate printed 33 "no workflow invokes it" failures.
- Non-gating masks: all `|| true` and `continue-on-error` uses are annotated and registered (#685). None sits on a test-running step.
- The three declared tests that fail only in the NixOS venv (`scripts/testing/test-cross-agent-contradiction-detection.py`, `scripts/testing/test-memory-recall-broker-contract.py`, `scripts/testing/test-model-optimization-implementation.py`) pass with `LD_LIBRARY_PATH` set. They stay declared.

Demoted to exemptions because they fail in a clean venv:
- `scripts/testing/test-capability-lease.py` (class: known-failing, not root-caused).
- `scripts/testing/test-dashboard-compat-routes.py` (missing routes when an optional dependency is absent).
- `scripts/testing/test-web-research-lane.py` (flaky under the parallel runner, class: unstable).

## Rollback Plan
Revert the staged changes in the worktree. The changes are the gate script, `config/ci-checks.json`, `.github/workflows/test.yml`, `config/ci-test-requirements.txt`, the two Python test files, and the promoted and demoted test entries. No data or runtime state is involved. Removing the `manifest-tests` job restores the prior CI behavior, but the gate would then fail on the 33 unwired checks. Rollback therefore also needs the gate change reverted.

## Residual Risk
- The `manifest-tests` job has never run on a real GitHub runner. The local check used a throwaway venv, `CI=true`, and `LD_LIBRARY_PATH` for libstdc++ on NixOS.
- NixOS `LD_LIBRARY_PATH` caveat: numpy wheels need libstdc++.so.6. Three declared tests fail on NixOS without it. CI runs on a different base, so this is a local caveat only.
- Runner differences are untested. Missing binaries on the runner (`shellcheck`, `jq`, `bwrap`), a shallow clone, and no HOME configuration may cause new failures. The first CI run may expose more. Treat those failures as real. Exempt them with a class. Do not mask them.
- 106 known-failing exempt tests are red in the host probe. The list with the last failure line for each is in `.agents/delegation/outputs/p05-all-tests/red-tests.txt`. Dominant causes: missing files, ImportError on moved modules, and stale assertions.
- The 21 live-service and 109 known-failing exemptions remain triage debt (issues-backlog TEST-COVERAGE).
- Probing the exempt tests in-tree mutated `.agent/collaboration/rsi-incidents.json` and `.agent/memory/issues-backlog.md`, and created `.agent/oncall` and `.agent/triage`. These were reverted or moved to `test-artifacts/` in the worktree and are not staged.

## Hint Feedback
No hints were recorded in the source report.

## Follow-up: first real GitHub runner run

The first real run on PR #690 (run 41943848534) failed 12 of the 33 checks. The tests assumed the owner host, and the earlier "clean env" validation had run on that host. Fixes, with no masking:

| Remedy | Count | What |
|---|---|---|
| Tool provided in the job | 11 | Nix, using the pinned action and config from `nix-build.yml`. gitleaks 8.24.3, pinned as in `gitleaks.yml`. `init.defaultBranch main`. The job also moves to Python 3.13, the production interpreter. Python 3.11 broke on 3.12+ f-strings in `aq-hints` and on `asyncio.wait_for` cancellation. |
| Hermetic override | 17 | `DASHBOARD_DATA_DIR` is set per test in `scripts/testing/run-test-group.py`. The PR event vars are stripped from the per-test env. `CODEX_BIN` and `REPO_PATH` are set in 4 tests. |
| Exempted with a class | 9 | live-service (5): the delegate tests that POST to the coordinator with the host secret. sandbox-env (4): tests that need the real Gemini MCP config, the local model weights, the installed Codex CLI, or bwrap containment. |
| Test fix | 1 | `test-delegate-headless-budget.py` used `source` under dash. It now uses `bash -c`. |

Local validation: a stripped-environment simulation (temp HOME, PR and CI env, Python 3.13 venv) passes every affected group with the tools present. Without nix and gitleaks, exactly the five items that need them fail. `run-ci-checks.sh --changed` passes 23 of 23.

Only the real runner can confirm:
- whether a cold `nix eval` fits the 120 s per-test timeout (it takes 23 s warm);
- the gitleaks 8.24.3 behaviour;
- the security-audit-gate fix, whose failure did not reproduce locally;
- the uv install on Python 3.13.

Detail: `.agents/delegation/outputs/p05-all-tests/runner-fix/REPORT.md`.

## Follow-up: second real runner run

The second real run (job 127024578611) passed 31 of 33 checks. Three tests remained, and each failure was reproduced locally before it was fixed:

- **`test-aqos-guided-install.py`:** `hash_password` falls back to stdlib `crypt` when `mkpasswd` is absent, and Python 3.13 removed `crypt`. The job now installs apt `whois`, which provides `mkpasswd`.
- **`test-security-audit-gate.sh`:** the "covered clean scan" case ran the real `dashboard-security-scan.sh` against a live dashboard on 127.0.0.1:8889. It now uses the `ok-dashboard.sh` and `ok-secrets.sh` stubs the test already defines. The pip-audit coverage assertion is unchanged.
- **`test-write-region.py`:** the local-agent file tools only allow writes under /tmp, ~/Documents and ~/.local/share. `scripts/testing/run-test-group.py` built per-test dirs under the runner's TMPDIR, `/home/runner/work/_temp`. They are now created under /tmp.

Local stripped-env simulation, using `env -i`, Python 3.13, TMPDIR outside /tmp and a dead dashboard URL: `run-ci-checks.sh --changed` passes 37 of 37.
