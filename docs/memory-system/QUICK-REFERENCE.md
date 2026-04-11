# Memory System Quick Reference

**Version:** 1.0.0
**Last Updated:** 2026-04-11

Quick reference card for the AI harness memory system.

---

## Command Cheat Sheet

### aq-memory CLI

```bash
# Add a fact
aq-memory add "CONTENT" --project PROJECT --topic TOPIC --type TYPE

# Search facts
aq-memory search "QUERY" [--project P] [--topic T] [--type T]

# List facts
aq-memory list [--project P] [--valid-now] [--stale]

# Expire a fact
aq-memory expire FACT_ID --until DATE --reason "REASON"

# Agent diary
aq-memory agent-diary AGENT [--topic T] [--limit N]

# Statistics
aq-memory stats [--project P]
```

### aq-benchmark CLI

```bash
# Run full benchmark
aq-benchmark run --corpus CORPUS.json --output results.json

# Recall accuracy tests
aq-benchmark recall --all [--limit N]

# Performance tests
aq-benchmark perf --all [--queries N]

# Generate report
aq-benchmark report results.json --format [text|html|json]
```

---

## Common Commands

### Store Facts

```bash
# Decision
aq-memory add "Using JWT with 7-day expiry" \
  --project ai-stack --topic auth --type decision \
  --tags "jwt,security" --confidence 0.95

# Preference
aq-memory add "Prefer tabs over spaces" \
  --project coding --topic style --type preference

# Discovery
aq-memory add "Found bug in metadata filtering" \
  --project ai-stack --topic bugs --type discovery

# Temporary fact
aq-memory add "API at localhost:8889" \
  --project dashboard --topic deployment --type event \
  --valid-until "2026-05-01T00:00:00Z"
```

### Search & Query

```bash
# Basic search
aq-memory search "authentication"

# Filtered search (34% better recall)
aq-memory search "auth" \
  --project ai-stack --topic auth --type decision --valid-now

# List current facts
aq-memory list --project ai-stack --valid-now --limit 20

# Find stale facts
aq-memory list --stale --project ai-stack
```

### Agent Diaries

```bash
# View agent diary
aq-memory agent-diary qwen --topic coding --limit 10

# Get all diary topics
aq-memory agent-diary qwen --limit 100 | grep "\[" | sort -u

# Statistics
aq-memory stats --project agent-qwen
```

---

## Python API Quick Start

### Basic Usage

```python
from aidb.temporal_facts import TemporalFact
from datetime import datetime, timezone

# Create a fact
fact = TemporalFact(
    content="Using JWT with 7-day expiry",
    project="ai-stack",
    topic="auth",
    type="decision",
    tags=["jwt", "security"]
)

# Check validity
now = datetime.now(timezone.utc)
is_valid = fact.is_valid_at(now)
is_stale = fact.is_stale()
```

### Metadata Filtering

```python
from aidb.temporal_query import (
    filter_facts_by_project,
    filter_facts_by_topic,
    filter_facts_by_type
)

# Filter chain
facts = filter_facts_by_project(all_facts, "ai-stack")
facts = filter_facts_by_topic(facts, "auth")
facts = filter_facts_by_type(facts, "decision")
```

### Progressive Loading

```python
from aidb.layered_loading import LayeredMemory

memory = LayeredMemory(fact_store=store)

# Load with budget
context = memory.progressive_load(
    query="implement authentication",
    max_tokens=500
)
```

### Agent Diaries

```python
from aidb.agent_diary import AgentDiary

# Write to diary
diary = AgentDiary("qwen")
diary.write(
    "Implemented JWT validation",
    topic="auth",
    tags=["jwt"]
)

# Read diary
entries = diary.read(topic="auth", since_days=7)

# Observer mode
qwen_work = AgentDiary.read_as_observer("qwen", limit=10)
```

---

## Memory Layers (L0-L3)

| Layer | Always Loaded | Tokens | Contains |
|-------|--------------|--------|----------|
| **L0** | ✅ Yes | 50 | Agent identity, role, context |
| **L1** | ✅ Yes | 170 | Critical facts, recent decisions |
| **L2** | 📋 On-demand | Variable | Topic-specific memories |
| **L3** | 🔍 Explicit | Heavy | Full semantic search |

**Token Savings:**
- L0 + L1 only: 78% reduction (220 tokens)
- L0 + L1 + L2: 48% reduction (520 tokens)
- Progressive avg: 40-70% reduction

---

## Fact Types

| Type | Use Case | Example |
|------|----------|---------|
| **decision** | Technical/architectural choices | "Using JWT for auth" |
| **preference** | User/team preferences | "Prefer verbose logging" |
| **discovery** | Bugs found, insights | "Found metadata bug" |
| **event** | Time-bound happenings | "Deployed v2.0" |
| **advice** | Best practices, lessons | "Always validate inputs" |
| **fact** | General information | "API runs on port 8889" |

---

## Metadata Taxonomy

```
Project (ai-stack, dashboard, nix-config)
  └── Topic (auth, deployment, database)
      └── Type (decision, preference, fact, ...)
          └── Tags [jwt, security, ...]
```

**Filtering Impact:**
- No filters: 60-70% recall
- Project only: 75-80% recall
- Project + Topic: 85-90% recall
- Project + Topic + Type: 90-95% recall (+34%)

---

## Common Patterns

### Find Recent Decisions

```bash
aq-memory list --type decision --valid-now --limit 10
```

### Check Authentication Facts

```bash
aq-memory search "auth" --project ai-stack --topic auth
```

### Expire Outdated Config

```bash
aq-memory expire abc123 --until "2026-12-31T23:59:59Z" \
  --reason "superseded"
```

### Review Agent Work

```bash
aq-memory agent-diary qwen --topic coding --limit 20
```

### Memory Health Check

```bash
aq-memory stats --project ai-stack
aq-memory list --stale
```

---

## Troubleshooting Quick Fixes

### No Results Found

```bash
# Remove filters progressively
aq-memory search "query" --limit 50
aq-memory list --limit 100
```

### High Token Usage

```python
# Reduce budget
context = memory.progressive_load(query, max_tokens=300)

# Use specific filters
facts = filter_facts_by_topic(facts, "specific-topic")
```

### Slow Queries

```bash
# Add metadata filters (faster)
aq-memory search "query" --project P --topic T --type TYPE

# Reduce limit
--limit 10
```

### Stale Facts Accumulating

```bash
# Find stale facts
aq-memory list --stale --project ai-stack

# Expire them
for id in $(aq-memory list --stale --json | jq -r '.[].fact_id'); do
  aq-memory expire "$id" --until $(date +%Y-%m-%d) --reason "cleanup"
done
```

---

## Performance Targets

| Metric | Target | Command |
|--------|--------|---------|
| L0 load | < 10ms | `memory.load_l0()` |
| L1 load | < 100ms | `memory.load_l1()` |
| L2 load | < 300ms | `memory.load_l2("topic")` |
| L3 search | < 500ms | `memory.load_l3("query")` |
| Baseline recall | 85%+ | `aq-benchmark recall` |
| Metadata recall | 90%+ | with filters |
| Throughput | 50+ qps | `aq-benchmark perf --throughput` |

---

## File Locations

```
~/.aidb/
  ├── identity.txt              # L0 identity (50 tokens)
  ├── critical_facts.json       # L1 critical facts (170 tokens)
  ├── temporal_facts.json       # Fact store (in-memory mode)
  └── diaries/
      ├── qwen_diary.json       # Qwen's private diary
      ├── codex_diary.json      # Codex's private diary
      └── claude_diary.json     # Claude's private diary
```

---

## Environment Variables

```bash
# Custom storage location
export AIDB_STORAGE=".aidb/temporal_facts.json"

# Custom diary directory
export AIDB_DIARY_DIR="~/.aidb/diaries"

# Custom identity file
export AIDB_IDENTITY="~/.aidb/identity.txt"

# Verbose logging
export AIDB_VERBOSE=1
```

---

## Confidence Levels

| Level | Meaning | Use When |
|-------|---------|----------|
| 1.0 | Verified, authoritative | Documentation, specs |
| 0.9 | High confidence, tested | Tested code, confirmed facts |
| 0.8 | Moderate, observed | Observed behavior |
| 0.7 | Low confidence, inferred | Assumptions, guesses |
| < 0.7 | Speculative | Needs verification |

---

## Best Practices Checklist

- [ ] Use specific topics (not "general" or "misc")
- [ ] Tag facts with relevant keywords
- [ ] Set appropriate confidence levels
- [ ] Set `valid_until` for temporary facts
- [ ] Use metadata filters for better recall
- [ ] Check for stale facts monthly
- [ ] Use progressive loading to save tokens
- [ ] Never store sensitive data (passwords, API keys)
- [ ] Write clear, searchable content
- [ ] Review agent diaries for insights

---

## One-Liners

```bash
# Count facts by project
aq-memory list --json | jq -r '.[].project' | sort | uniq -c

# Find all security-related facts
aq-memory search "security" --tags "security"

# Export facts to JSON
aq-memory list --limit 1000 --json > backup.json

# Check memory usage
du -sh ~/.aidb/

# List all agent diaries
ls -1 ~/.aidb/diaries/*_diary.json | xargs -n1 basename | sed 's/_diary.json//'
```

---

## Links

- **User Guide**: [USER-GUIDE.md](./USER-GUIDE.md)
- **API Reference**: [API-REFERENCE.md](./API-REFERENCE.md)
- **Integration Examples**: [INTEGRATION-EXAMPLES.md](./INTEGRATION-EXAMPLES.md)
- **Architecture**: [../architecture/memory-system-design.md](../architecture/memory-system-design.md)

---

**Print this page for quick reference during development!**
