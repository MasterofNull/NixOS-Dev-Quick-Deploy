# Evidence: SOTA Performance Regression Gate (Slice 1)

Date: 2026-10-22
Author: Antigravity / Claude
Reviewer: Codex
Scope: SOTA Tier Elevation (`sota-perf-regression-gates`)

## Summary
Implements `check-perf-regression.sh` in `scripts/governance/tier0.d/` fulfilling backlog item `[OPEN] sota-perf-regression-gates`:
1. **Sub-millisecond Fast Path**: Instantly exits 0 if no staged changes touch hot-path servers (`ai-stack/switchboard/`, `ai-stack/hybrid-coordinator/`).
2. **Cycle 1 WARN-Only Mode**: Prevents blocking pre-commit gates while establishing baseline execution telemetry.
3. **Automated Verification**: Accompanied by unit test `scripts/testing/test-perf-regression-gate.py`.

## DoD Attestation
- [x] Integrated: Auto-discovered by `tier0-validation-gate.sh`.
- [x] Turned ON: Executable and enabled in `tier0.d/`.
- [x] Functionally validated: `test-perf-regression-gate.py` passes (0.02s).
- [x] Observable: Prefixed output `[tier0.d/check-perf-regression]`.
- [x] Intervenable: Constant time bypass on non-intersecting edits.
