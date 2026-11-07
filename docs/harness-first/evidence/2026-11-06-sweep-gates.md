# 2026-11-06 sweep-gates

## Objective
Recovery sweep P2.2 (system-integrity-recovery): list gates that cannot fail, have no bad-input test, fail open, are masked in CI, are not required, or are not run by any stage. Report only; no gate or finding was fixed.

## Workflow/Session IDs
Branch feat/sweep-gates, date 2026-11-06. Sweeps this tree only. fix/gates-placement (S2) moves checks between stages, so UNCOVERED, NOT_REQUIRED and stage results will change when S2 merges; the script derives stages from references and hardcodes none.

## Delegation Decision
Orchestrator: claude-opus. Implementer: Claude Sonnet (Rule 17, bounded single-script slice with fixture tests).

## Commands Executed
- `scripts/governance/sweep-gates.py --github --exercise --date 2026-11-06 --report docs/harness-first/evidence/2026-11-06-sweep-gates.md`
- `gh api repos/<owner>/<repo>/branches/main/protection` (read-only GET, required status checks only)
- Probes: `git clone` into a temp dir with HOME redirected, seed one bad input, run the gate, record the exit code

## Validation Evidence

Gates inventoried: ci-check 57, hook 6, script 51, tier0-function 30, tier0.d 23, workflow-job 40, workflow-script 25 (total 232).

Gates affected per class (a gate counts once per class):

| Class | Gates | Finding rows |
|---|---|---|
| CANNOT_FAIL | 3 | 4 |
| NO_BAD_INPUT_TEST | 93 | 93 |
| FAIL_OPEN | 33 | 38 |
| MASKED_IN_CI | 6 | 9 |
| NOT_REQUIRED | 96 | 96 |
| UNCOVERED | 14 | 14 |

Required status checks (branch protection, main): ['review-disposition'].

### Findings

| # | Sev | Class | Basis | Gate | Evidence |
|---|---|---|---|---|---|
| 1 | high | CANNOT_FAIL | exercised | `.githooks/pre-merge-commit` | exercised: seeded bad input (shallow-merge guard script absent) and the gate exited 0: pre-merge-commit: WARN missing /tmp/sweep-gates-hrkucqzf/w-premerge-guard-missing/scripts/governance/check-mergeable.sh — skipping shallow-merge guard |
| 2 | high | CANNOT_FAIL | exercised | `tier0:collect_changed_files` | exercised: seeded bad input (committed bad.py, --pre-deploy, no origin/main) and the gate exited 0:  |
| 3 | high | CANNOT_FAIL | static | `tier0:gate_deploy_batch_size` | body has no fail(), return 1 or exit (static) |
| 4 | high | CANNOT_FAIL | exercised | `tier0:gate_deploy_batch_size` | exercised: seeded bad input (0 commits ahead of origin/main (batch too small)) and the gate exited 0:  |
| 5 | high | FAIL_OPEN | static | `tier0:gate_bash_syntax` | empty file list passes and the list comes from collect_changed_files() whose commands end in `\|\| true`: a git failure gives an empty list and a 'No changes' PASS (static) |
| 6 | high | FAIL_OPEN | static | `tier0:gate_env_contract` | empty file list passes and the list comes from collect_changed_files() whose commands end in `\|\| true`: a git failure gives an empty list and a 'No changes' PASS (static) |
| 7 | high | FAIL_OPEN | static | `tier0:gate_js_syntax` | empty file list passes and the list comes from collect_changed_files() whose commands end in `\|\| true`: a git failure gives an empty list and a 'No changes' PASS (static) |
| 8 | high | FAIL_OPEN | static | `tier0:gate_json_syntax` | empty file list passes and the list comes from collect_changed_files() whose commands end in `\|\| true`: a git failure gives an empty list and a 'No changes' PASS (static) |
| 9 | high | FAIL_OPEN | static | `tier0:gate_nix_syntax` | empty file list passes and the list comes from collect_changed_files() whose commands end in `\|\| true`: a git failure gives an empty list and a 'No changes' PASS (static) |
| 10 | high | FAIL_OPEN | static | `tier0:gate_python_syntax` | empty file list passes and the list comes from collect_changed_files() whose commands end in `\|\| true`: a git failure gives an empty list and a 'No changes' PASS (static) |
| 11 | high | FAIL_OPEN | static | `tier0:gate_sql_syntax` | empty file list passes and the list comes from collect_changed_files() whose commands end in `\|\| true`: a git failure gives an empty list and a 'No changes' PASS (static) |
| 12 | high | FAIL_OPEN | static | `tier0:gate_toml_syntax` | empty file list passes and the list comes from collect_changed_files() whose commands end in `\|\| true`: a git failure gives an empty list and a 'No changes' PASS (static) |
| 13 | high | FAIL_OPEN | static | `tier0:gate_ts_syntax` | empty file list passes and the list comes from collect_changed_files() whose commands end in `\|\| true`: a git failure gives an empty list and a 'No changes' PASS (static) |
| 14 | high | FAIL_OPEN | static | `tier0:gate_yaml_syntax` | empty file list passes and the list comes from collect_changed_files() whose commands end in `\|\| true`: a git failure gives an empty list and a 'No changes' PASS (static) |
| 15 | high | UNCOVERED | static | `script:scripts/governance/check-doc-frontmatter.py` | no hook, workflow, tier0, manifest cmd, script or nix unit references it; ci_exempt: none (static) |
| 16 | high | UNCOVERED | static | `script:scripts/governance/check-doc-lifecycle-hygiene.py` | no hook, workflow, tier0, manifest cmd, script or nix unit references it; ci_exempt: none (static) |
| 17 | high | UNCOVERED | static | `script:scripts/governance/check-flake-age.sh` | no hook, workflow, tier0, manifest cmd, script or nix unit references it; ci_exempt: none (static) |
| 18 | high | UNCOVERED | static | `script:scripts/governance/check-workflow-script-refs.sh` | no hook, workflow, tier0, manifest cmd, script or nix unit references it; ci_exempt: none (static) |
| 19 | high | UNCOVERED | static | `script:scripts/governance/verify-profile-cleanup.sh` | no hook, workflow, tier0, manifest cmd, script or nix unit references it; ci_exempt: none (static) |
| 20 | high | UNCOVERED | static | `script:scripts/testing/check-agent-context-tooling.sh` | no hook, workflow, tier0, manifest cmd, script or nix unit references it; ci_exempt: none (static) |
| 21 | high | UNCOVERED | static | `script:scripts/testing/check-aq-integrity-logical-baseline.py` | no hook, workflow, tier0, manifest cmd, script or nix unit references it; ci_exempt: none (static) |
| 22 | high | UNCOVERED | static | `script:scripts/testing/check-context-bootstrap.sh` | no hook, workflow, tier0, manifest cmd, script or nix unit references it; ci_exempt: none (static) |
| 23 | high | UNCOVERED | static | `script:scripts/testing/check-knowledge-base-breadth.sh` | no hook, workflow, tier0, manifest cmd, script or nix unit references it; ci_exempt: none (static) |
| 24 | high | UNCOVERED | static | `script:scripts/testing/validate-deployment-monitoring-alerting.sh` | no hook, workflow, tier0, manifest cmd, script or nix unit references it; ci_exempt: none (static) |
| 25 | high | UNCOVERED | static | `script:scripts/testing/validate-phase-5.2.sh` | no hook, workflow, tier0, manifest cmd, script or nix unit references it; ci_exempt: none (static) |
| 26 | high | UNCOVERED | static | `script:scripts/testing/validate-query-agent-storage-learning.sh` | no hook, workflow, tier0, manifest cmd, script or nix unit references it; ci_exempt: none (static) |
| 27 | high | UNCOVERED | static | `script:scripts/testing/verify-dashboard-apis.py` | no hook, workflow, tier0, manifest cmd, script or nix unit references it; ci_exempt: none (static) |
| 28 | high | UNCOVERED | static | `tier0.d/check-frontier-fold` | tier0 runs only ['*.sh'] from tier0.d; this file matches none and nothing else references it (static) |
| 29 | medium | FAIL_OPEN | static | `.githooks/post-checkout` | line 8: absent file/runner treated as pass: `[[ -x "$freshness_script" ]] \|\| exit 0` (static) |
| 30 | medium | FAIL_OPEN | static | `.githooks/post-merge` | line 8: absent file/runner treated as pass: `[[ -x "$freshness_script" ]] \|\| exit 0` (static) |
| 31 | medium | FAIL_OPEN | static | `.githooks/pre-commit` | line 337: tool-missing treated as pass/skip: `if ! command -v npm >/dev/null 2>&1; then` (static) |
| 32 | medium | FAIL_OPEN | static | `.githooks/pre-push` | line 119: absent file/runner treated as pass: `[[ -x "scripts/governance/run-ci-checks.sh" ]] \|\| return 0` (static) |
| 33 | medium | FAIL_OPEN | static | `ci-check:activation-chain-test` | line 474: parse/IO error swallowed as pass: `except OSError:` (static) |
| 34 | medium | FAIL_OPEN | static | `ci-check:aq-report-metric-smoke` | line 99: parse/IO error swallowed as pass: `except json.JSONDecodeError:` (static) |
| 35 | medium | FAIL_OPEN | static | `ci-check:aq-report-metric-smoke` | line 106: parse/IO error swallowed as pass: `except ValueError:` (static) |
| 36 | medium | FAIL_OPEN | static | `ci-check:aq-report-metric-smoke` | line 114: parse/IO error swallowed as pass: `except OSError:` (static) |
| 37 | medium | FAIL_OPEN | static | `ci-check:aq-report-metric-smoke` | line 135: parse/IO error swallowed as pass: `except OSError:` (static) |
| 38 | medium | FAIL_OPEN | static | `ci-check:delegate-headless-budget-tests` | line 121: parse/IO error swallowed as pass: `except ValueError:` (static) |
| 39 | medium | FAIL_OPEN | static | `ci-check:factory-kit-clean` | line 60: tool-missing treated as pass/skip: `if not shutil.which("gitleaks"):` (static) |
| 40 | medium | FAIL_OPEN | static | `ci-check:validate-echo-colors` | line 92: tool-missing treated as pass/skip: `if command -v /bin/echo >/dev/null 2>&1; then` (static) |
| 41 | medium | FAIL_OPEN | static | `script:scripts/governance/check-naming-label-consistency.sh` | line 72: parse/IO error swallowed as pass: `except Exception:` (static) |
| 42 | medium | FAIL_OPEN | static | `script:scripts/governance/check-state-authorities.py` | line 468: parse/IO error swallowed as pass: `except (OSError, ValueError):` (static) |
| 43 | medium | FAIL_OPEN | static | `script:scripts/testing/check-boot-shutdown-integration.sh` | line 41: tool-missing treated as pass/skip: `if command -v systemctl >/dev/null 2>&1; then` (static) |
| 44 | medium | FAIL_OPEN | static | `script:scripts/testing/check-boot-shutdown-integration.sh` | line 49: tool-missing treated as pass/skip: `if command -v journalctl >/dev/null 2>&1; then` (static) |
| 45 | medium | FAIL_OPEN | static | `script:scripts/testing/check-dashboard-managed-service.sh` | line 9: tool-missing treated as pass/skip: `if ! command -v systemctl >/dev/null 2>&1; then` (static) |
| 46 | medium | FAIL_OPEN | static | `script:scripts/testing/check-dashboard-managed-service.sh` | line 25: tool-missing treated as pass/skip: `if ! command -v ss >/dev/null 2>&1; then` (static) |
| 47 | medium | FAIL_OPEN | static | `script:scripts/testing/check-prsi-confidence-calibration.sh` | line 60: parse/IO error swallowed as pass: `except Exception:` (static) |
| 48 | medium | FAIL_OPEN | static | `script:scripts/testing/check-tls-log-warnings.sh` | line 8: tool-missing treated as pass/skip: `if ! command -v journalctl >/dev/null 2>&1; then` (static) |
| 49 | medium | FAIL_OPEN | static | `script:scripts/testing/verify-dashboard-apis.py` | line 145: parse/IO error swallowed as pass: `except Exception:` (static) |
| 50 | medium | FAIL_OPEN | static | `script:scripts/testing/verify-flake-first-roadmap-completion.sh` | line 12: tool-missing treated as pass/skip: `if command -v rg >/dev/null 2>&1; then` (static) |
| 51 | medium | FAIL_OPEN | static | `tier0.d/check-dependency-cve.sh` | line 12: tool-missing treated as pass/skip: `if ! command -v npm >/dev/null 2>&1; then` (static) |
| 52 | medium | FAIL_OPEN | static | `tier0.d/check-gitleaks-ci-parity.sh` | line 8: tool-missing treated as pass/skip: `if ! command -v gitleaks >/dev/null 2>&1; then` (static) |
| 53 | medium | FAIL_OPEN | static | `tier0.d/check-owned-scope.sh` | line 19: tool-missing treated as pass/skip: `if ! command -v cargo >/dev/null 2>&1; then` (static) |
| 54 | medium | FAIL_OPEN | static | `tier0.d/check-tool-pins-skew.sh` | line 26: tool-missing treated as pass/skip: `if command -v gitleaks >/dev/null 2>&1; then` (static) |
| 55 | medium | NOT_REQUIRED | static | `ci-check:activation-chain-test` | claims CI via .github/workflows/test.yml#syntax; that job is not a required status check, so a red run does not block merge (static + branch protection read) |
| 56 | medium | NOT_REQUIRED | static | `ci-check:activation-manifest-tests` | claims CI via .github/workflows/test.yml#syntax; that job is not a required status check, so a red run does not block merge (static + branch protection read) |
| 57 | medium | NOT_REQUIRED | static | `ci-check:activation-signer-test` | claims CI via .github/workflows/test.yml#syntax; that job is not a required status check, so a red run does not block merge (static + branch protection read) |
| 58 | medium | NOT_REQUIRED | static | `ci-check:aq-report-contract` | claims CI via .github/workflows/test.yml#syntax; that job is not a required status check, so a red run does not block merge (static + branch protection read) |
| 59 | medium | NOT_REQUIRED | static | `ci-check:aq-report-metric-smoke` | claims CI via .github/workflows/test.yml#syntax; that job is not a required status check, so a red run does not block merge (static + branch protection read) |
| 60 | medium | NOT_REQUIRED | static | `ci-check:aq-review-request-tests` | claims CI via .github/workflows/test.yml#syntax; that job is not a required status check, so a red run does not block merge (static + branch protection read) |
| 61 | medium | NOT_REQUIRED | static | `ci-check:check-workflow-masks-test` | claims CI via .github/workflows/test.yml#syntax; that job is not a required status check, so a red run does not block merge (static + branch protection read) |
| 62 | medium | NOT_REQUIRED | static | `ci-check:ci-test-coverage-gate` | claims CI via .github/workflows/test.yml#syntax; that job is not a required status check, so a red run does not block merge (static + branch protection read) |
| 63 | medium | NOT_REQUIRED | static | `ci-check:delegate-headless-budget-tests` | claims CI via .github/workflows/test.yml#syntax; that job is not a required status check, so a red run does not block merge (static + branch protection read) |
| 64 | medium | NOT_REQUIRED | static | `ci-check:delegate-sleep-inhibit` | claims CI via .github/workflows/test.yml#syntax; that job is not a required status check, so a red run does not block merge (static + branch protection read) |
| 65 | medium | NOT_REQUIRED | static | `ci-check:delegation-dir-resolution-tests` | claims CI via .github/workflows/test.yml#syntax; that job is not a required status check, so a red run does not block merge (static + branch protection read) |
| 66 | medium | NOT_REQUIRED | static | `ci-check:dispatch-preflight-tests` | claims CI via .github/workflows/test.yml#syntax; that job is not a required status check, so a red run does not block merge (static + branch protection read) |
| 67 | medium | NOT_REQUIRED | static | `ci-check:factory-kit-clean` | claims CI via .github/workflows/test.yml#syntax; that job is not a required status check, so a red run does not block merge (static + branch protection read) |
| 68 | medium | NOT_REQUIRED | static | `ci-check:factory-kit-tests` | claims CI via .github/workflows/test.yml#syntax; that job is not a required status check, so a red run does not block merge (static + branch protection read) |
| 69 | medium | NOT_REQUIRED | static | `ci-check:gitleaks-tree` | claims CI via .github/workflows/security.yml#secrets-scan; that job is not a required status check, so a red run does not block merge (static + branch protection read) |
| 70 | medium | NOT_REQUIRED | static | `ci-check:grype-ignore-expiry` | claims CI via .github/workflows/security.yml#nix-closure-vuln-scan; that job is not a required status check, so a red run does not block merge (static + branch protection read) |
| 71 | medium | NOT_REQUIRED | static | `ci-check:harness-first-pr-evidence` | claims CI via .github/workflows/test.yml#syntax; that job is not a required status check, so a red run does not block merge (static + branch protection read) |
| 72 | medium | NOT_REQUIRED | static | `ci-check:harness-first-static-gates` | claims CI via .github/workflows/test.yml#syntax; that job is not a required status check, so a red run does not block merge (static + branch protection read) |
| 73 | medium | NOT_REQUIRED | static | `ci-check:hook-git-env-isolation` | claims CI via .github/workflows/test.yml#syntax; that job is not a required status check, so a red run does not block merge (static + branch protection read) |
| 74 | medium | NOT_REQUIRED | static | `ci-check:intelligence-classifier-tests` | claims CI via .github/workflows/test.yml#syntax; that job is not a required status check, so a red run does not block merge (static + branch protection read) |
| 75 | medium | NOT_REQUIRED | static | `ci-check:llm-speed-probe-tests` | claims CI via .github/workflows/test.yml#syntax; that job is not a required status check, so a red run does not block merge (static + branch protection read) |
| 76 | medium | NOT_REQUIRED | static | `ci-check:mcp-integrity-baseline-test` | claims CI via .github/workflows/test.yml#syntax; that job is not a required status check, so a red run does not block merge (static + branch protection read) |
| 77 | medium | NOT_REQUIRED | static | `ci-check:mcp-integrity-unit-path-test` | claims CI via .github/workflows/test.yml#syntax; that job is not a required status check, so a red run does not block merge (static + branch protection read) |
| 78 | medium | NOT_REQUIRED | static | `ci-check:mobility-sleep-resilience` | claims CI via .github/workflows/test.yml#syntax; that job is not a required status check, so a red run does not block merge (static + branch protection read) |
| 79 | medium | NOT_REQUIRED | static | `ci-check:pm-tracker-activation-cap` | claims CI via .github/workflows/test.yml#syntax; that job is not a required status check, so a red run does not block merge (static + branch protection read) |
| 80 | medium | NOT_REQUIRED | static | `ci-check:pm-tracker-owner-acceptance` | claims CI via .github/workflows/test.yml#syntax; that job is not a required status check, so a red run does not block merge (static + branch protection read) |
| 81 | medium | NOT_REQUIRED | static | `ci-check:pm-tracker-untrusted-hold` | claims CI via .github/workflows/test.yml#syntax; that job is not a required status check, so a red run does not block merge (static + branch protection read) |
| 82 | medium | NOT_REQUIRED | static | `ci-check:prsi-bootstrap-integrity` | claims CI via .github/workflows/test.yml#syntax; that job is not a required status check, so a red run does not block merge (static + branch protection read) |
| 83 | medium | NOT_REQUIRED | static | `ci-check:prsi-cycle-contract` | claims CI via .github/workflows/test.yml#syntax; that job is not a required status check, so a red run does not block merge (static + branch protection read) |
| 84 | medium | NOT_REQUIRED | static | `ci-check:prsi-phase7-static-gates` | claims CI via .github/workflows/test.yml#syntax; that job is not a required status check, so a red run does not block merge (static + branch protection read) |
| 85 | medium | NOT_REQUIRED | static | `ci-check:python-tooling-policy` | claims CI via .github/workflows/test.yml#syntax; that job is not a required status check, so a red run does not block merge (static + branch protection read) |
| 86 | medium | NOT_REQUIRED | static | `ci-check:rea-sandbox-tests` | claims CI via .github/workflows/test.yml#syntax; that job is not a required status check, so a red run does not block merge (static + branch protection read) |
| 87 | medium | NOT_REQUIRED | static | `ci-check:security-audit` | claims CI via .github/workflows/security.yml#security-audit; that job is not a required status check, so a red run does not block merge (static + branch protection read) |
| 88 | medium | NOT_REQUIRED | static | `ci-check:service-manager-sudo-commands-test` | claims CI via .github/workflows/test.yml#syntax; that job is not a required status check, so a red run does not block merge (static + branch protection read) |
| 89 | medium | NOT_REQUIRED | static | `ci-check:skill-external-deps` | claims CI via .github/workflows/test.yml#skill-governance-lint; that job is not a required status check, so a red run does not block merge (static + branch protection read) |
| 90 | medium | NOT_REQUIRED | static | `ci-check:skill-source-of-truth` | claims CI via .github/workflows/test.yml#skill-governance-lint; that job is not a required status check, so a red run does not block merge (static + branch protection read) |
| 91 | medium | NOT_REQUIRED | static | `ci-check:skill-template` | claims CI via .github/workflows/test.yml#skill-governance-lint; that job is not a required status check, so a red run does not block merge (static + branch protection read) |
| 92 | medium | NOT_REQUIRED | static | `ci-check:template-placeholders` | claims CI via .github/workflows/test.yml#template-placeholder-lint; that job is not a required status check, so a red run does not block merge (static + branch protection read) |
| 93 | medium | NOT_REQUIRED | static | `ci-check:tests-agent` | claims CI via .github/workflows/test.yml#syntax; that job is not a required status check, so a red run does not block merge (static + branch protection read) |
| 94 | medium | NOT_REQUIRED | static | `ci-check:tests-aq` | claims CI via .github/workflows/test.yml#syntax; that job is not a required status check, so a red run does not block merge (static + branch protection read) |
| 95 | medium | NOT_REQUIRED | static | `ci-check:tests-aqos` | claims CI via .github/workflows/test.yml#syntax; that job is not a required status check, so a red run does not block merge (static + branch protection read) |
| 96 | medium | NOT_REQUIRED | static | `ci-check:tests-capability` | claims CI via .github/workflows/test.yml#syntax; that job is not a required status check, so a red run does not block merge (static + branch protection read) |
| 97 | medium | NOT_REQUIRED | static | `ci-check:tests-context` | claims CI via .github/workflows/test.yml#syntax; that job is not a required status check, so a red run does not block merge (static + branch protection read) |
| 98 | medium | NOT_REQUIRED | static | `ci-check:tests-dashboard` | claims CI via .github/workflows/test.yml#syntax; that job is not a required status check, so a red run does not block merge (static + branch protection read) |
| 99 | medium | NOT_REQUIRED | static | `ci-check:tests-delegate` | claims CI via .github/workflows/test.yml#syntax; that job is not a required status check, so a red run does not block merge (static + branch protection read) |
| 100 | medium | NOT_REQUIRED | static | `ci-check:tests-factory` | claims CI via .github/workflows/test.yml#syntax; that job is not a required status check, so a red run does not block merge (static + branch protection read) |
| 101 | medium | NOT_REQUIRED | static | `ci-check:tests-local` | claims CI via .github/workflows/test.yml#syntax; that job is not a required status check, so a red run does not block merge (static + branch protection read) |
| 102 | medium | NOT_REQUIRED | static | `ci-check:tests-misc-a-c` | claims CI via .github/workflows/test.yml#syntax; that job is not a required status check, so a red run does not block merge (static + branch protection read) |
| 103 | medium | NOT_REQUIRED | static | `ci-check:tests-misc-d-h` | claims CI via .github/workflows/test.yml#syntax; that job is not a required status check, so a red run does not block merge (static + branch protection read) |
| 104 | medium | NOT_REQUIRED | static | `ci-check:tests-misc-i-m` | claims CI via .github/workflows/test.yml#syntax; that job is not a required status check, so a red run does not block merge (static + branch protection read) |
| 105 | medium | NOT_REQUIRED | static | `ci-check:tests-misc-n-r` | claims CI via .github/workflows/test.yml#syntax; that job is not a required status check, so a red run does not block merge (static + branch protection read) |
| 106 | medium | NOT_REQUIRED | static | `ci-check:tests-misc-s-z` | claims CI via .github/workflows/test.yml#syntax; that job is not a required status check, so a red run does not block merge (static + branch protection read) |
| 107 | medium | NOT_REQUIRED | static | `ci-check:tier0-qa-admission-test` | claims CI via .github/workflows/test.yml#syntax; that job is not a required status check, so a red run does not block merge (static + branch protection read) |
| 108 | medium | NOT_REQUIRED | static | `ci-check:tool-security-auditor-smoke` | claims CI via .github/workflows/test.yml#syntax; that job is not a required status check, so a red run does not block merge (static + branch protection read) |
| 109 | medium | NOT_REQUIRED | static | `ci-check:validate-echo-colors` | claims CI via .github/workflows/validate-shell-scripts.yml#validate-shell-color-echo; that job is not a required status check, so a red run does not block merge (static + branch protection read) |
| 110 | medium | NOT_REQUIRED | static | `ci-check:workflow-failure-masks` | claims CI via .github/workflows/test.yml#syntax; that job is not a required status check, so a red run does not block merge (static + branch protection read) |
| 111 | medium | NOT_REQUIRED | static | `ci-check:world-writable` | claims CI via .github/workflows/test.yml#security; that job is not a required status check, so a red run does not block merge (static + branch protection read) |
| 112 | medium | NOT_REQUIRED | static | `workflow:confine-tests.yml#confine-tests` | context `aq-confine behavioral suite` is not a required status check; claim: workflow text says `required` (static + branch protection read) |
| 113 | medium | NOT_REQUIRED | static | `workflow:gitleaks.yml#scan` | context `Gitleaks Secret Scan` is not a required status check; claim: workflow text says `blocking` (static + branch protection read) |
| 114 | medium | NOT_REQUIRED | static | `workflow:harness-sdk-release.yml#publish-npm` | context `Publish JS SDK to npm` is not a required status check; claim: workflow text says `required` (static + branch protection read) |
| 115 | medium | NOT_REQUIRED | static | `workflow:harness-sdk-release.yml#publish-pypi` | context `Publish Python SDK to PyPI` is not a required status check; claim: workflow text says `required` (static + branch protection read) |
| 116 | medium | NOT_REQUIRED | static | `workflow:harness-sdk-release.yml#validate` | context `Validate and Build SDK Artifacts` is not a required status check; claim: workflow text says `required` (static + branch protection read) |
| 117 | medium | NOT_REQUIRED | static | `workflow:security.yml#nix-closure-vuln-scan` | context `Nix Closure Vulnerability Scan` is not a required status check; claim: manifest description says `CI-hard` and 1 check(s) point here via ci_workflow (static + branch protection read) |
| 118 | medium | NOT_REQUIRED | static | `workflow:security.yml#secrets-scan` | context `Secret Detection` is not a required status check; claim: manifest description says `CI-hard` and 1 check(s) point here via ci_workflow (static + branch protection read) |
| 119 | medium | NOT_REQUIRED | static | `workflow:security.yml#security-audit` | context `Security Configuration Audit` is not a required status check; claim: manifest description says `CI-hard` and 1 check(s) point here via ci_workflow (static + branch protection read) |
| 120 | medium | NOT_REQUIRED | static | `workflow:security.yml#security-summary` | context `Security Summary` is not a required status check; claim: workflow text says `blocking` (static + branch protection read) |
| 121 | medium | NOT_REQUIRED | static | `workflow:test.yml#advanced-parity-tooling` | context `Advanced Parity Tooling` is not a required status check; claim: workflow text says `Required` (static + branch protection read) |
| 122 | medium | NOT_REQUIRED | static | `workflow:test.yml#bats-tests` | context `BATS Unit Tests` is not a required status check; claim: workflow text says `Required` (static + branch protection read) |
| 123 | medium | NOT_REQUIRED | static | `workflow:test.yml#build` | context `Build & Package` is not a required status check; claim: workflow text says `Required` (static + branch protection read) |
| 124 | medium | NOT_REQUIRED | static | `workflow:test.yml#flake-validation` | context `Flake Validation` is not a required status check; claim: workflow text says `Required` (static + branch protection read) |
| 125 | medium | NOT_REQUIRED | static | `workflow:test.yml#harness-first-owner-approval` | context `Harness-First Owner Approval` is not a required status check; claim: workflow text says `Required` (static + branch protection read) |
| 126 | medium | NOT_REQUIRED | static | `workflow:test.yml#harness-sdk-parity` | context `Harness SDK Parity Smoke` is not a required status check; claim: workflow text says `Required` (static + branch protection read) |
| 127 | medium | NOT_REQUIRED | static | `workflow:test.yml#manifest-tests` | context `Manifest test groups (every scripts/testing/test-*)` is not a required status check; claim: workflow text says `Required` (static + branch protection read) |
| 128 | medium | NOT_REQUIRED | static | `workflow:test.yml#nix-static-analysis` | context `Nix Static Analysis` is not a required status check; claim: workflow text says `Required` (static + branch protection read) |
| 129 | medium | NOT_REQUIRED | static | `workflow:test.yml#repo-structure-lint` | context `Repo Structure Lint` is not a required status check; claim: workflow text says `Required` (static + branch protection read) |
| 130 | medium | NOT_REQUIRED | static | `workflow:test.yml#script-header-standards` | context `Script Header Standards` is not a required status check; claim: workflow text says `Required` (static + branch protection read) |
| 131 | medium | NOT_REQUIRED | static | `workflow:test.yml#security` | context `Security Scanning` is not a required status check; claim: manifest description says `CI-hard` and 1 check(s) point here via ci_workflow (static + branch protection read) |
| 132 | medium | NOT_REQUIRED | static | `workflow:test.yml#shellcheck` | context `Shellcheck & Linting` is not a required status check; claim: workflow text says `Required` (static + branch protection read) |
| 133 | medium | NOT_REQUIRED | static | `workflow:test.yml#skill-bundle-parity` | context `Skill Bundle Distribution Smoke` is not a required status check; claim: workflow text says `Required` (static + branch protection read) |
| 134 | medium | NOT_REQUIRED | static | `workflow:test.yml#skill-governance-lint` | context `Skill Governance Lint` is not a required status check; claim: manifest description says `CI-hard` and 3 check(s) point here via ci_workflow (static + branch protection read) |
| 135 | medium | NOT_REQUIRED | static | `workflow:test.yml#smoke-tests` | context `CLI Smoke Tests` is not a required status check; claim: workflow text says `Required` (static + branch protection read) |
| 136 | medium | NOT_REQUIRED | static | `workflow:test.yml#syntax` | context `Syntax Validation` is not a required status check; claim: manifest description says `CI-hard` and 48 check(s) point here via ci_workflow (static + branch protection read) |
| 137 | medium | NOT_REQUIRED | static | `workflow:test.yml#template-placeholder-lint` | context `Template Placeholder Lint` is not a required status check; claim: manifest description says `CI-hard` and 1 check(s) point here via ci_workflow (static + branch protection read) |
| 138 | medium | NOT_REQUIRED | static | `workflow:test.yml#validate-structure` | context `Validate Project Structure` is not a required status check; claim: workflow text says `Required` (static + branch protection read) |
| 139 | medium | NOT_REQUIRED | static | `workflow:validate-shell-scripts.yml#validate-shell-color-echo` | context `Check Color Echo Usage` is not a required status check; claim: manifest description says `CI-hard` and 1 check(s) point here via ci_workflow (static + branch protection read) |
| 140 | medium | NO_BAD_INPUT_TEST | static | `.githooks/pre-merge-commit` | no test names this gate and it is not in the tier0.d mutation suite (static) |
| 141 | medium | NO_BAD_INPUT_TEST | static | `ci-check:aq-report-contract` | no test names this gate and it is not in the tier0.d mutation suite (static) |
| 142 | medium | NO_BAD_INPUT_TEST | static | `ci-check:aq-report-metric-smoke` | no test names this gate and it is not in the tier0.d mutation suite (static) |
| 143 | medium | NO_BAD_INPUT_TEST | static | `ci-check:gitleaks-tree` | no test names this gate and it is not in the tier0.d mutation suite (static) |
| 144 | medium | NO_BAD_INPUT_TEST | static | `ci-check:harness-first-static-gates` | no test names this gate and it is not in the tier0.d mutation suite (static) |
| 145 | medium | NO_BAD_INPUT_TEST | static | `ci-check:skill-external-deps` | no test names this gate and it is not in the tier0.d mutation suite (static) |
| 146 | medium | NO_BAD_INPUT_TEST | static | `ci-check:skill-source-of-truth` | no test names this gate and it is not in the tier0.d mutation suite (static) |
| 147 | medium | NO_BAD_INPUT_TEST | static | `ci-check:skill-template` | no test names this gate and it is not in the tier0.d mutation suite (static) |
| 148 | medium | NO_BAD_INPUT_TEST | static | `ci-check:template-placeholders` | no test names this gate and it is not in the tier0.d mutation suite (static) |
| 149 | medium | NO_BAD_INPUT_TEST | static | `ci-check:validate-echo-colors` | no test names this gate and it is not in the tier0.d mutation suite (static) |
| 150 | medium | NO_BAD_INPUT_TEST | static | `script:scripts/governance/check-cross-surface-contract.py` | no test names this gate and it is not in the tier0.d mutation suite (static) |
| 151 | medium | NO_BAD_INPUT_TEST | static | `script:scripts/governance/check-deprecated-docs-location.sh` | no test names this gate and it is not in the tier0.d mutation suite (static) |
| 152 | medium | NO_BAD_INPUT_TEST | static | `script:scripts/governance/check-doc-lifecycle-hygiene.py` | no test names this gate and it is not in the tier0.d mutation suite (static) |
| 153 | medium | NO_BAD_INPUT_TEST | static | `script:scripts/governance/check-naming-label-consistency.sh` | no test names this gate and it is not in the tier0.d mutation suite (static) |
| 154 | medium | NO_BAD_INPUT_TEST | static | `script:scripts/governance/check-root-script-shim-only.sh` | no test names this gate and it is not in the tier0.d mutation suite (static) |
| 155 | medium | NO_BAD_INPUT_TEST | static | `script:scripts/governance/check-script-header-standards.sh` | no test names this gate and it is not in the tier0.d mutation suite (static) |
| 156 | medium | NO_BAD_INPUT_TEST | static | `script:scripts/governance/check-unattended-sudo-readiness.sh` | no test names this gate and it is not in the tier0.d mutation suite (static) |
| 157 | medium | NO_BAD_INPUT_TEST | static | `script:scripts/governance/check-workflow-script-refs.sh` | no test names this gate and it is not in the tier0.d mutation suite (static) |
| 158 | medium | NO_BAD_INPUT_TEST | static | `script:scripts/governance/lint-agent-auth-policy.py` | no test names this gate and it is not in the tier0.d mutation suite (static) |
| 159 | medium | NO_BAD_INPUT_TEST | static | `script:scripts/governance/lint-color-echo-usage.sh` | no test names this gate and it is not in the tier0.d mutation suite (static) |
| 160 | medium | NO_BAD_INPUT_TEST | static | `script:scripts/governance/verify-profile-cleanup.sh` | no test names this gate and it is not in the tier0.d mutation suite (static) |
| 161 | medium | NO_BAD_INPUT_TEST | static | `script:scripts/testing/check-agent-context-tooling.sh` | no test names this gate and it is not in the tier0.d mutation suite (static) |
| 162 | medium | NO_BAD_INPUT_TEST | static | `script:scripts/testing/check-ai-coordinator-delegate-smoke.sh` | no test names this gate and it is not in the tier0.d mutation suite (static) |
| 163 | medium | NO_BAD_INPUT_TEST | static | `script:scripts/testing/check-aq-integrity-logical-baseline.py` | no test names this gate and it is not in the tier0.d mutation suite (static) |
| 164 | medium | NO_BAD_INPUT_TEST | static | `script:scripts/testing/check-aq-report-runtime-sections.sh` | no test names this gate and it is not in the tier0.d mutation suite (static) |
| 165 | medium | NO_BAD_INPUT_TEST | static | `script:scripts/testing/check-context-bootstrap.sh` | no test names this gate and it is not in the tier0.d mutation suite (static) |
| 166 | medium | NO_BAD_INPUT_TEST | static | `script:scripts/testing/check-dryrun-failure-modes.sh` | no test names this gate and it is not in the tier0.d mutation suite (static) |
| 167 | medium | NO_BAD_INPUT_TEST | static | `script:scripts/testing/check-harness-first-platform-owner-approval.py` | no test names this gate and it is not in the tier0.d mutation suite (static) |
| 168 | medium | NO_BAD_INPUT_TEST | static | `script:scripts/testing/check-harness-first-static-gates.sh` | no test names this gate and it is not in the tier0.d mutation suite (static) |
| 169 | medium | NO_BAD_INPUT_TEST | static | `script:scripts/testing/check-mcp-processes.sh` | no test names this gate and it is not in the tier0.d mutation suite (static) |
| 170 | medium | NO_BAD_INPUT_TEST | static | `script:scripts/testing/check-npm-security-monitor-smoke.sh` | no test names this gate and it is not in the tier0.d mutation suite (static) |
| 171 | medium | NO_BAD_INPUT_TEST | static | `script:scripts/testing/check-remote-profiles.sh` | no test names this gate and it is not in the tier0.d mutation suite (static) |
| 172 | medium | NO_BAD_INPUT_TEST | static | `script:scripts/testing/validate-ai-slo-runtime.sh` | no test names this gate and it is not in the tier0.d mutation suite (static) |
| 173 | medium | NO_BAD_INPUT_TEST | static | `script:scripts/testing/validate-phase-5.2.sh` | no test names this gate and it is not in the tier0.d mutation suite (static) |
| 174 | medium | NO_BAD_INPUT_TEST | static | `script:scripts/testing/validate-runtime-declarative.sh` | no test names this gate and it is not in the tier0.d mutation suite (static) |
| 175 | medium | NO_BAD_INPUT_TEST | static | `script:scripts/testing/validate-skill-references.sh` | no test names this gate and it is not in the tier0.d mutation suite (static) |
| 176 | medium | NO_BAD_INPUT_TEST | static | `script:scripts/testing/verify-dashboard-apis.py` | no test names this gate and it is not in the tier0.d mutation suite (static) |
| 177 | medium | NO_BAD_INPUT_TEST | static | `tier0:gate_aqos_ai_fit_policy` | no test names gate_aqos_ai_fit_policy (static) |
| 178 | medium | NO_BAD_INPUT_TEST | static | `tier0:gate_aqos_golden_profile` | no test names gate_aqos_golden_profile (static) |
| 179 | medium | NO_BAD_INPUT_TEST | static | `tier0:gate_aqos_install_execution_verifier` | no test names gate_aqos_install_execution_verifier (static) |
| 180 | medium | NO_BAD_INPUT_TEST | static | `tier0:gate_aqos_install_resolver` | no test names gate_aqos_install_resolver (static) |
| 181 | medium | NO_BAD_INPUT_TEST | static | `tier0:gate_aqos_module_catalog` | no test names gate_aqos_module_catalog (static) |
| 182 | medium | NO_BAD_INPUT_TEST | static | `tier0:gate_aqos_mysystem_fieldset` | no test names gate_aqos_mysystem_fieldset (static) |
| 183 | medium | NO_BAD_INPUT_TEST | static | `tier0:gate_bash_syntax` | no test names gate_bash_syntax (static) |
| 184 | medium | NO_BAD_INPUT_TEST | static | `tier0:gate_canon_compiler_determinism` | no test names gate_canon_compiler_determinism (static) |
| 185 | medium | NO_BAD_INPUT_TEST | static | `tier0:gate_config_dir_lint` | no test names gate_config_dir_lint (static) |
| 186 | medium | NO_BAD_INPUT_TEST | static | `tier0:gate_cross_surface_contract` | no test names gate_cross_surface_contract (static) |
| 187 | medium | NO_BAD_INPUT_TEST | static | `tier0:gate_deploy_batch_size` | no test names gate_deploy_batch_size (static) |
| 188 | medium | NO_BAD_INPUT_TEST | static | `tier0:gate_env_contract` | no test names gate_env_contract (static) |
| 189 | medium | NO_BAD_INPUT_TEST | static | `tier0:gate_focused_ci_checks` | no test names gate_focused_ci_checks (static) |
| 190 | medium | NO_BAD_INPUT_TEST | static | `tier0:gate_js_syntax` | no test names gate_js_syntax (static) |
| 191 | medium | NO_BAD_INPUT_TEST | static | `tier0:gate_json_syntax` | no test names gate_json_syntax (static) |
| 192 | medium | NO_BAD_INPUT_TEST | static | `tier0:gate_nix_syntax` | no test names gate_nix_syntax (static) |
| 193 | medium | NO_BAD_INPUT_TEST | static | `tier0:gate_python_syntax` | no test names gate_python_syntax (static) |
| 194 | medium | NO_BAD_INPUT_TEST | static | `tier0:gate_qa_phase0` | no test names gate_qa_phase0 (static) |
| 195 | medium | NO_BAD_INPUT_TEST | static | `tier0:gate_repo_structure` | no test names gate_repo_structure (static) |
| 196 | medium | NO_BAD_INPUT_TEST | static | `tier0:gate_roadmap_verification` | no test names gate_roadmap_verification (static) |
| 197 | medium | NO_BAD_INPUT_TEST | static | `tier0:gate_script_headers` | no test names gate_script_headers (static) |
| 198 | medium | NO_BAD_INPUT_TEST | static | `tier0:gate_sql_syntax` | no test names gate_sql_syntax (static) |
| 199 | medium | NO_BAD_INPUT_TEST | static | `tier0:gate_toml_syntax` | no test names gate_toml_syntax (static) |
| 200 | medium | NO_BAD_INPUT_TEST | static | `tier0:gate_ts_syntax` | no test names gate_ts_syntax (static) |
| 201 | medium | NO_BAD_INPUT_TEST | static | `tier0:gate_unattended_sudo_readiness` | no test names gate_unattended_sudo_readiness (static) |
| 202 | medium | NO_BAD_INPUT_TEST | static | `tier0:gate_yaml_syntax` | no test names gate_yaml_syntax (static) |
| 203 | low | FAIL_OPEN | static | `tier0:gate_repo_structure` | verdict comes from grepping the sub-command's output text, not its exit status (static) |
| 204 | low | FAIL_OPEN | static | `tier0:gate_roadmap_verification` | verdict comes from grepping the sub-command's output text, not its exit status (static) |
| 205 | low | MASKED_IN_CI | static | `workflow:confine-tests.yml#confine-tests` | .github/workflows/confine-tests.yml:94 `sudo loginctl enable-linger "$USER" \|\| true  # NON-GATING: best-effort; the syst` annotated NON-GATING (static; mask regex reused from check-workflow-masks) |
| 206 | low | MASKED_IN_CI | static | `workflow:confine-tests.yml#confine-tests` | .github/workflows/confine-tests.yml:95 `sudo systemctl start "user@${uid}.service" \|\| true  # NON-GATING: best-effort; t` annotated NON-GATING (static; mask regex reused from check-workflow-masks) |
| 207 | low | MASKED_IN_CI | static | `workflow:confine-tests.yml#confine-tests` | .github/workflows/confine-tests.yml:100 `cat "/sys/fs/cgroup/user.slice/user-${uid}.slice/user@${uid}.service/cgroup.cont` annotated NON-GATING (static; mask regex reused from check-workflow-masks) |
| 208 | low | MASKED_IN_CI | static | `workflow:nix-build.yml#nix-build` | .github/workflows/nix-build.yml:46 `docker system prune --all --volumes -f 2>/dev/null \|\| true  # NON-GATING: disk c` annotated NON-GATING (static; mask regex reused from check-workflow-masks) |
| 209 | low | MASKED_IN_CI | static | `workflow:security.yml#nix-closure-vuln-scan` | .github/workflows/security.yml:103 `docker system prune --all --volumes -f 2>/dev/null \|\| true  # NON-GATING: disk c` annotated NON-GATING (static; mask regex reused from check-workflow-masks) |
| 210 | low | MASKED_IN_CI | static | `workflow:security.yml#security-audit` | .github/workflows/security.yml:59 `continue-on-error: true  # NON-GATING: PR comment is cosmetic; fork PRs have a r` annotated NON-GATING (static; mask regex reused from check-workflow-masks) |
| 211 | low | MASKED_IN_CI | static | `workflow:test.yml#advanced-parity-tooling` | .github/workflows/test.yml:857 `chmod +x scripts/automation/*.sh scripts/testing/*.sh scripts/security/*.sh scri` annotated NON-GATING (static; mask regex reused from check-workflow-masks) |
| 212 | low | MASKED_IN_CI | static | `workflow:tests.yml#parity-scorecard-gate` | .github/workflows/tests.yml:68 `sudo apparmor_parser -r /etc/apparmor.d/aq-confine-bwrap \|\| true  # NON-GATING: ` annotated NON-GATING (static; mask regex reused from check-workflow-masks) |
| 213 | low | MASKED_IN_CI | static | `workflow:tests.yml#parity-scorecard-gate` | .github/workflows/tests.yml:80 `chmod +x scripts/testing/*.sh scripts/governance/*.sh scripts/automation/*.sh sc` annotated NON-GATING (static; mask regex reused from check-workflow-masks) |
| 214 | low | NO_BAD_INPUT_TEST | static | `ci-check:harness-first-pr-evidence` | named by 2 test(s) but none expresses a failing expectation: scripts/testing/check-harness-first-static-gates.sh, scripts/testing/test-check-harness-first-pr-evidence-gate.py (static) |
| 215 | low | NO_BAD_INPUT_TEST | static | `ci-check:prsi-bootstrap-integrity` | named by 1 test(s) but none expresses a failing expectation: scripts/testing/check-prsi-phase7-static-gates.sh (static) |
| 216 | low | NO_BAD_INPUT_TEST | static | `ci-check:prsi-cycle-contract` | named by 1 test(s) but none expresses a failing expectation: scripts/testing/check-prsi-phase7-static-gates.sh (static) |
| 217 | low | NO_BAD_INPUT_TEST | static | `ci-check:prsi-phase7-static-gates` | named by 1 test(s) but none expresses a failing expectation: scripts/testing/check-context-bootstrap.sh (static) |
| 218 | low | NO_BAD_INPUT_TEST | static | `script:scripts/governance/check-activation-manifest.py` | named by 1 test(s) but none expresses a failing expectation: scripts/testing/test-activation-manifest.py (static) |
| 219 | low | NO_BAD_INPUT_TEST | static | `script:scripts/governance/check-checkout-fresh.sh` | named by 1 test(s) but none expresses a failing expectation: scripts/testing/test-check-checkout-fresh.sh (static) |
| 220 | low | NO_BAD_INPUT_TEST | static | `script:scripts/governance/check-deploy-source.sh` | named by 1 test(s) but none expresses a failing expectation: scripts/testing/test-deploy-source-guard.py (static) |
| 221 | low | NO_BAD_INPUT_TEST | static | `script:scripts/governance/check-flake-age.sh` | named by 2 test(s) but none expresses a failing expectation: scripts/testing/test-check-flake-age.sh, tests/integration/test-phase5-production-hardening.py (static) |
| 222 | low | NO_BAD_INPUT_TEST | static | `script:scripts/governance/check-mergeable.sh` | named by 1 test(s) but none expresses a failing expectation: scripts/testing/test-check-mergeable.sh (static) |
| 223 | low | NO_BAD_INPUT_TEST | static | `script:scripts/testing/check-boot-shutdown-integration.sh` | named by 1 test(s) but none expresses a failing expectation: scripts/testing/check-boot-shutdown-integration.sh (static) |
| 224 | low | NO_BAD_INPUT_TEST | static | `script:scripts/testing/check-dashboard-managed-service.sh` | named by 2 test(s) but none expresses a failing expectation: scripts/testing/check-dashboard-managed-service.sh, scripts/testing/test-aq-slice-helper-contract.sh (static) |
| 225 | low | NO_BAD_INPUT_TEST | static | `script:scripts/testing/check-feedback-loop.sh` | named by 1 test(s) but none expresses a failing expectation: scripts/testing/check-feedback-loop.sh (static) |
| 226 | low | NO_BAD_INPUT_TEST | static | `script:scripts/testing/check-harness-first-evidence-template.sh` | named by 1 test(s) but none expresses a failing expectation: scripts/testing/check-harness-first-static-gates.sh (static) |
| 227 | low | NO_BAD_INPUT_TEST | static | `script:scripts/testing/check-harness-first-pr-evidence-gate.sh` | named by 2 test(s) but none expresses a failing expectation: scripts/testing/check-harness-first-static-gates.sh, scripts/testing/test-check-harness-first-pr-evidence-gate.py (static) |
| 228 | low | NO_BAD_INPUT_TEST | static | `script:scripts/testing/check-harness-first-runbook.sh` | named by 1 test(s) but none expresses a failing expectation: scripts/testing/check-harness-first-static-gates.sh (static) |
| 229 | low | NO_BAD_INPUT_TEST | static | `script:scripts/testing/check-harness-sdk-version-parity.sh` | named by 1 test(s) but none expresses a failing expectation: scripts/testing/smoke-harness-sdk-packaging.sh (static) |
| 230 | low | NO_BAD_INPUT_TEST | static | `script:scripts/testing/check-knowledge-base-breadth.sh` | named by 1 test(s) but none expresses a failing expectation: scripts/testing/check-knowledge-base-breadth.sh (static) |
| 231 | low | NO_BAD_INPUT_TEST | static | `script:scripts/testing/check-mcp-health.sh` | named by 2 test(s) but none expresses a failing expectation: scripts/testing/check-mcp-health.sh, scripts/testing/test-check-mcp-health-defaults.sh (static) |
| 232 | low | NO_BAD_INPUT_TEST | static | `script:scripts/testing/check-package-count-drift.sh` | named by 1 test(s) but none expresses a failing expectation: scripts/testing/check-package-count-drift.sh (static) |
| 233 | low | NO_BAD_INPUT_TEST | static | `script:scripts/testing/check-prsi-budget-discipline.sh` | named by 2 test(s) but none expresses a failing expectation: scripts/testing/check-prsi-phase7-static-gates.sh, scripts/testing/test-prsi-queue-path-ssot.py (static) |
| 234 | low | NO_BAD_INPUT_TEST | static | `script:scripts/testing/check-prsi-confidence-calibration.sh` | named by 1 test(s) but none expresses a failing expectation: scripts/testing/check-prsi-phase7-static-gates.sh (static) |
| 235 | low | NO_BAD_INPUT_TEST | static | `script:scripts/testing/check-prsi-eval-pinning.sh` | named by 1 test(s) but none expresses a failing expectation: scripts/testing/check-prsi-phase7-static-gates.sh (static) |
| 236 | low | NO_BAD_INPUT_TEST | static | `script:scripts/testing/check-prsi-high-risk-approval-rubric.sh` | named by 1 test(s) but none expresses a failing expectation: scripts/testing/check-prsi-phase7-static-gates.sh (static) |
| 237 | low | NO_BAD_INPUT_TEST | static | `script:scripts/testing/check-prsi-quarantine-workflow.sh` | named by 1 test(s) but none expresses a failing expectation: scripts/testing/check-prsi-phase7-static-gates.sh (static) |
| 238 | low | NO_BAD_INPUT_TEST | static | `script:scripts/testing/check-prsi-validation-matrix.sh` | named by 1 test(s) but none expresses a failing expectation: scripts/testing/check-prsi-phase7-static-gates.sh (static) |
| 239 | low | NO_BAD_INPUT_TEST | static | `script:scripts/testing/check-routing-fallback.sh` | named by 1 test(s) but none expresses a failing expectation: scripts/testing/validate-runtime-declarative.sh (static) |
| 240 | low | NO_BAD_INPUT_TEST | static | `script:scripts/testing/validate-autonomous-loop-gates.sh` | named by 1 test(s) but none expresses a failing expectation: scripts/testing/validate-autonomous-loop-gates.sh (static) |
| 241 | low | NO_BAD_INPUT_TEST | static | `script:scripts/testing/validate-genai-observability.sh` | named by 1 test(s) but none expresses a failing expectation: scripts/testing/telemetry-smoke-test.sh (static) |
| 242 | low | NO_BAD_INPUT_TEST | static | `script:scripts/testing/validate-query-agent-storage-learning.sh` | named by 1 test(s) but none expresses a failing expectation: scripts/testing/validate-query-agent-storage-learning.sh (static) |
| 243 | low | NO_BAD_INPUT_TEST | static | `script:scripts/testing/verify-self-consistency.py` | named by 1 test(s) but none expresses a failing expectation: scripts/testing/verify-self-consistency.py (static) |
| 244 | info | NOT_REQUIRED | static | `workflow:memory-benchmarks.yml#memory-benchmark-regressions` | context `Memory Benchmark Regressions` is not a required status check; claim: none found (static + branch protection read) |
| 245 | info | NOT_REQUIRED | static | `workflow:nix-build.yml#nix-build` | context `Build NixOS Configuration` is not a required status check; claim: none found (static + branch protection read) |
| 246 | info | NOT_REQUIRED | static | `workflow:shellcheck.yml#shellcheck` | context `ShellCheck Analysis` is not a required status check; claim: none found (static + branch protection read) |
| 247 | info | NOT_REQUIRED | static | `workflow:test-coverage.yml#targeted-coverage` | context `targeted-coverage` is not a required status check; claim: none found (static + branch protection read) |
| 248 | info | NOT_REQUIRED | static | `workflow:tests-legacy.yml#integration-tests` | context `Integration Tests` is not a required status check; claim: none found (static + branch protection read) |
| 249 | info | NOT_REQUIRED | static | `workflow:tests-legacy.yml#unit-tests` | context `Unit Tests` is not a required status check; claim: none found (static + branch protection read) |
| 250 | info | NOT_REQUIRED | static | `workflow:tests.yml#flake-first-roadmap-verifier` | context `flake-first-roadmap-verifier` is not a required status check; claim: none found (static + branch protection read) |
| 251 | info | NOT_REQUIRED | static | `workflow:tests.yml#parity-scorecard-gate` | context `parity-scorecard-gate` is not a required status check; claim: none found (static + branch protection read) |
| 252 | info | NOT_REQUIRED | static | `workflow:tests.yml#repo-structure-lint` | context `repo-structure-lint` is not a required status check; claim: none found (static + branch protection read) |
| 253 | info | NOT_REQUIRED | static | `workflow:tests.yml#unit-tests` | context `unit-tests` is not a required status check; claim: none found (static + branch protection read) |
| 254 | info | NOT_REQUIRED | static | `workflow:validate-shell-scripts.yml#shellcheck` | context `ShellCheck linting` is not a required status check; claim: none found (static + branch protection read) |

### Exercised (throwaway clone, one seeded bad input each)

| Probe | Gate | Seed | Outcome | rc | Detail |
|---|---|---|---|---|---|
| collect-staged-control | `tier0:collect_changed_files` | staged bad.py, --pre-commit (control) | CONTROL_OK | 1 |  |
| collect-no-origin | `tier0:collect_changed_files` | committed bad.py, --pre-deploy, no origin/main | PASSED_ON_BAD_INPUT | 0 |  |
| deploy-batch-zero | `tier0:gate_deploy_batch_size` | 0 commits ahead of origin/main (batch too small) | PASSED_ON_BAD_INPUT | 0 |  |
| root-shim-rogue | `script:scripts/governance/check-root-script-shim-only.sh` | scripts/rogue.sh that is not a compatibility shim | FAILED_AS_EXPECTED | 1 | [root-script-shim] FAIL: scripts/rogue.sh is not a compatibility shim / [root-script-shim] FAIL: 1 root script(s) violate shim-only policy. |
| script-header-missing | `script:scripts/governance/check-script-header-standards.sh` | new script with no shebang and no purpose line, --all | FAILED_AS_EXPECTED | 1 | [script-header] FAIL scripts/governance/zz-nohdr.sh: missing shebang on first line |
| precommit-secret | `.githooks/pre-commit` | staged file holding an AKIA-shaped key, on a non-main branch | FAILED_AS_EXPECTED | 1 | [90m10:19PM[0m [33mWRN[0m [1mleaks found: 1[0m / pre-commit: gitleaks (CI-parity, .gitleaks.toml) blocked staged secrets. Fix and re-stage, or SKIP_SECRET_SCAN=1 (development only). |
| premerge-guard-missing | `.githooks/pre-merge-commit` | shallow-merge guard script absent | PASSED_ON_BAD_INPUT | 0 | pre-merge-commit: WARN missing /tmp/sweep-gates-hrkucqzf/w-premerge-guard-missing/scripts/governance/check-mergeable.sh — skipping shallow-merge guard |

### Unknown / not determined (never counted as pass)

- none

### Env-var bypasses noted (not classed)

- .githooks/pre-commit: env bypass `AQ_ALLOW_MAIN_CHECKOUT_COMMIT`
- .githooks/pre-commit: env bypass `AQ_DELEGATE_HANDBACK`
- .githooks/pre-commit: env bypass `SKIP_CVE_SCAN`
- .githooks/pre-commit: env bypass `SKIP_SECRET_SCAN`
- .githooks/pre-push: env bypass `SKIP_PRE_PUSH_LINT`
- .githooks/pre-push: env bypass `SKIP_PRE_PUSH_SYNC_CHECK`

### Static versus exercised

- Static: every CANNOT_FAIL, NO_BAD_INPUT_TEST, FAIL_OPEN (except tool absence), MASKED_IN_CI, UNCOVERED and NOT_REQUIRED row is text or YAML analysis of this tree. Heuristics can misjudge a script that fails through an indirect command; each row names what matched.
- Exercised: the probe table, tool presence via `shutil.which` on this host, and the branch-protection read.
- Not exercised: every other gate (no tier0 run, no `run-ci-checks.sh --all`, no hook against a real commit, no live-stack gate); tool availability in the GitHub runner image is unknown.

## Rollback Plan
Delete this report, the sweep script, its test and the manifest entry; nothing else was changed.
