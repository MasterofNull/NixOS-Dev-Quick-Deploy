# Harness-First Task Evidence

Date: 2026-09-26
Task ID: CI-20260926-REMEDIATION

## Objective
- Resolve failing GitHub Actions checks on main:
  1. Syntax validation and PR evidence gate failure on high-impact paths.
  2. Stale workflow script references to deprecated/archived scripts (`smoke-cross-client-compat.sh`, `validate-flake-inputs.sh`, `validate-tool-management-policy.sh`, `validate-config-settings.sh`, `smoke-skill-bundle-distribution.sh`, `check-harness-sdk-version-parity.sh`, `lint-timeouts.sh`).
  3. Skill governance unpinned installer URL lint.
  4. Flake check assertion failures on `aqos-vm-ai-dev`.
  5. Parity scorecard dependencies and missing `.claude/settings.json`.
  6. Unit test dependency conflicts between `pytest>=9.0.3` and `pytest-asyncio==0.23.8`.
  7. Dockerfile hadolint errors and Trivy image build failures.
  8. Gitleaks secret detection allowlist for fixtures and local worktrees.
  9. Untracked submodule gitlink causing exit code 128.
  10. Stale archived script references in advanced parity suite (`check-failed-units-classification.sh`, `check-prsi-phase7-program.sh`, `smoke-cross-client-compat.sh`, `smoke-skill-bundle-distribution.sh`) and guarded Trivy custom image table scanner.
  11. Harness SDK packaging smoke A2A methods check (`smoke-harness-sdk-packaging.sh`) following `extensions/harness_sdk.py` after domain-split refactor.
  12. Missing `httpx`, `aiohttp`, `requests` in `parity-scorecard-gate` runner environment.
  13. Target resolution in `check-dryrun-failure-modes.sh` mapping `nixos-ai-dev` to canonical `hyperd-ai-dev`.
  14. Golden evals version check in `run-harness-regression-gate.sh` accepting version >= 1.

## Workflow/Session IDs
- Workflow ID: ci-failure-resolution
- Session ID: b035cb17-3ae5-4b00-8934-dfcbe4f0c0dc

## Delegation Decision
- Local-first triage, implementation, and gate validation.
- Direct remediation of workflow definitions, requirements constraints, test fixtures, and flake configurations.

## Commands Executed
```bash
scripts/governance/check-workflow-script-refs.sh
nix flake check --offline --no-build .
./scripts/testing/check-package-count-drift.sh
./scripts/testing/harness-runner.sh --offline --skip-schema
pytest ai-stack/mcp-servers/hybrid-coordinator/tests/ -q
./scripts/testing/smoke-harness-sdk-packaging.sh
./scripts/automation/run-harness-regression-gate.sh --offline
./scripts/testing/check-dryrun-failure-modes.sh --flake-ref . --nixos-target hyperd-ai-dev
nix shell nixpkgs#gitleaks -c gitleaks detect --redact --config .gitleaks.toml --source . --no-git
nix shell nixpkgs#hadolint -c hadolint --failure-threshold error ai-stack/mcp-servers/*/Dockerfile
scripts/governance/tier0-validation-gate.sh --pre-commit
FORCE_HARNESS_FIRST_EVIDENCE_GATE=true BASE_REF=origin/main scripts/testing/check-harness-first-pr-evidence-gate.sh
```

## Validation Evidence
- `scripts/governance/check-workflow-script-refs.sh`: PASS (0 dangling references in 11 workflows).
- `nix flake check --offline --no-build .`: PASS (all checks passed).
- `./scripts/testing/check-package-count-drift.sh`: PASS (zero package count drift).
- `./scripts/testing/harness-runner.sh --offline --skip-schema`: PASS (2 passed, 0 failed, 2 skipped).
- `pytest ai-stack/mcp-servers/hybrid-coordinator/tests/ -q`: PASS (208 passed).
- `./scripts/testing/smoke-harness-sdk-packaging.sh`: PASS (python, js/ts, A2A methods, docs, and packages build cleanly).
- `./scripts/automation/run-harness-regression-gate.sh --offline`: PASS (golden eval schema passed).
- `./scripts/testing/check-dryrun-failure-modes.sh`: PASS (known dry-run failure modes validated).
- `gitleaks detect`: PASS (0 leaks found).
- `hadolint --failure-threshold error`: PASS (all MCP Dockerfiles).
- `scripts/governance/tier0-validation-gate.sh --pre-commit`: PASS (53 passed, 0 failed).
- `scripts/testing/check-harness-first-pr-evidence-gate.sh`: PASS (harness-first PR evidence gate satisfied).

## Rollback Plan
- Revert the commit on `factory/resolve-ci-check-failures` branch if needed.
- Restore baseline workflows and configurations.

## Residual Risk
- Low: all modified scripts, workflows, and requirements were validated against local nix evaluation, hadolint, gitleaks, and tier0 test suites.

## Hint Feedback
- Hint IDs used: none recorded for this change.
- Helpful/unhelpful feedback summary: n/a (remediation of existing CI gates and test suites).
