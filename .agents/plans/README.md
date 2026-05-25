# Plans Index

Status: Active
Owner: AI Stack Maintainers
Last Updated: 2026-05-25

## Start Here

Use this directory for active implementation plans and short-lived phase records. Do not treat every file in this directory as current authority.

For agent behavior, instruction, routing, and feature parity work, start with:

- `docs/architecture/agent-behavior-parity-index.md`
- `docs/architecture/role-matrix.md`
- `docs/architecture/routing-profile-inventory.md`
- `.agents/plans/multi-agent-edge-harness/PARITY-INTEGRATION-PLAN.md`

For document lifecycle and retirement rules, use:

- `docs/operations/document-lifecycle-hygiene.md`

## Required Plan Header

Every new active plan should include:

```text
# Title

Status: Active
Owner: <agent/team>
Last Updated: YYYY-MM-DD
Supersedes: none
Superseded-By: none
```

## Plan Contents

Each plan should include:

1. Objective
2. Scope lock
3. Active authority links
4. Steps
5. Validation commands
6. Rollback notes
7. Retirement condition

## Rules

- Keep one logical slice per plan file.
- Link to source docs instead of duplicating long policy text.
- Include explicit validation evidence and rollback notes in each plan.
- When a slice ships, mark the plan `Reference` or `Superseded`, or move it to an archive path after summarizing it in the nearest active index.
- Historical plans are evidence, not default instructions.
