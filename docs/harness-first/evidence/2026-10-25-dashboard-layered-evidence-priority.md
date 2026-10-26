# Evidence: Dashboard OSI Layered Health Evidence Precedence

## Objective
Fix the OSI layer health endpoint (`/api/health/layered`) to check and serve authoritative host QA evidence from `QAEvidenceStore` prior to falling back to in-memory cache hits, ensuring sandboxed/confined execution runs cannot permanently cache and serve 27 false failures to operators.

## Workflow/Session IDs
- Session ID: `57a807e7-c3e6-4e8e-833b-ce38fb8d47cd`
- PRD: `PRD-HEALTH-SPIDER-AUTONOMOUS-HEALING.md`
- Branch: `fix/dashboard-layered-authoritative-evidence-cache`

## Delegation Decision
- Implementer: Antigravity orchestrator in isolated git branch.
- Reviewer: Codex independent parity check.

## Commands Executed
- `python3 scripts/testing/test-dashboard-layered-health-precedence.py`
- `bash scripts/governance/tier0-validation-gate.sh --pre-commit`

## Validation Evidence
- Unit test passed: `test-dashboard-layered-health-precedence.py` (verified that `_load_persisted_qa_results` takes priority over stale `_layered_cache`).
- Direct invocation returns 204 passed and 1 failed matching host state.
- Tier 0 pre-commit gate passed (71/71 checks pass).

## Rollback Plan
- Revert commit on `fix/dashboard-layered-authoritative-evidence-cache` or restore prior commit on `main`.

## Residual Risk
- The live systemd service `command-center-dashboard-api.service` requires an in-flight reload or restart (`sudo systemctl restart command-center-dashboard-api.service`) to swap Python code in memory.

## Hint Feedback
- `QAEvidenceStore.production().read_latest()` provides tamper-verified host evidence with SHA verification, ideal as an authoritative cache anchor.
