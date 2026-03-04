# Harness-First Task Evidence

Date: YYYY-MM-DD
Task ID: HF-YYYYMMDD-001

## Objective
- What was requested and what was delivered.

## Workflow/Session IDs
- Workflow ID:
- Session ID:

## Delegation Decision
- Local-only or delegated.
- If delegated: policy reason and target backend/subagent.

## Commands Executed
```bash
scripts/aq-hints "<task summary>" --format=json --agent=codex
node scripts/harness-rpc.js run-start --workflow-id "<workflow_id>" --query "<task summary>"
scripts/aq-qa 0 --json
scripts/aq-qa 1 --json
```

## Validation Evidence
- Key outputs and pass/fail status.
- Links to artifacts/logs.

## Rollback Plan
- Exact rollback command(s) and trigger conditions.

## Residual Risk
- Remaining risk after implementation.

## Hint Feedback
- Hint IDs used.
- Helpful/unhelpful feedback summary.
