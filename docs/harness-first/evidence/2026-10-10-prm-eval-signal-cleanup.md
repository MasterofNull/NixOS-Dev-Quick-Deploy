# Evidence: PRM Evaluation Harness Signal Cleanup and Agent Process Reaping

## Context
Date: 2026-10-10
Slice: `fix/prm-eval-signal-cleanup`
Plan: `frontier-evidence-intake`
Component: `scripts/ai/aq-prm-eval`, `scripts/testing/test-prm-eval-harness.py`

## Problem
When `aq-prm-eval` was interrupted via SIGTERM or SIGINT (such as when an operator cancels a long-running eval or a supervisor stops the job), the subprocess wrapper and any detached agent processes (spawned via `setsid`) remained alive in the background. Because local agent inference shares a single APU slot, these orphan processes caused slot saturation, cross-run file contention, and invalid evaluations.

## Solution
1. **Signal Handling and Emergency Cleanup**:
   - Implemented `emergency_cleanup()` in `scripts/ai/aq-prm-eval` to terminate `_ACTIVE_PROC` process groups via `_kill_pids` and reap all live agent PIDs from `_ACTIVE_DELEG / registry.jsonl`.
   - Bound `emergency_cleanup()` to `signal.SIGTERM`, `signal.SIGINT`, and Python `atexit`.
   - Ensured active process and delegation path are safely tracked in `run_arm` and cleaned up on early exit.

2. **Test Coverage**:
   - Extended `scripts/testing/test-prm-eval-harness.py` with test cases verifying:
     - Direct `emergency_cleanup()` kills both active subprocess groups and detached agent processes.
     - Signal handler exits with standard exit code `128 + signum` while terminating all active process trees.

3. **Plan Tracking**:
   - Reconciled `.agents/plans/frontier-evidence-intake/tracker.json` item `fe-1-prm-verify` with commit matching and evidence references, projecting progress accurately at 81% (8/10 shipped).

## Validation Evidence
- `python3 scripts/testing/test-prm-eval-harness.py`: All 17 unit checks PASS (including emergency cleanup and signal handler tests).
- `python3 scripts/ai/aq-prm-eval --dry-run`: PASS (fixtures valid, arms off/on validated).
- `scripts/governance/tier0-validation-gate.sh --pre-commit`: 55/55 checks PASS.
