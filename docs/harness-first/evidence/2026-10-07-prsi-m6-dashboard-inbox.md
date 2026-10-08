# Harness-First Task Evidence

Date: 2026-10-07
Task ID: HF-20261007-016

## Objective
- PRSI->RSI M6: show the RSI/approval inbox read-only on the dashboard from the same backend as aq-approve (scripts/ai/lib/approval_inbox.py); no separate approve path until ACP crypto.

## Workflow/Session IDs
- Session ID: c30f6c3c-e25f-4e8e-8ce5-b4faa7687d3f; delegate codex-20261007-223641-dr1o5e

## Delegation Decision
- Implementer: Codex (bridge). Reviewer: Claude Opus 5.5 (re-ran tests).

## Commands Executed
```bash
python3 scripts/testing/test-dashboard-approval-inbox.py
python3 -m py_compile dashboard/backend/api/routes/approval_inbox.py dashboard/backend/api/main.py
node --check assets/dashboard.js
python3 scripts/governance/check-cross-surface-contract.py <staged>
```

## Validation Evidence
- 5/5 tests (canonical projection, empty inbox, failure -> 200 unavailable, no mutating methods, registration + polling).
- Live validation pending: dashboard backend restart required to load the new route (owner act).

## Rollback Plan
- Revert; restart dashboard backend.

## Residual Risk
- Read-only by design; approvals still via chat / aq-approve.

## Hint Feedback
- No aq-hints consulted.
