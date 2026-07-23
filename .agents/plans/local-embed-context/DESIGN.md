# Design — Embed model as a first-class local-inference context layer

**Author:** fable-5 (analysis/orchestration). **Inputs synthesized:** orchestrator
analysis + Antigravity (Gemini) architectural review (verified against code) +
never-skip-local root-cause (local abstained on dispatch-integration review because
its ~12k-char context evicted the content under review).

## Problem
Local (Qwen3-35B, on-host APU) has a hard ~12000-char (~3000-token) context budget
(`agent_executor._CTX_CHAR_BUDGET`) — Qwen3 re-prefills fully every call (SWA, no KV
reuse), so context is capped for latency. Large/multi-file tasks blow the budget;
the positional pinned+sliding prune evicts the very content under review; only a
lossy 600-char digest survives (`_store_prune_checkpoint`). Result: local sees
fragments, believes content is "compacted", loops, abstains.

The bge-m3 embed model (`:8081`, 12 iGPU layers) is **underutilized**: it powers
static indexing (aq-index→Qdrant), local RAG tools (query_aidb/hybrid_search), and
switchboard history pruning (`SEMANTIC_TOP_K`/`_get_semantic_similarity`) — but sits
idle ~99% of the time and does nothing for the live local-agent context problem.

## Verified facts (trust-but-verify on Antigravity's review)
- Switchboard DOES semantic-prune chat history via embed + top-K (switchboard.py
  L672 `SEMANTIC_TOP_K`, L782 `_get_semantic_similarity` → `/v1/embeddings`, L1943
  `SEMANTIC_PRUNE_ENABLED`). **Confirmed.**
- **KV-cache constraint (Antigravity, accepted as a hard design rule):** dynamic
  semantic pruning that re-orders/cherry-picks the prompt prefix per query
  invalidates llama.cpp prefix KV-cache reuse → forces full re-eval. So semantic
  selection must NOT mutate the stable prefix; retrieved content goes in a SEPARATE
  appended block. (Moot for Qwen3-SWA which never reuses KV, but binding for the
  switchboard lane and any prefix-cache-capable model.)
- AIDB chunking is token/structural, not semantic-boundary. **Accepted.**

## Architecture: embed model as the local context cache + chunking layer
Four slices, ordered by value/safety. Each USES `:8081` more fully.

### Slice 1 — `aq-local-review`: chunked map-reduce review (layer 1, BUILD FIRST)
New standalone helper. Solves the local-review problem now, no agent_executor risk.
- Split the target artifact into budget-fitting chunks (~5–6k chars; semantic
  boundaries in Slice 4, token/line boundaries for v1).
- MAP: one fast small-context local call per chunk (`delegate-to-local --mode direct`
  or agent) with the focused question → per-chunk finding. Small context = fast
  prefill (avoids the 12-min full-context penalty).
- CACHE: embed each chunk + its finding to a per-task ephemeral Qdrant collection
  (`:8081`) so REDUCE can retrieve rather than hold all in context.
- REDUCE: a final local call synthesizes the per-chunk findings → `local.md`.
- Wire as the local path for large `--target` in aq-collab-round (fall back to the
  bounded-inline stopgap when the artifact already fits `LOCAL_INLINE_CAP`).

### Slice 2 — agent_executor semantic context cache (layer 2A)
Replace the lossy 600-char prune digest with a real cache.
- On prune: embed the FULL evicted chunks (not a 120-char-per-msg digest) to a
  per-task ephemeral collection via `:8081`.
- Before a call: embed the current objective/subtask, retrieve top-K relevant
  evicted chunks, inject them into a DEDICATED, clearly-delimited
  "## Retrieved context (semantic cache)" block placed AFTER the stable pinned
  prefix (stable-prefix + dynamic-suffix — KV-friendly: prefix still matches up to
  the injection point). Never re-order the main history stream.
- Net: local recovers exactly the evicted content it needs, by relevance, without
  breaking prefix caching for models that have it.

### Slice 3 — switchboard KV-stable prune refactor (layer 2B, Antigravity's fix)
Current semantic prune re-orders the prefix → kills KV reuse. Refactor to:
- Lock a static contiguous prefix (system + core instructions + most-recent N
  turns).
- Move semantic selection OUT of the main stream into a "semantic scratchpad"
  block appended after the stable prefix. Preserves llama.cpp prefix-matching →
  fewer full re-evals → faster chat.

### Slice 4 — semantic chunking + contextual retrieval (Antigravity's suggestions)
- Semantic-boundary chunking: split where sentence-embedding cosine distance
  drops below a threshold → coherent self-contained chunks (vs arbitrary token
  cuts). Improves Slice 1 + AIDB index quality.
- Contextual/late chunking: prepend a short file-level summary to each chunk's
  embedded representation so global context survives retrieval.
- (Stretch) proactive pre-fetch: embed local buffer/AST-matched nodes and
  pre-warm relevant context before the agent's first tool query.

## Non-goals / guards
- Do NOT semantically re-order any stable prompt prefix (KV-cache rule).
- Ephemeral per-task collections must be cleaned up (TTL/round-end) — no unbounded
  Qdrant growth.
- Embed calls fail-open: if `:8081` is down, fall back to the current behavior
  (bounded inline / positional prune) — never block a local dispatch on the cache.
- APU budget: embed model already runs; added embed calls are cheap (ms), but batch
  where possible and cap per-task chunk counts.

## Acceptance (per slice)
- Slice 1: a >12k-char artifact gets a real, coverage-complete local verdict
  (not an abstention), within the APU budget, in bounded time; embed-cache used;
  fail-open when `:8081` down.
- Slices 2–4: measured — context-recovery hit rate, KV-reuse preserved (switchboard
  prefill time down), chunk coherence. Independent review each (Antigravity/codex/
  fresh-flagship), never-skip-local self-test.
