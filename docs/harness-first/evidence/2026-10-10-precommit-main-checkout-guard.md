# Evidence: Pre-Commit Primary Checkout Main Guard

## Context
Date: 2026-10-10
Slice: `feat/precommit-main-checkout-guard`
Component: `.githooks/pre-commit`, `scripts/testing/test-precommit-main-checkout-guard.py`
Implementer Task: `antigravity-20261010-170154-am6w3f`

## Problem
Per canonical delivery workflow (`canon/blocks/delivery-workflow.md`), all changes must be developed in branch-bound worktrees and land via PR. Previously, no git hook prevented an agent or operator session from committing directly to `main` in the primary checkout, leading to checkout drift and potential conflict regressions.

## Solution
1. **Primary-Checkout Main Guard**:
   - Added an early guard in `.githooks/pre-commit` refusing commits with an informative message if:
     - Branch is `main` (`git symbolic-ref --short -q HEAD`).
     - Repository is the primary checkout (`git rev-parse --git-dir` equals `git rev-parse --git-common-dir`).
     - `AQ_ALLOW_MAIN_CHECKOUT_COMMIT` is not set to `1`.
     - In-progress merge (`MERGE_HEAD`) is absent.
   - Allows commits on feature branches, linked worktrees, merge commits, and explicit override `AQ_ALLOW_MAIN_CHECKOUT_COMMIT=1` (for administrative maintenance such as lockfile refreshes).
2. **Behavioural Test Suite**:
   - Added `scripts/testing/test-precommit-main-checkout-guard.py` creating isolated temporary repositories and verifying:
     - Direct commit on `main` in primary checkout fails closed.
     - Direct commit on `main` in primary checkout succeeds with `AQ_ALLOW_MAIN_CHECKOUT_COMMIT=1`.
     - Direct commit on a feature branch succeeds.
     - Commit inside a linked worktree (including on `main`) succeeds.

## Validation Evidence
- `bash -n .githooks/pre-commit`: PASS (syntax valid).
- `python3 scripts/testing/test-precommit-main-checkout-guard.py`: PASS (all 4 cases verified).
- `scripts/governance/tier0-validation-gate.sh --pre-commit`: 55/55 checks PASS.
