# Harness-First Task Evidence

Date: 2026-10-08
Task ID: HF-20261008-aidb-indexer-backoff

## Objective
- aq-index-logic-patterns posted ~1200/min against AIDB's 500/min ingest limit and treated 429 as a hard failure. Each reindex dropped ~1k RAG docs (2172 ingest_rate_limited/24h) with exit 0, and spilled 429s onto other callers sharing the API-key bucket (813). Also: dashboard AppArmor read rule for ~/.cache/ai-harness (consensus/plan panels were EACCES), and query-gaps tmpfiles owner corrected to the coordinator user plus removal of a stale .tmp.

## Workflow/Session IDs
- Session ID: c30f6c3c-e25f-4e8e-8ce5-b4faa7687d3f

## Delegation Decision
- Haiku implementer; the orchestrator replaced its source-grep test with a behavioural one during review.

## Commands Executed
```bash
python3 scripts/testing/test-aq-index-logic-patterns-backoff.py; nix eval ...command-center-dashboard-api.profile | rg ai-harness
```

## Validation Evidence
- Behavioural test: 429,429,201 gives success after 3 attempts with 2s/4s backoff; persistent 429 fails; partial ingest exits 1. The test FAILS against the original script. The profile renders both ai-harness rules.

## Rollback Plan
- Revert the commit and rebuild.

## Residual Risk
- Hardcoded /home/hyperd matches the existing profile lines. A reindex now takes ~4x longer at 0.2s pacing (AQ_INDEX_PACE_S overrides).

## Hint Feedback
- None.
