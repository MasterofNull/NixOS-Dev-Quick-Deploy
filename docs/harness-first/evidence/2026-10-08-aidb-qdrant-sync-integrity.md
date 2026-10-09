# Harness-First Task Evidence

Date: 2026-10-08
Task ID: HF-20261008-230

## Objective
- Fix RAG vector-store integrity issues found by the read-only audit:
  - AIDB `_vectorize_doc_to_qdrant` used a 32-bit md5 point id, so colliding paths and same paths across projects overwrote each other. Qdrant `knowledge` holds 16856 points, against 28243 PG rows and 27754 distinct paths.
  - Only 1200 chars were embedded. A live sample of 2000 rows has p50 of 2067 chars, so about 70% of chunks were truncated.
  - The vectorize queue overflowed: 909 `queue_full` drops in 24h, never retried.
  - There was no PG/Qdrant reconciliation.
- Fix:
  - uuid5(project|path) point ids.
  - A durable JSONL spool plus a 30s drain, so nothing is dropped.
  - A 2400-char embed cap, with shrink-and-retry for the embed server's 1024-token slots.
  - `aq-vector-reconcile` (dry-run by default; `--apply` enqueues; `--prune-legacy` is double-guarded).
  - /vector/sync/status.
  - Concurrency raised 2→4 (matching the embed server's slots) and the queue 16→64.

## Workflow/Session IDs
- Session ID: c30f6c3c-e25f-4e8e-8ce5-b4faa7687d3f

## Delegation Decision
- Sonnet implementer (data integrity). The orchestrator added the Nix env tuning and verified the tests.

## Commands Executed
```bash
python3 scripts/testing/test-aidb-vector-sync.py   # PASS: 10 (uuid5 stable across processes, no collision in 50k, spool not drop, drain retry, reconcile math, prune guard)
curl :8081/embedding timing: 0.59s @1200 chars, 1.03s @2100; >=3000 chars -> HTTP 400 (1024-token slot)
```

## Validation Evidence
- Tests pass. The live Qdrant read shows all 16856 `knowledge` points carry legacy integer ids, so after deploy they are legacy orphans until `aq-vector-reconcile --prune-legacy --apply-prune` (refused while any doc is still missing).

## Rollback Plan
- Revert the commit. The legacy points remain intact until the explicit prune.

## Residual Risk
- A one-time re-vectorization of about 28k docs follows: about 2h at concurrency 4. Search returns legacy plus new duplicates until the prune. Rows over 2400 chars (~1%) embed only their head. PG counts could not be measured from the sandbox (the secret is unreadable), so run the reconcile as the service user.

## Hint Feedback
- None.
