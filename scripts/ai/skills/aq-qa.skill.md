# SKILL: aq-qa

**Purpose**: Phase-gated health checker for the AI stack. Runs structured checks
for services, APIs, data integrity, and harness contracts. Use after every deploy.

## Synopsis

```
aq-qa [PHASE] [--format=text|json] [--skip=CHECK_NAME]
```

## Phases

| Phase | Checks | Description |
|-------|--------|-------------|
| `0` | 39 | Full stack health (services, APIs, routing, cache, memory) |
| `1` | ~15 | Harness contract checks (hints, delegation, intent-contract) |
| `2` | ~10 | RAG and knowledge base checks |

## Phase 0 Check Categories

| Category | What it validates |
|----------|------------------|
| Services | All AI stack systemd units active |
| Endpoints | HTTP 200 for /health on each service |
| Routing | `route_search` returns results with score |
| Cache | Semantic cache hit rate > threshold |
| Memory | AIDB document count, vector search responds |
| Auth | API key enforcement on protected endpoints |

## Output

```
39 passed · 0 failed · 1 skipped
```

With `--format=json`: structured results per check with `status`, `message`, `duration_ms`.

## Examples

```bash
# Full health check after nixos-rebuild
aq-qa 0

# JSON output for programmatic consumption
aq-qa 0 --format=json | jq '.results[] | select(.status=="failed")'

# Skip slow delegation sample check
aq-qa 0 --skip=delegation_sample
```

## Notes

- Target: 39+ passed, 0 failed after every deploy.
- 1 skipped (delegation sample) is normal when no recent delegation traffic.
- Run `aq-report` for deeper 7d trend analysis beyond pass/fail.
