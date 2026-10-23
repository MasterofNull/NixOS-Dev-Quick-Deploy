# Evidence: Factory Kit K10 — Worktree Helper, Learn Command, and Canon Core Rules

**Date**: 2026-10-22
**Author**: antigravity
**Reviewer**: codex
**Subject**: Slice K10 (`software-dev-factory-rollout`)

## 1. Objective
Complete Slice K10 of `software-dev-factory-rollout`:
- Implement `aq-factory learn`: scans consumer repo, detects active technology stacks (node, python, rust, go, nix), and writes project facts to `.agent/memory/project-facts.json`.
- Implement `aq-factory worktree`: creates isolated worktrees with dedicated branch creation from specified bases, preventing direct main edits per Delivery Workflow contracts.

## 2. Test Execution & Results
- Unit test suite: `scripts/testing/test-factory-kit-k10.py`
  - Execution command: `python3 scripts/testing/test-factory-kit-k10.py`
  - Result: 2/2 tests passed (0 errors, 0 failures, 0.609s).
  - Validation:
    1. `test_learn_command`: verified automated multi-stack detection and json fact extraction into `.agent/memory/`.
    2. `test_worktree_command`: verified clean `git worktree add` execution and directory setup.

## 3. Ground Truth Attestation (Rule 15 DoD)
1. **Integrated**: Callable directly via CLI: `aq-factory learn` and `aq-factory worktree <name> [--base <ref>] [--dir <path>]`.
2. **Turned ON**: Enabled and operational in `scripts/ai/aq-factory`.
3. **Validated Real-World**: Verified against clean git repository fixtures in automated test suite.
4. **Observable**: Emits structured JSON facts or informative CLI output.
5. **Intervenable**: Dry-run supported for both learn and worktree creation.
6. **PM-Tracked**: Projected in `.agents/plans/software-dev-factory-rollout/tracker.json` (9/11 slices complete, 85% progress).
