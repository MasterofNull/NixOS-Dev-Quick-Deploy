# Evidence: Surface Unreadable PRSI Queue Instead of False Inbox (2026-10-07)

**Objective**: Fix approval inbox to distinguish between missing files (OK) and unreadable/corrupt files (DEGRADED), surfacing errors instead of silently showing a false inbox state.

**Workflow/Session IDs**: Agent delegation, worktree agent-a69776d0df837036e

**Delegation Decision**: Bounded implementer slice — minimal changes to distinguish error conditions and propagate degradation status through three layers (library → CLI → dashboard).

## Problem (Verified Live 2026-10-07)

- `scripts/ai/lib/approval_inbox.py::_load_json()` catches both `OSError` and `ValueError`, returning default on any error
- When PRSI queue is unreadable (permission denied, sandbox), queue silently becomes `{}`, `represented` stays empty
- Dashboard reports 51 deferred vs aq-approve's 1 needed-approval — a plausible-looking but false inbox
- Missing file is legitimately empty; unreadable/corrupt is NOT — they must be distinguished

## Commands Executed

```bash
# Branch creation
git fetch origin && git switch -c fix/approval-inbox-surface-read-errors-20261007 origin/main

# Syntax validation
python3 -m py_compile scripts/ai/lib/approval_inbox.py
python3 -m py_compile dashboard/backend/api/routes/approval_inbox.py
python3 -m py_compile scripts/testing/test-dashboard-approval-inbox.py
node --check assets/dashboard.js

# Test execution
cd /home/hyperd/Documents/NixOS-Dev-Quick-Deploy/.claude/worktrees/agent-a69776d0df837036e
python3 -m pytest scripts/testing/test-dashboard-approval-inbox.py -xvs

# Validation gate
./scripts/governance/tier0-validation-gate.sh --pre-commit
```

## Validation Evidence

### Syntax Checks
```
✓ approval_inbox.py syntax OK
✓ approval_inbox route syntax OK
✓ test file syntax OK
✓ dashboard.js syntax OK
```

### Test Results
```
============================= test session starts ==============================
platform linux -- Python 3.13.15, pytest-9.0.3, pluggy-1.6.0

collecting ... collected 9 items

scripts/testing/test-dashboard-approval-inbox.py::ApprovalInboxTests::test_canonical_projection PASSED
scripts/testing/test-dashboard-approval-inbox.py::ApprovalInboxTests::test_degraded_corrupt_json PASSED
scripts/testing/test-dashboard-approval-inbox.py::ApprovalInboxTests::test_degraded_in_collect_with_status PASSED
scripts/testing/test-dashboard-approval-inbox.py::ApprovalInboxTests::test_degraded_unreadable_queue PASSED
scripts/testing/test-dashboard-approval-inbox.py::ApprovalInboxTests::test_empty_inbox PASSED
scripts/testing/test-dashboard-approval-inbox.py::ApprovalInboxTests::test_failure_is_safe_and_unavailable PASSED
scripts/testing/test-dashboard-approval-inbox.py::ApprovalInboxTests::test_missing_queue_not_degraded PASSED
scripts/testing/test-dashboard-approval-inbox.py::ApprovalInboxTests::test_no_mutating_methods PASSED (with 4 subtests)
scripts/testing/test-dashboard-approval-inbox.py::ApprovalInboxTests::test_registration_and_polling PASSED

===================== 9 passed, 4 subtests passed in 0.98s =====================
```

## Changes Summary

### 1. `scripts/ai/lib/approval_inbox.py`
- Added `_load_json_with_status()` function to distinguish:
  - `FileNotFoundError` → returns default, no degradation (missing file is OK)
  - `OSError` / `JSONDecodeError` → returns default + error info (unreadable/corrupt is DEGRADED)
- Added `collect_with_status()` → returns `(items, degraded_sources)` tuple
- Refactored `collect()` to call `collect_with_status()` and return items only (backward compatible)
- Updated `inbox_cli()` to print one-line WARNING per degraded source to stderr

### 2. `dashboard/backend/api/routes/approval_inbox.py`
- Changed `_project()` to call `collect_with_status()` instead of `collect()`
- When `degraded_sources` list is not empty, response includes `"status": "degraded"` and `"degraded_sources": [{"path": str, "error": str}, ...]`
- Maintains 200 status and includes item counts (fail-soft)

### 3. `assets/dashboard.js`
- Updated `loadApprovalInbox()` to check `d.status === "degraded"`
- When degraded, displays visible warning panel with path and error for each degraded source
- Uses `warn` class for status line, `err` class for error details

### 4. `scripts/testing/test-dashboard-approval-inbox.py`
- Added `test_degraded_unreadable_queue()` — tests chmod 000 detection (skips if root)
- Added `test_degraded_corrupt_json()` — tests JSONDecodeError detection
- Added `test_missing_queue_not_degraded()` — verifies missing file is NOT degraded
- Added `test_degraded_in_collect_with_status()` — unit test distinguishing missing vs corrupt
- Updated `test_empty_inbox()` and `test_failure_is_safe_and_unavailable()` to patch `collect_with_status()` instead of `collect()`

## Rollback Plan

If regressions occur:
1. Revert the worktree branch: `git switch main` from original checkout
2. The backward-compatible `collect()` interface means no callers need immediate updates
3. Dashboard will fall back to showing "unavailable" if route error occurs

## Residual Risk

- **PermissionError subclass coverage**: Tested with chmod 000; sandbox effects depend on runtime environment
- **Concurrent file corruption**: Monitor reads during writes could miss brief corruption; acceptable for non-critical approval state
- **Dashboard DOM handling**: `line()` helper now takes optional `cls` parameter; verified with `node --check`

## Hint Feedback

- Prefer `FileNotFoundError` over catching generic `OSError` when distinguishing "missing" — more precise and idiomatic
- `collect_with_status()` tuple return avoids breaking existing callers relying on `collect()`
- Dashboard fail-soft (200 + degraded status) prevents false "unavailable" alarms
