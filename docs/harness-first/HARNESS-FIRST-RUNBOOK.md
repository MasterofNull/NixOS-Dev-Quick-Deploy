# Harness-First Operations Runbook

Last updated: 2026-03-04

## Objective
Make the AI stack harness the default execution path for all agent work so planning, delegation, validation, and feedback are captured in one loop.

## Scope Lock
- In scope:
  - Agent task execution through harness ingress.
  - Delegation/subagent routing through switchboard/PRSI policies.
  - Local health and QA gates before task close.
  - Feedback loops into hints and telemetry.
- Out of scope:
  - One-off manual shell workflows without harness metadata.
  - Direct endpoint workflows that bypass policy/audit.

## Non-Negotiable Gates
1. Pre-task context:
```bash
scripts/ai/aq-hints "<task summary>" --format=json --agent=codex
```
2. Run/session ingress (contracted):
```bash
node scripts/ai/harness-rpc.js run-start \
  --workflow-id "<workflow_id>" \
  --query "<task summary>"
```
3. Close-task health evidence:
```bash
scripts/ai/aq-qa 0 --json
scripts/ai/aq-qa 1 --json
```
4. Deep baseline check before deploy/release gates:
```bash
scripts/health/system-health-check.sh --detailed
```

## Delegation Policy (Subagents + Local Tooling)
1. **Harness-first: always start with the local harness** at `http://127.0.0.1:8003` (plan → run/start → hints → execute → review).
2. Use switchboard/PRSI policy for escalation to remote models when local harness lacks capability.
3. Require approval path for high-risk actions.
4. Feed outcomes back into hints ranking.

## Standard Task Lifecycle
1. Intake and scope lock.
2. Pull hints and route intent.
3. Execute via harness workflow run/session.
4. Run QA/health checks.
5. Submit hint feedback.
6. Record evidence artifact.

## Evidence Artifact Contract
Store per-task evidence in:
- `docs/harness-first/evidence/YYYY-MM-DD-<task-id>.md`

Each artifact must include:
- `Task ID`
- `Objective`
- `Workflow/Session IDs`
- `Delegation Decision`
- `Commands Executed`
- `Validation Evidence`
- `Rollback Plan`
- `Residual Risk`

Use template:
- `docs/harness-first/HARNESS-FIRST-EVIDENCE-TEMPLATE.md`

## Rollback
If any mandatory gate fails:
1. Stop rollout and mark task `gated`.
2. Revert to last known-good deployment generation.
3. Re-run `scripts/ai/aq-qa 0 --json` and `scripts/ai/aq-qa 1 --json`.
4. Document failure and remediation in evidence artifact.

## CI Enforcement
Static CI gates must pass:
- `scripts/testing/check-harness-first-runbook.sh`
- `scripts/testing/check-harness-first-evidence-template.sh`
- `scripts/testing/check-harness-first-pr-evidence-gate.sh` (PR-only)
- `scripts/testing/check-harness-first-static-gates.sh`
- `scripts/testing/check-harness-first-platform-owner-approval.py` (PR-only for policy-file edits)

PR policy for high-impact changes:
- Path policy file: `config/harness-first-high-impact-paths.txt`
- Platform owners file: `config/harness-first-platform-owners.txt`
- If any listed path changes in a PR, a new file must be added:
  - `docs/harness-first/evidence/YYYY-MM-DD-<task-id>.md`
- If the path policy file changes in a PR, at least one configured platform owner must approve.

## Local Release Gate
Include harness-first gate in:
```bash
scripts/automation/run-advanced-parity-suite.sh
```
