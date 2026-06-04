---
name: rag-operations
description: "RAG Operations Skill"
---

# RAG Operations Skill
## Tags
rag, aidb, qdrant, search, seed, collection, embedding, threshold, hybrid_search, 8003, 8002
## When to Use
Searching AIDB for patterns/solutions; seeding new knowledge; understanding collection names;
setting search thresholds; schema for /query vs /hybrid_search.

---

## 1. Access Rules

```
:8002 (AIDB direct) — BLOCKED for agent access. Never curl :8002 directly.
:8003 (coordinator) — ALL RAG queries go through here. Always.
```

```python
# Correct pattern:
COORD = os.environ.get("HYBRID_URL", "http://127.0.0.1:8003")
response = await session.post(f"{COORD}/query", json={"query": text, ...})

# WRONG:
response = await session.post("http://127.0.0.1:8002/collections/...", ...)  # blocked
```

---

## 2. Collection Names

| Collection | Purpose | Query use case |
|------------|---------|----------------|
| `error-solutions` | Bug patterns + fixes | "What causes X error and how to fix it" |
| `best-practices` | Architectural decisions, correct patterns | "What's the pattern for X" |
| `skills-patterns` | Reusable agent/tool patterns | "How to do X in this codebase" |
| `logic-patterns` | Code/architecture concept index (1288+ entries) | Concept-to-code mapping |
| `codebase-context` | File/module context | Finding relevant files for a topic |

All collections use BGE-M3 embeddings.

---

## 3. Search Thresholds

```
Score threshold for retrieval:  0.45  (BGE-M3 default, tuned for this codebase)
Score threshold for validation:  0.50  (structured outputs quality check)
```

Results below 0.45 are typically noise. Don't lower the threshold — improve the query text
or the seed content quality.

---

## 4. Query Payload

```python
# Basic search:
payload = {
    "query": "AppArmor rule for FastAPI service with NoNewPrivileges",
    "n_results": 5,
    "score_threshold": 0.45,     # optional, defaults to 0.45
}

# Collection-targeted:
payload = {
    "query": "async blocking in aiohttp handlers",
    "collection": "error-solutions",
    "n_results": 3,
    "metadata_filter": {"fact_type": "solution"},  # optional
}

# Hybrid dense+sparse:
payload = {
    "query": "coordinator delegation 401 error",
    "use_hybrid": True,    # dense + BM25 sparse combined
    "n_results": 5,
}
```

Response shape:
```json
{
  "results": [
    {
      "id": "...",
      "score": 0.72,
      "payload": {
        "text": "...",
        "source": "error-solutions",
        "metadata": {...}
      }
    }
  ],
  "query_time_ms": 45
}
```

---

## 5. Seeding New Knowledge

```bash
# Via script (preferred for batches):
python3 scripts/data/seed-rag-knowledge.py

# Via aq-commit-facts (extracts from recent work automatically):
scripts/ai/aq-commit-facts

# Via coordinator API (for single facts from agent code):
curl -s http://127.0.0.1:8003/memory/facts \
  -H "Content-Type: application/json" \
  -d '{"content": "pattern text", "source": "agent-fix", "fact_type": "solution"}'
```

**Seed triggers** (Rule from system-dev skill):
- Any error that took >10 min to diagnose → `error-solutions`
- Any architectural decision or constraint discovered → `best-practices`
- Any reusable agent pattern → `skills-patterns`

---

## 6. Idempotent Upserts

The seed script uses content-hash deduplication. Re-running it won't create duplicates.
But if you seed slightly different text for the same concept, you'll get duplicate entries
with slightly different embeddings. Before seeding, search for existing entries:

```python
# Check if similar content already exists:
results = await search_collection("error-solutions", "your new pattern text", n=3)
if any(r["score"] > 0.85 for r in results):
    # Very similar entry exists — update it rather than adding new
```

---

## 7. Collection Management

Do NOT directly interact with Qdrant collections during normal operation. For test teardown:
```python
# Only for test cleanup — never in production code:
await coordinator.delete_test_collection("test_collection_name")
```

Never call `qdrant_client.delete_collection()` directly — it bypasses coordinator tracking
and can corrupt the collection registry.
