# Slice 2a — context_cache.py (embed-backed semantic context cache library)

**Shipped:** `ai-stack/local-agents/context_cache.py` + `scripts/testing/test-context-cache.py`.
Standalone library only — NOT yet wired into any runtime (integration is Slice 2b,
which is freeze-aware because `agent_executor.py` is hash-pinned).

## API (all fail-open — never raise; empty/None on any error)
- `embed_text(text, timeout=8.0) -> list[float] | None` — bge-m3 at
  `AI_STACK_EMBED_ENDPOINT` (:8081).
- `cache_evicted(task_id, chunks, timeout=8.0) -> collection_name | None` — create
  `agent-ctx-<task_id>` (Cosine, size from first embedding), embed+upsert chunks.
- `retrieve_ctx(collection, query, k=6, timeout=8.0) -> list[str]` — query-embed,
  Qdrant search, return payload.text in score order.
- `scratchpad_message(retrieved) -> dict | None` — pure formatter; the returned
  system message MUST be inserted AFTER the stable pinned prefix (KV-cache rule),
  never mutating the prefix. No insertion logic here (that is 2b).
- `delete_collection(collection, timeout=8.0)` — best-effort teardown.

## Why it exists
Replaces the lossy 600-char prune digest (`_store_prune_checkpoint`) with a real
retrievable cache, so the local agent can recover its evicted context by relevance.
Uses the otherwise-idle bge-m3 embed model. See DESIGN.md + SLICE2-LOCAL-DECOMPOSITION.md.

## Not yet integrated (Slice 2b)
The one hook that calls this from `agent_executor.py`'s prune path is deferred:
that file is hash-pinned in `local-delegation-reliability-golden.json`, so 2b must
reconcile the freeze (reviewed re-pin) rather than silently drift it.

## Validation
14/14 unit tests (fail-open on dead endpoints, stubbed 200s, upsert count, ordered
retrieval, empty/non-empty scratchpad) via a monkeypatched http client — no live
embed/Qdrant server needed.
