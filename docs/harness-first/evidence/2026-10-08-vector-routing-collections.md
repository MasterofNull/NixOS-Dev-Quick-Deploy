# Harness-First Task Evidence

Date: 2026-10-08
Task ID: HF-20261008-240

## Objective
- The AIDB `knowledge` collection (16.8k points) got 273 of 23k searches, and `wiki-sections` was rarely routed. Route `knowledge` into general, code, error and architecture query sets (within the existing cap), and route `wiki-sections` for architecture queries. Add per-collection hit counts to route_search telemetry.
- Missing collections:
  - `mcp-semantic-search` is created as an infra collection.
  - `solved_issues` is Postgres-only; the GC now tolerates its absence (it used to log errors every cycle).
  - The dead default `nixos_docs` becomes `best-practices`.
- Also: a stable continuous_learning point id (Python hash() was per-process), and context_cache test-collection leaks fixed, plus a guarded prune script.

## Workflow/Session IDs
- Session ID: c30f6c3c-e25f-4e8e-8ce5-b4faa7687d3f

## Delegation Decision
- Sonnet implementer. The orchestrator verified that the existing route-handler test failures pre-date this change (they fail identically on unmodified main).

## Commands Executed
```bash
pytest tests/unit/test_vector_routing_collections.py   # 7 passed
test-continuous-learning-qdrant-upsert (2/2), -embeddings, -proposals pass; test-read-file-gate (stub) 13 OK
pytest tests/unit/test_route_handler_collection_policy.py on origin/main: 3 failed (pre-existing, logged)
```

## Validation Evidence
- Before/after routing: the code query now gets [codebase-context, knowledge]; the architecture query [codebase-context, wiki-sections, knowledge]; the error query [codebase-context, error-solutions, knowledge].

## Rollback Plan
- Revert the commit.

## Residual Risk
- The pre-existing route tests are broken (shim/_COLLECTIONS patching and a routing_config import). tool_discovery still uses hash()%10**8 for ids (logged). The 2 leaked test collections are removed only when the prune script runs with --apply.

## Hint Feedback
- None.
