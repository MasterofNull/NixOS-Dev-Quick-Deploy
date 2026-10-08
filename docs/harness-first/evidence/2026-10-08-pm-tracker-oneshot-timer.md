# PM Tracker Oneshot Service Projection Fix — Evidence

**Date:** 2026-10-08
**Objective:** Fix PM projector to correctly honor timer-triggered oneshot services with empty timestamps
**Session ID:** bounded-fix

## Problem Statement

The PM projector (`scripts/ai/aq-pm-tracker`) was incorrectly projecting timer-driven oneshot services as IN-PROGRESS 40, even when:
- Service Result=success
- Owner had accepted the service
- Timer had been triggered

Root cause: After a oneshot service deactivates, its run-timestamp fields (ActiveEnterTimestamp, ExecMainStartTimestamp, InactiveExitTimestamp) become empty. The `_project_systemd()` function only checked these fields to determine if a service had run, missing the evidence from the timer's LastTriggerUSec.

## Workflow / Commands Executed

1. **Read the PM tracker implementation**
   - Examined `/scripts/ai/aq-pm-tracker` to understand current `_project_systemd()` logic
   - Identified the issue: `ran` boolean only checks empty timestamps

2. **Implement fix**
   - Added `_systemd_timer_state()` helper function to read timer's LastTriggerUSec and Result
   - Modified `_project_systemd()` to check timer state when unit timestamps are empty but Result=success
   - Added fallback: if timer triggered AND Result=success, treat as "ran"

3. **Extend test suite**
   - Added 4 new test cases to `scripts/testing/test-dashboard-program-progress.py`
   - Each test mocks systemctl output to verify the new timer-checking logic

4. **Validate with live tests**
   - Ran all 4 new unit tests: **PASSED**
   - Ran projector on actual tracker: verified service status changed to SHIPPED 100 for services with triggered timers
   - Verified edge cases (e.g., ai-crystallize-sessions correctly stays IN-PROGRESS 40 because its timer never triggered)

## Validation Evidence

### Unit Tests — All Passing

```
scripts/testing/test-dashboard-program-progress.py::ProjectionProvenanceTests::test_oneshot_service_empty_timestamps_timer_triggered_accepted PASSED [ 25%]
scripts/testing/test-dashboard-program-progress.py::ProjectionProvenanceTests::test_oneshot_service_empty_timestamps_timer_triggered_unaccepted PASSED [ 50%]
scripts/testing/test-dashboard-program-progress.py::ProjectionProvenanceTests::test_oneshot_service_empty_timestamps_timer_never_triggered PASSED [ 75%]
scripts/testing/test-dashboard-program-progress.py::ProjectionProvenanceTests::test_oneshot_service_failed_result_returns_blocked PASSED [100%]

============================== 4 passed in 1.11s ===============================
```

### Live Projection Output

**Before fix (simulated):** Services with triggered timers showed IN-PROGRESS 40
**After fix (actual output):**

```
ai-training-ingest                       SHIPPED         100
ai-local-training-loop                   SHIPPED         100
ai-prompt-eval                           SHIPPED         100
ai-sync-knowledge-sources                SHIPPED         100
ai-aidb-reindex (DB reindex)             SHIPPED         100
```

**Correctly staying IN-PROGRESS 40** (timer never triggered):
```
ai-crystallize-sessions (session/DB cleanup) IN-PROGRESS      40
```

### Service State Verification

**ai-training-ingest (now SHIPPED 100):**
```
ActiveState=inactive
Result=success
ActiveEnterTimestamp=
ExecMainStartTimestamp=
InactiveExitTimestamp=
UnitFileState=linked
LastTriggerUSec=Thu 2026-10-08 03:09:02 PDT
```

**ai-crystallize-sessions (correctly IN-PROGRESS 40):**
```
ActiveState=inactive
Result=success
ActiveEnterTimestamp=
ExecMainStartTimestamp=
InactiveExitTimestamp=
UnitFileState=linked
LastTriggerUSec=  (empty — never triggered)
```

## Files Changed

1. **`scripts/ai/aq-pm-tracker`**
   - Added `_systemd_timer_state()` function (18 lines)
   - Modified `_project_systemd()` to check timer state (5 new lines)
   - Total diff: ~23 lines

2. **`scripts/testing/test-dashboard-program-progress.py`**
   - Added `test_oneshot_service_empty_timestamps_timer_triggered_accepted()` (18 lines)
   - Added `test_oneshot_service_empty_timestamps_timer_triggered_unaccepted()` (16 lines)
   - Added `test_oneshot_service_empty_timestamps_timer_never_triggered()` (18 lines)
   - Added `test_oneshot_service_failed_result_returns_blocked()` (16 lines)
   - Total addition: ~68 lines

## Rollback Plan

1. Revert changes to `scripts/ai/aq-pm-tracker` (restore `_systemd_state()` function, remove `_systemd_timer_state()`, restore original `_project_systemd()`)
2. Remove the 4 new test methods from `scripts/testing/test-dashboard-program-progress.py`
3. Re-run projector: services will show as IN-PROGRESS 40 again (old behavior)

**Blast radius:** Minimal. Changes are isolated to PM tracker logic and tests. No dependencies on this fix exist in production yet.

## Residual Risk

1. **systemctl unavailability:** If systemctl fails or is unavailable (e.g., in CI), both unit state and timer state calls return empty dicts; projection falls back to existing DESIGNED tier (no regression).
2. **Malformed systemctl output:** Already handled by try/except in subprocess calls.
3. **Edge case — Result field changed:** If the system's Result field changes semantics, the check `result == "success"` remains correct.

## Hint Feedback

- Timer-driven oneshot services now correctly project as SHIPPED when accepted and their timers have triggered
- Caching strategy (both unit and timer in `_SYSTEMD_CACHE` dict) prevents repeated systemctl calls for same unit
- Tests use monkeypatch pattern to inject fake systemctl output; no real system calls in tests
