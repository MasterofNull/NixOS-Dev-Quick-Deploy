# SKILL: aq-report

**Purpose**: AI stack performance digest. Generates a structured report covering
routing, cache, hints, delegation, RAG quality, tool security, and PRSI metrics
for a configurable time window.

## Synopsis

```
aq-report [--since=Nd] [--format=text|json|markdown] [--aidb-import] [--metric=NAME]
```

## Key Flags

| Flag | Default | Description |
|------|---------|-------------|
| `--since` | `7d` | Time window: `24h`, `7d`, `30d` |
| `--format` | `text` | `json` for machine parsing, `markdown` for docs |
| `--aidb-import` | off | Import report into AIDB for historical search |
| `--metric` | — | Single metric: `delegation_success`, `cache_hit_rate`, etc. |

## Report Sections (JSON contract)

| Section | Key | Description |
|---------|-----|-------------|
| 1 | `tool_performance` | Per-tool call counts and success rates |
| 2 | `routing` | Local/remote split, backend selections |
| 3 | `semantic_cache` | Hit rate, total lookups |
| 9 | `hint_adoption` | Injection rate, adoption % |
| 10 | `intent_contract` | Coverage %, coercion rate |
| 11 | `tool_security_auditor` | Cache hit rate, blocked tools |
| 13 | `hint_diversity` | Entropy, dominant hint share |

## Examples

```bash
# 7-day digest (terminal)
aq-report --since=7d --format=text

# Machine-readable for scripts
aq-report --format=json | jq '.semantic_cache.hit_rate_pct'

# Check delegation success after a fix
aq-report --metric=delegation_success --since=24h

# Import report into AIDB (weekly recommended)
aq-report --aidb-import
```

## Recommendations

The `recommendations[]` array in JSON output contains actionable auto-generated
items (e.g. "run aq-knowledge-import to close top gap"). Consumed by `aq-optimizer`.
