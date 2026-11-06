## Objective
Prove every scripts/governance/tier0.d gate can fail (P0.8 of system-integrity-recovery: "every tier0.d gate has a test proving it can fail"). A gate that cannot fail reads green while checking nothing.

## Workflow/Session IDs
Plan .agents/plans/system-integrity-recovery, slice P0.8. Branch test/gate-mutation-p08. Date 2026-11-05. Inventory and report: .agents/delegation/outputs/p08-gate-mutation/.

## Delegation Decision
Implementer: Claude Sonnet (Rule 17). Orchestrator dispatched the slice; bounded to one new test file and its manifest registration.

## Commands Executed
- python3 scripts/testing/test-tier0d-gate-mutation.py
- bash scripts/governance/tier0.d/check-ci-test-coverage.sh
- python3 scripts/testing/run-test-group.py tests-misc-s-z
- scripts/governance/run-ci-checks.sh --changed --base origin/main

## Validation Evidence
Inventory of 23 gates: 9 already have a bad-input test elsewhere (named in COVERED_ELSEWHERE), 14 had none or only good-path/library-level tests and are now mutated by scripts/testing/test-tier0d-gate-mutation.py (36 cases, each gate with a known-good and a known-bad or warn case, run from a copied gate inside a throwaway git repo). A meta-check fails when any file in tier0.d is in neither table, so a new gate needs a mutation test. Registered in config/ci-checks.json group tests-misc-s-z (tests and paths). Results: see the report for pasted output.
Findings: no gate is unconditionally green, but several only fail in narrow conditions (see Residual Risk).

## Rollback Plan
Revert the new test file and the three lines added to config/ci-checks.json. No runtime or data change.

## Residual Risk
check-config-contracts.sh passes ("no registered config schemas") when the registry import raises, so a broken contracts package disables it silently. check-owned-scope.sh exits 0 unless OWNED_PATHS is set and WARN-skips without cargo. check-sops-sync.sh and check-dependency-cve.sh exit 0 when the SOPS file, npm, or the manifest change is absent, so they do nothing in CI. check-tool-pins-skew.sh never reads the pins in config/tool-pins.json beyond existence. These are recorded, not fixed here. Warn-class gates (commit-evidence-warn, shallow-repo, lane-hook-parity) are advisory by design and are tested for their WARN signal.

## Hint Feedback
No hints were consulted for this slice.
