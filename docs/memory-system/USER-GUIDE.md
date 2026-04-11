# Memory System User Guide

**Version:** 1.0.0
**Last Updated:** 2026-04-11
**Phase:** 1 Complete

---

## Overview

The AI harness memory system (AIDB) provides intelligent, persistent memory for AI agents with temporal validity, multi-layer loading, and agent-specific diaries. This guide covers everything you need to know to effectively use the memory system.

### Key Features

- **Temporal Facts**: Memory with time validity (valid_from, valid_until)
- **Multi-Layer Loading**: L0-L3 progressive disclosure (50%+ token reduction)
- **Metadata Filtering**: Project/topic/type taxonomy (34% recall improvement)
- **Agent Diaries**: Private memory spaces for individual agents
- **Staleness Detection**: Identify outdated facts automatically
- **Semantic Search**: Vector-based similarity search

---

## Key Concepts

### Temporal Facts

Facts are memories with temporal validity, allowing queries like "what was true in March 2026?"

**Core Properties:**
- `content`: The fact text
- `project`: Top-level category (e.g., "ai-stack", "dashboard")
- `topic`: Subcategory (e.g., "auth", "deployment")
- `type`: Fact type (decision, preference, discovery, event, advice, fact)
- `valid_from`: When fact became valid
- `valid_until`: When fact expires (None = ongoing)
- `agent_owner`: Agent that owns this fact (None = shared)

**Example:**
```python
from aidb.temporal_facts import TemporalFact
from datetime import datetime, timezone

fact = TemporalFact(
    content="Using JWT with 7-day expiry for authentication",
    project="ai-stack",
    topic="auth",
    type="decision",
    tags=["security", "jwt"],
    confidence=0.95,
    valid_from=datetime.now(timezone.utc)
)
```

### Multi-Layer Loading (L0-L3)

Progressive memory disclosure to minimize token usage:

**L0: Identity (50 tokens)**
- Always loaded
- Agent identity and role
- Stored in `~/.aidb/identity.txt`

**L1: Critical Facts (170 tokens)**
- Always loaded
- Recent decisions, active blockers, key preferences
- Stored in `~/.aidb/critical_facts.json`

**L2: Topic-Specific (variable)**
- Loaded on demand based on query context
- Filtered by project and topic
- Automatically selected by topic extraction

**L3: Full Semantic Search (heavy)**
- Only when explicitly requested
- Complete vector similarity search
- Use sparingly due to cost

### Agent Diaries

Each agent maintains a private diary for expertise accumulation:

- **Private memory space**: Facts with `agent_owner` set
- **Project namespace**: `agent-{name}` (e.g., `agent-qwen`)
- **Isolation**: Agents can only write to their own diary
- **Observer mode**: Orchestrators can read any diary (read-only)

### Metadata Taxonomy

Organized hierarchy for efficient filtering:

```
Memory Fact
├── project (e.g., ai-stack, dashboard, nix-config)
├── topic (e.g., auth, workflows, deployment)
└── type (decision, preference, discovery, event, advice, fact)
```

---

## Getting Started

### Installation

The memory system is included in the AI harness. Ensure you have:

```bash
# Verify installation
python3 -c "from aidb.temporal_facts import TemporalFact; print('✅ Memory system ready')"

# Check CLI tools
aq-memory --help
aq-benchmark --help
```

### Quick Start

**1. Store your first fact:**

```bash
aq-memory add "Using FastAPI for dashboard backend" \
  --project dashboard \
  --topic architecture \
  --type decision \
  --tags "fastapi,python" \
  --confidence 0.95
```

**2. Search for facts:**

```bash
aq-memory search "authentication" --project ai-stack --limit 5
```

**3. View agent diary:**

```bash
aq-memory agent-diary qwen --topic coding --limit 10
```

### Your First Memory (Python)

```python
from aidb.temporal_facts import TemporalFact
from aidb.layered_loading import LayeredMemory
from datetime import datetime, timezone

# Create a fact
fact = TemporalFact(
    content="Prefer verbose logging during development",
    project="ai-stack",
    topic="preferences",
    type="preference",
    tags=["logging", "dev"],
    confidence=1.0,
    valid_from=datetime.now(timezone.utc)
)

# Save to store (using in-memory store for demo)
from scripts.ai.aq-memory import InMemoryFactStore
store = InMemoryFactStore()
fact_id = store.add(fact)
print(f"Stored fact: {fact_id}")

# Load memory with progressive disclosure
memory = LayeredMemory(fact_store=store)
context = memory.progressive_load(
    query="What are the logging preferences?",
    max_tokens=500
)
print(context)
```

---

## Common Workflows

### Storing Facts

**Decision Facts:**
```bash
aq-memory add "Switching from SQLite to PostgreSQL for production" \
  --project ai-stack \
  --topic database \
  --type decision \
  --tags "postgres,migration" \
  --confidence 0.9
```

**Preference Facts:**
```bash
aq-memory add "User prefers tabs over spaces (4-space indent)" \
  --project coding \
  --topic style \
  --type preference
```

**Discovery Facts:**
```bash
aq-memory add "Found bug in metadata filtering returning stale facts" \
  --project ai-stack \
  --topic bugs \
  --type discovery \
  --tags "bug,metadata" \
  --confidence 0.8
```

**Temporary Facts (with expiration):**
```bash
aq-memory add "API endpoint temporarily at localhost:8889" \
  --project dashboard \
  --topic deployment \
  --type event \
  --valid-until "2026-05-01T00:00:00Z"
```

### Searching Memories

**Basic search:**
```bash
aq-memory search "JWT authentication"
```

**Filtered search:**
```bash
aq-memory search "authentication" \
  --project ai-stack \
  --topic auth \
  --type decision \
  --valid-now
```

**Python search:**
```python
from aidb.temporal_query import (
    filter_facts_by_project,
    filter_facts_by_topic,
    filter_facts_by_type
)

# Get all facts
all_facts = store.get_all()

# Filter by project
ai_facts = filter_facts_by_project(all_facts, "ai-stack")

# Filter by topic
auth_facts = filter_facts_by_topic(ai_facts, "auth")

# Filter by type
decisions = filter_facts_by_type(auth_facts, "decision")
```

### Managing Agent Diaries

**Agent writes to diary (Python):**
```python
from aidb.agent_diary import AgentDiary

diary = AgentDiary("qwen")
diary.write(
    "Implemented JWT validation with bcrypt hashing",
    topic="auth",
    tags=["jwt", "security"],
    create_fact=False  # Set to True with fact_store
)
```

**Read agent's own diary:**
```python
# Recent entries
recent = diary.read(limit=20)

# Topic-specific
auth_entries = diary.read(topic="auth", since_days=7)

# Search diary
results = diary.search("JWT implementation")
```

**Observer mode (orchestrator reading agent's diary):**
```python
from aidb.agent_diary import AgentDiary

# Read qwen's diary (read-only)
qwen_work = AgentDiary.read_as_observer("qwen", topic="auth", limit=10)

for entry in qwen_work:
    print(f"[{entry.timestamp}] {entry.content}")
```

**CLI diary access:**
```bash
# View diary
aq-memory agent-diary qwen --topic auth --limit 10

# Get diary statistics
aq-memory stats --project agent-qwen
```

### Temporal Queries

**Query facts valid at specific time:**
```python
from datetime import datetime, timezone
from aidb.temporal_facts import get_valid_facts

all_facts = store.get_all()

# What was valid on April 1st?
april_first = datetime(2026, 4, 1, tzinfo=timezone.utc)
valid_facts = get_valid_facts(all_facts, at_time=april_first)
```

**Find stale facts:**
```bash
aq-memory list --stale --project ai-stack
```

```python
from aidb.temporal_facts import get_stale_facts

stale = get_stale_facts(all_facts)
print(f"Found {len(stale)} stale facts")
```

**Expire a fact:**
```bash
aq-memory expire abc12345 \
  --until "2026-12-31T23:59:59Z" \
  --reason "superseded by new architecture"
```

---

## Best Practices

### Fact Organization

**DO:**
- Use specific, descriptive topics (not "general")
- Tag facts with relevant keywords
- Set appropriate confidence levels (0.8-1.0 for verified facts)
- Write clear, searchable content
- Use `type` field correctly (decision vs fact vs preference)

**DON'T:**
- Store sensitive data (passwords, tokens, API keys)
- Use vague topics like "misc" or "other"
- Leave facts untagged
- Write overly verbose content (keep under 200 chars when possible)
- Forget to set `valid_until` for temporary facts

### Metadata Strategy

**Project naming:**
- Use consistent project names: `ai-stack`, `dashboard`, `nix-config`
- Agent diaries use `agent-{name}`: `agent-qwen`, `agent-codex`

**Topic naming:**
- Use lowercase, hyphenated: `auth`, `api-design`, `error-handling`
- Be specific: `jwt-auth` not `auth`
- Reuse topics for consistency

**Type selection:**
- `decision`: Architectural or implementation choices
- `preference`: User or team preferences
- `discovery`: Bugs found, insights gained
- `event`: Time-bound happenings (deployments, milestones)
- `advice`: Best practices, lessons learned
- `fact`: General information

### Performance Optimization

**Token efficiency:**
```python
# Instead of loading all context
memory = LayeredMemory(fact_store=store)

# Use progressive loading with budget
context = memory.progressive_load(
    query="implement authentication",
    max_tokens=500  # Limit token usage
)
```

**Metadata filtering:**
```bash
# Slower: unfiltered search
aq-memory search "authentication"

# Faster: filtered search (34% better recall)
aq-memory search "authentication" \
  --project ai-stack \
  --topic auth \
  --type decision
```

**Layer selection:**
```python
# Light queries: L0 + L1 only
context = memory.progressive_load(query, max_tokens=220)

# Medium queries: L0 + L1 + L2
context = memory.progressive_load(query, max_tokens=520)

# Heavy queries: Force L3 (only when needed)
context = memory.progressive_load(query, max_tokens=1000, force_l3=True)
```

### Memory Hygiene

**Regular maintenance:**
```bash
# Check for stale facts monthly
aq-memory list --stale

# Review and expire outdated facts
aq-memory expire <fact_id> --until $(date +%Y-%m-%d) --reason "outdated"

# View statistics
aq-memory stats --project ai-stack
```

**Deduplication:**
- The system uses content hashing for deduplication
- Same content + project + time = same fact
- Update existing facts rather than creating duplicates

**Confidence levels:**
- 1.0: Verified, authoritative
- 0.9: High confidence, tested
- 0.8: Moderate confidence, observed
- 0.7: Low confidence, inferred
- < 0.7: Speculative, needs verification

---

## Troubleshooting

### Common Issues

**Issue: "No facts found" but I know there are relevant facts**

**Solution:**
```bash
# Check if facts are stale
aq-memory list --project ai-stack --stale

# Search without filters
aq-memory search "your query" --limit 50

# Check all facts
aq-memory list --limit 100
```

**Issue: "Agent diary returns empty"**

**Solution:**
```python
# Verify agent name
from aidb.agent_diary import AgentDiary
agents = AgentDiary.list_all_diaries()
print(f"Available diaries: {agents}")

# Check if facts exist
diary = AgentDiary("qwen")
stats = diary.get_stats()
print(stats)
```

**Issue: "Token budget exceeded"**

**Solution:**
```python
# Reduce max_tokens
context = memory.progressive_load(query, max_tokens=300)

# Use more specific filtering
from aidb.temporal_query import filter_facts_by_topic
filtered = filter_facts_by_topic(facts, "specific-topic")
```

**Issue: "Facts not being found by semantic search"**

**Solution:**
```bash
# Use tags for keyword matching
aq-memory add "..." --tags "jwt,auth,security"

# Search by tags
aq-memory search "jwt" --tags "jwt"

# Be more specific in content
# Good: "Using JWT with 7-day expiry for API authentication"
# Bad: "Using tokens for auth"
```

### Debug Commands

**Check system status:**
```bash
# View all facts
aq-memory list --limit 100

# Statistics by project
aq-memory stats --project ai-stack

# Find stale facts
aq-memory list --stale
```

**Verify layer loading:**
```python
from aidb.layered_loading import LayeredMemory

memory = LayeredMemory()

# Check loaded layers
l0 = memory.load_l0()
print(f"L0: {len(l0)} chars")

l1 = memory.load_l1()
print(f"L1: {len(l1)} chars")

# Get statistics
stats = memory.get_layer_stats()
print(stats)
```

**Test fact validity:**
```python
from datetime import datetime, timezone

fact = store.get_by_id("abc123")
now = datetime.now(timezone.utc)

print(f"Valid now: {fact.is_valid_at(now)}")
print(f"Stale: {fact.is_stale(now)}")
print(f"Ongoing: {fact.is_ongoing()}")
```

### Performance Problems

**Query taking > 500ms:**
1. Add metadata filters (project, topic, type)
2. Reduce result limit
3. Check database indexes
4. Use L2 instead of L3 loading

**High token usage:**
1. Use progressive loading with budget
2. Filter to specific topics
3. Avoid loading L3 unnecessarily
4. Set identity and critical facts appropriately

**Low recall accuracy:**
1. Add more metadata (tags, topic, type)
2. Use metadata filtering in queries
3. Improve fact content clarity
4. Check for stale facts

---

## FAQ

**Q: What's the difference between `type` and `topic`?**

A: `type` categorizes the kind of fact (decision, preference, etc.), while `topic` is the subject matter (auth, deployment, etc.). Think of `type` as "what kind of memory" and `topic` as "what it's about."

**Q: Should I set `valid_until` for all facts?**

A: No. Only set `valid_until` for facts you know will become outdated (temporary configurations, time-bound events). Most facts should be ongoing (valid_until=None).

**Q: Can agents read each other's diaries?**

A: Agents can only write to their own diaries. Orchestrators can read any diary in "observer mode" (read-only) for review purposes.

**Q: How do I migrate existing memories to the new system?**

A: The system provides backward compatibility. Existing queries work via a compatibility view. For full features, use the migration script in `ai-stack/aidb/schema/migrations/`.

**Q: What happens if I store duplicate facts?**

A: The system uses content hashing for deduplication. Facts with the same content, project, and valid_from are considered duplicates and only one is stored.

**Q: How often should I check for stale facts?**

A: Monthly is a good baseline. Run `aq-memory list --stale` and expire outdated facts with a reason.

**Q: What's the token reduction from multi-layer loading?**

A: Average 50%+ reduction. L0+L1 only = 78% reduction (220 tokens vs 1000). Full progressive loading = 40-70% reduction depending on query.

**Q: Can I use the memory system without Python?**

A: Yes! Use the `aq-memory` CLI for all operations. The Python API is for programmatic access and integration.

**Q: How do I benchmark my memory setup?**

A: Use `aq-benchmark` with your own corpus:
```bash
aq-benchmark run --corpus my-corpus.json --output results.json
aq-benchmark report results.json --format html
```

**Q: Where are facts stored?**

A: Facts are stored in `.aidb/temporal_facts.json` (in-memory mode) or PostgreSQL database (production mode). Identity is in `~/.aidb/identity.txt`, critical facts in `~/.aidb/critical_facts.json`.

---

## Next Steps

- **API Reference**: See [API-REFERENCE.md](./API-REFERENCE.md) for detailed API documentation
- **Integration Examples**: See [INTEGRATION-EXAMPLES.md](./INTEGRATION-EXAMPLES.md) for code examples
- **Quick Reference**: See [QUICK-REFERENCE.md](./QUICK-REFERENCE.md) for command cheat sheet
- **Architecture**: See [../architecture/memory-system-design.md](../architecture/memory-system-design.md) for system design

---

**Questions or Issues?**

- Check the [troubleshooting section](#troubleshooting) above
- Review [INTEGRATION-EXAMPLES.md](./INTEGRATION-EXAMPLES.md) for working code
- See [API-REFERENCE.md](./API-REFERENCE.md) for function signatures
