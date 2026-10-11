# Evidence: Chat/Batch Parity Re-Pin and Issues Backlog Reconciliation

## Context
Date: 2026-10-10
Slice: `fix/chat-batch-parity-repin-and-backlog-reconcile`
Component: `scripts/testing/fixtures/local-inference-chat-batch-parity-golden.json`, `scripts/security/rsi-intake-code-scanning.py`, `.agent/memory/issues-backlog.md`
Implementation Lane: Antigravity

## Problem
1. **Chat/Batch Parity Test Failure**:
   - `scripts/testing/test-local-inference-chat-batch-parity.py` failed with predecessor hash mismatch on `scripts/ai/aq-chat`. In commit `8a955e16`, `aq-chat` was updated to incorporate invocation logging, changing its digest without re-pinning in the golden manifest.
2. **RSI Intake Wrong Flake Path in Root Fix**:
   - In `scripts/security/rsi-intake-code-scanning.py`, `root_fix` template stated `flake.lock under nix/` (which does not exist; `flake.lock` is at the repository root) and formatted unknown versions as `>=unknown`.
3. **Issues Backlog Stale Entries**:
   - Comprehensive audit of `.agent/memory/issues-backlog.md` revealed 28 stale `- [OPEN]` entries that had already been resolved on `origin/main` across earlier commits and PRs.

## Solution
1. **Re-pin Chat/Batch Parity Golden Fixture**:
   - Updated `scripts/ai/aq-chat` sha256 to `b0181653b767757cc3b5954ccb1ee256b25af52a7c5f3abf7ed3960fdafe8fae` in `scripts/testing/fixtures/local-inference-chat-batch-parity-golden.json`.
   - Recomputed `manifest_digest` to `3a2815d5aa5b31713036e695bbd21831bbafb6eb8545dae5cb7a631ef81d7c74`.
2. **Correct Flake Path and Target Version Formatting**:
   - Updated `scripts/security/rsi-intake-code-scanning.py:311` to specify `flake.lock at repo root` and format `target_ver` cleanly.
3. **Reconcile Issues Backlog**:
   - Updated stale entries in `.agent/memory/issues-backlog.md` to `[FIXED ...]` with exact commit SHAs, test proofs, and verified PR numbers.

## Validation Evidence
- `python3 scripts/testing/test-local-inference-chat-batch-parity.py`: PASS (12 pairs compared, 0 failures).
- `python3 scripts/testing/test-rsi-intake-code-scanning.py`: PASS (11/11 tests).
- `python3 scripts/testing/test-aq-closure-scan.py`: PASS (18/18 tests).
- `scripts/governance/tier0-validation-gate.sh --pre-commit`: 55/55 checks PASS.
