# Task: Review seed-rag-knowledge.py content quality
Role: architect/reviewer
Priority: high
Assigned-to: gemini

## Objective

Review the seed data in `scripts/data/seed-rag-knowledge.py` for:
1. Correctness of error+solution pairs against the codebase
2. Coverage gaps — what important bug patterns or best practices are missing?
3. Quality of embed-text construction in `_text_for_embed()` — is the text well-formed for BGE-M3 semantic search?
4. Whether the `_clear_wrong_type_points()` logic correctly identifies memory-type pollution in `error-solutions`

## Context

Collections to seed:
- `error-solutions` (currently 36 wrong-type points — system memory blobs, not error+solution pairs)
- `skills-patterns` (currently 2 points — effectively empty)
- `best-practices` (currently 2 points — only NixOS module system docs)

AIDB/Qdrant endpoint: `PUT http://127.0.0.1:6333/collections/{name}/points`
Embedding server: `POST http://127.0.0.1:8081/v1/embeddings` (BGE-M3, 1024-dim, CLS pooling)

BGE-M3 score ranges on this corpus:
- knowledge: 0.62-0.67 (rich, well-indexed)
- codebase-context: 0.48-0.58 (good)
- error-solutions: 0.34-0.44 (sparse/type mismatch)
- skills-patterns: 0.35-0.41 (sparse)
- best-practices: 0.34-0.63 (sparse)

Target: after seeding, typical query should surface at least 1 result from each collection at score ≥ 0.45.

## Deliverable

1. A concise review verdict: APPROVE / APPROVE-WITH-AMENDMENTS / REJECT
2. If amendments: list specific additions or changes as code patches
3. Any missing error-solutions entries from the session history (check `.agent/collaboration/HANDOFF.md` and `MEMORY.md` for promoted bug patterns not yet covered)
4. Confirm `_text_for_embed()` embed text patterns are semantically rich enough for BGE-M3

## Reference files

- `scripts/data/seed-rag-knowledge.py` — the script to review
- `.agent/collaboration/HANDOFF.md` — recent session history
- `/home/hyperd/.claude/projects/-home-hyperd-Documents-NixOS-Dev-Quick-Deploy/memory/MEMORY.md` — promoted bug patterns
- `ai-stack/mcp-servers/hybrid-coordinator/knowledge/collections_config.py` — collection schemas
