---
doc_type: plan
id: workflow-deviation-recovery-c0
title: Workflow Deviation Recovery C0 Contract Slice
status: active
owner: codex-orchestrator
date: 2026-08-08
parent_prd: workflow-deviation-recovery
---

# C0 design packet

## Boundary

C0 is pure and offline. It adds one Draft 2020-12 closed schema, one
dependency-free resolver, golden vectors, and focused tests. It does not write
events or issues, call PRSI, launch agents, modify services, enable automation,
stage, deploy, or change traffic.

## Invariants

- Record and nested objects reject unknown fields.
- `deviation_id` is a domain-separated digest of the exact normalized record
  excluding only `deviation_id`.
- `root_issue_key` remains the deduplication group across evidence revisions.
- Unknown reason codes resolve to at least medium risk, non-retryable, and
  owner-required.
- `automatic_eligible` is derived, never trusted from input.
- Authority, release, security, deployment, secret, destructive, external, and
  live-traffic classes are never automatic.
- Evidence contains typed references plus SHA-256 digests, never raw content.

## Exact C0 inventory

1. `.agent/PROJECT-WORKFLOW-DEVIATION-RECOVERY-PRD.md`
2. `.agents/plans/workflow-deviation-recovery/C0-DESIGN-PACKET-20260808.md`
3. `config/schemas/workflow-deviation.schema.json`
4. `scripts/ai/lib/workflow_deviation.py`
5. `scripts/testing/fixtures/workflow-deviation-golden.json`
6. `scripts/testing/test-workflow-deviation-contract.py`

## Validation

```bash
python3 -m py_compile scripts/ai/lib/workflow_deviation.py
python3 -m json.tool config/schemas/workflow-deviation.schema.json
python3 scripts/testing/test-workflow-deviation-contract.py
python3 scripts/governance/check-doc-frontmatter.py --all
```

C1 requires separate review after C0 evidence. C0 grants no live authority.

