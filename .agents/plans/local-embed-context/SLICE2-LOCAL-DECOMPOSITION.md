# Slice 2 decomposition — built BY local, for local

**Principle:** [[feedback-local-builds-its-own-tools]] — local should build the
tools that help local. Slice 2 (agent_executor semantic context cache) is
decomposed into bounded single-function units that fit local's measured envelope
(✅ bounded single-edit, even in a large file). Each unit = one function + its
test, dispatched to `delegate-to-local`. The orchestrator composes + validates;
only the final multi-site integration (F5) may need a cheap-remote or a careful
local single-edit. Target: local builds F1–F4 itself.

## Goal (Slice 2)
Replace the lossy 600-char prune digest (`_store_prune_checkpoint`) with a real
embed-backed cache: on prune, embed the FULL evicted chunks to a per-task
collection; before a call, retrieve the most relevant evicted chunks into a
dedicated scratchpad block placed AFTER the stable pinned prefix (never re-order
the prefix — Antigravity's verified KV-cache rule).

## Local-buildable units (each: one function + one test, single-edit)
- **F1 `_embed_text(text) -> list[float] | None`** — POST bge-m3 at
  `${AI_STACK_EMBED_ENDPOINT:-http://127.0.0.1:8081}/v1/embeddings`; return the
  vector or None on ANY error (fail-open). Pattern: ai_coordination.py
  `_query_qdrant_direct`. Test: monkeypatch the client → returns None on dead
  endpoint, vector on a stubbed 200.
- **F2 `_cache_evicted(task_id, chunks: list[str]) -> str | None`** — ensure a
  per-task Qdrant collection `agent-ctx-<task_id>` exists (create with the vector
  size from the first embedding), embed + upsert each chunk; return the collection
  name or None (fail-open). Test: stubbed embed/qdrant → upserts N points; dead
  endpoint → None, no raise.
- **F3 `_retrieve_ctx(collection, query, k=6) -> list[str]`** — embed the query,
  search the collection, return the top-k chunk texts (payload.text); [] on any
  error. Test: stubbed search → returns ordered texts; error → [].
- **F4 `_scratchpad_message(retrieved: list[str]) -> dict | None`** — format a
  single `{"role":"system","content": "## Retrieved context (semantic cache)\n..."}`
  message from the retrieved chunks, or None if empty. Pure function. Test:
  empty → None; non-empty → one system message containing each snippet.

## Orchestrator/integration unit (F5 — not local-first)
- **F5 integration** — in the prune path: after computing `pinned + sliding`,
  call F2 on the evicted middle (`messages[4:-4]`), then F3 with the current
  objective, and INSERT F4's scratchpad message immediately AFTER the pinned
  prefix (index 4), before sliding. Guard: only when embed is reachable; else the
  existing 600-char checkpoint path unchanged (fail-open). This is the multi-site
  edit — orchestrator composes, or local does it as a single localized edit once
  F1–F4 exist and are tested.

## Guards (all units)
- Fail-open: any embed/Qdrant error → behave as today (no cache); never block or
  slow the agent loop's critical path (embed off the hot path / short timeouts).
- KV-cache: the scratchpad goes AFTER the stable prefix as its own block; the
  pinned prefix bytes never change → prefix-cache (for models that have it)
  preserved.
- Cleanup: per-task collections deleted at task end (add to the existing task
  teardown), TTL fallback.

## Acceptance
- F1–F4 unit tests pass; F5 integration: a pruned agent run recovers relevant
  evicted content via the scratchpad (measured hit), prefix bytes unchanged before
  the injection point, fail-open when :8081 down. Independent review + never-skip-local.
