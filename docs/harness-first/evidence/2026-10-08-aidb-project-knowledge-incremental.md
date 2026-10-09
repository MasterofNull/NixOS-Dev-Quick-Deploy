# Harness-First Task Evidence

Date: 2026-10-08
Task ID: HF-20261008-aidb-project-knowledge-incremental

## Objective
- The AIDB reindex job 2 never finished: 13743 chunks at about 1s each against a 5400s subjob timeout, restarting from file 1 every night (project_knowledge_exit 124, 6078s, status partial), so under 40% of the corpus was refreshed. Ingest is now incremental: per-chunk content-hash state, unchanged chunks skipped, state saved atomically after successful posts and on SIGTERM, so a timeout-killed run resumes. --full forces everything.

## Workflow/Session IDs
- Session ID: c30f6c3c-e25f-4e8e-8ce5-b4faa7687d3f

## Delegation Decision
- Sonnet implementer (data-integrity judgement on AIDB upsert). The orchestrator verified the real SIGTERM path against a stub AIDB.

## Commands Executed
```bash
python3 scripts/testing/test-ingest-project-knowledge-incremental.py   # PASS
timeout 4 ingest-project-knowledge.py --paths docs (stub AIDB)   # exit 124, posted 72, saved 72; next dry-run skips 72
```

## Validation Evidence
- AIDB upserts on (project, relative_path): 13793 live rows, 0 duplicate keys. Real-repo dry run on the second pass: would post 0 of 13743 chunks.

## Rollback Plan
- Revert the commit.

## Residual Risk
- The first night after deploy still times out (no state yet) and converges over about 3 nights. Upsert never deletes, so about 50 orphan chunks of shrunk or renamed files stay in AIDB (logged).

## Hint Feedback
- None.
