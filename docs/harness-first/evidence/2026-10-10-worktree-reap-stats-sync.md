# Evidence: Worktree Reap Stats Disk Measurement and Plan Synchronization

## Context
Date: 2026-10-10
Slice: `fix/worktree-reap-stats-undercount`
Component: `scripts/ai/aq-worktree-reap`, `scripts/testing/test-aq-worktree-reap.py`, `.agent/memory/issues-backlog.md`
Implementation Lane: Antigravity

## Problem
In `scripts/ai/aq-worktree-reap`:
1. `stats.bytes_freed` computed disk usage via `Path(wt.path).rglob("*")` *after* `remove_worktree` deleted the worktree, guaranteeing that 0 bytes were reported as freed even after removing large trees.
2. In `--apply --json` mode, `plan["stats"]` was serialized via `asdict(stats)` prior to executing worktree removals and graph archiving. As a result, the reported JSON stats in CI and automation always reported 0 graphs archived and 0 bytes freed.

## Solution
1. **Pre-deletion Size Calculation**:
   - Calculated worktree directory disk size before invoking `remove_worktree()`, adding `wt_bytes` to `stats.bytes_freed` upon successful removal.
2. **Stats Synchronization in Plan**:
   - Synchronized `plan["stats"] = asdict(stats)` following all applied removals and graph archiving operations before JSON serialization.
3. **Unit Test Suite**:
   - Added `TestReapStatsSynchronization` in `scripts/testing/test-aq-worktree-reap.py` ensuring `plan["stats"]["bytes_freed"]` is strictly positive and accurately tracks freed payload files during `--apply`.
4. **Issues Backlog**:
   - Updated `.agent/memory/issues-backlog.md` marking `aq-worktree-reap-stats-undercount` as `[FIXED 2026-10-10]`.

## Validation Evidence
- `python3 scripts/testing/test-aq-worktree-reap.py`: PASS (7/7 tests passed in 0.57s).
- `scripts/governance/tier0-validation-gate.sh --pre-commit`: PASS (55/55 checks passed).
