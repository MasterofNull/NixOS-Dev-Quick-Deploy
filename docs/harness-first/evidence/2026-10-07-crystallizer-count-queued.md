# Harness-First Task Evidence

Date: 2026-10-07
Task ID: HF-20261007-012

## Objective
- Crystallizer reported `distilled 0 facts` / insights_stored 0 although facts were written: store_agent_memory returns status "queued" (async ingestion) and the crystallizer only counted "stored"/"success". Count "queued" (same set http_server_impl uses at ~1824).

## Workflow/Session IDs
- Workflow ID: wf-crystallizer-count-queued-20261007
- Session ID: c30f6c3c-e25f-4e8e-8ce5-b4faa7687d3f; live request 116d76b4b6a64d8a8f63fb3f8ba5aef6

## Delegation Decision
- Claude Opus 5.5 direct (Rule 17 exception: one-line fix found during live activation verification).

## Commands Executed
```bash
aq-crystallize --session-dir ~/.codex/sessions --since-hours 24 --max-sessions 1   # live
python3 <qdrant scroll agent-memory-semantic>                                      # facts present
pytest -q tests/test_memory_crystallizer_sessions.py tests/test_memory_crystallizer.py
```

## Validation Evidence
- LIVE END-TO-END WORKING after #386/#387/#388 + rebuild: Codex session → client extraction/redaction → local Qwen distillation within timeout → facts in Qdrant agent-memory-semantic (e.g. "The repair lane configuration order is set to local, claude, antigravity, and codex."). Status showed sessions_processed=1 but insights_stored=0 — counting bug only.
- New regression test fails on old code (1 failed) and passes on fix; 31/31 crystallizer tests pass.

## Rollback Plan
- Revert (counter only).

## Residual Risk
- Requires rebuild + coordinator restart to deploy; fact accuracy depends on local model (no verification step).

## Hint Feedback
- No aq-hints consulted.
