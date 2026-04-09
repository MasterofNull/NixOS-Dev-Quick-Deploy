# Memory System Architecture Design

**Version:** 1.0.0
**Date:** 2026-04-09
**Phase:** 1 Slice 1.1
**Owner:** claude (architecture)
**Status:** Initial Design - Ready for Review

---

## Executive Summary

This document defines the enhanced AIDB memory system architecture incorporating:
1. **Temporal validity** - Facts with start/end dates and staleness detection
2. **Multi-layer loading** (L0-L3) - Progressive context loading for 50%+ token reduction
3. **Metadata filtering** - Project/topic/type taxonomy for 34% recall improvement
4. **Agent-specific diaries** - Isolated memory per agent for expertise accumulation

**Inspiration:** MemPalace (96.6% recall benchmark) with adaptations for our use case

---

## Current State Analysis

### Existing AIDB Capabilities

**What We Have:**
- PostgreSQL database for structured data
- Vector embeddings (via ChromaDB or pgvector)
- Basic category and project filtering
- Session log storage

**What We're Missing:**
- Temporal validity tracking
- Memory organization taxonomy
- Multi-layer loading strategy
- Agent memory isolation
- Staleness detection
- Contradiction checking

**Baseline Performance:**
- Recall accuracy: Not benchmarked (estimated 60-70%)
- Query latency: ~200-400ms for simple queries
- Token usage: Load all or nothing (inefficient)

---

## Design Goals

1. **Improve Recall Accuracy**: 60% → 90%+ via metadata filtering
2. **Reduce Token Usage**: 50%+ reduction via multi-layer loading
3. **Enable Temporal Queries**: "What was true in March 2026?"
4. **Isolate Agent Memory**: Each agent builds expertise independently
5. **Maintain Performance**: < 500ms p95 query latency
6. **Preserve Backward Compatibility**: Existing AIDB queries still work

---

## Architecture Overview

```
┌─────────────────────────────────────────────────────────────┐
│                  Memory System (AIDB v2)                    │
├─────────────────────────────────────────────────────────────┤
│                                                              │
│  ┌────────────────┐  ┌──────────────┐  ┌────────────────┐  │
│  │   L0: Identity │  │ L1: Critical │  │  L2: Topic     │  │
│  │   (50 tokens)  │  │  (170 tokens)│  │  (variable)    │  │
│  └────────────────┘  └──────────────┘  └────────────────┘  │
│           ▲                  ▲                  ▲           │
│           └──────────────────┴──────────────────┘           │
│                              │                              │
│                    ┌─────────┴─────────┐                    │
│                    │ Progressive Loader │                    │
│                    └─────────┬─────────┘                    │
│                              │                              │
│  ┌───────────────────────────┴──────────────────────────┐  │
│  │            Temporal Facts Store                       │  │
│  │  ┌─────────────────────────────────────────────────┐ │  │
│  │  │  fact_id, content, project, topic, type,        │ │  │
│  │  │  valid_from, valid_until, agent_owner,          │ │  │
│  │  │  created_at, embedding_vector                    │ │  │
│  │  └─────────────────────────────────────────────────┘ │  │
│  └─────────────────────────────────────────────────────┘  │
│                              │                              │
│  ┌───────────────────────────┴──────────────────────────┐  │
│  │         Metadata Index (project/topic/type)          │  │
│  └──────────────────────────────────────────────────────┘  │
│                              │                              │
│  ┌───────────────────────────┴──────────────────────────┐  │
│  │         Agent Diaries (isolated per agent)           │  │
│  │  qwen/ | codex/ | claude/ | gemini/                  │  │
│  └──────────────────────────────────────────────────────┘  │
└─────────────────────────────────────────────────────────────┘
```

---

## Component 1: Memory Organization Taxonomy

### Terminology Decision

**MemPalace uses:** Wings → Rooms → Halls (palace metaphor)
**We will use:** Projects → Topics → Types (direct, no metaphor)

**Rationale:**
- More intuitive for technical users
- Aligns with existing AIDB `project` field
- No learning curve for palace metaphor

### Taxonomy Structure

```
Memory Fact
├── project (Wing equivalent)
│   ├── ai-stack
│   ├── dashboard
│   ├── nix-config
│   ├── agent-qwen
│   ├── agent-codex
│   └── agent-claude
│
├── topic (Room equivalent)
│   ├── authentication
│   ├── workflows
│   ├── memory-system
│   ├── deployment
│   └── [free-form, agent-defined]
│
└── type (Hall equivalent)
    ├── decision
    ├── preference
    ├── discovery
    ├── event
    ├── advice
    └── fact
```

### Example Memories

```json
{
  "content": "Using JWT with 7-day expiry for API authentication",
  "project": "ai-stack",
  "topic": "authentication",
  "type": "decision",
  "valid_from": "2026-04-09T00:00:00Z",
  "valid_until": null,
  "agent_owner": "qwen"
}

{
  "content": "User prefers verbose logging during development",
  "project": "dashboard",
  "topic": "preferences",
  "type": "preference",
  "valid_from": "2026-03-15T00:00:00Z",
  "valid_until": null,
  "agent_owner": null
}

{
  "content": "Dashboard served from FastAPI at port 8889",
  "project": "dashboard",
  "topic": "architecture",
  "type": "fact",
  "valid_from": "2026-04-01T00:00:00Z",
  "valid_until": "2026-04-05T00:00:00Z",
  "agent_owner": null
}
```

---

## Component 2: Temporal Validity Schema

### Database Schema

```sql
-- ai-stack/aidb/schema/temporal-facts-v2.sql

CREATE TABLE IF NOT EXISTS temporal_facts (
    fact_id UUID PRIMARY KEY DEFAULT gen_random_uuid(),

    -- Content
    content TEXT NOT NULL,
    content_hash VARCHAR(64) NOT NULL,  -- SHA256 for deduplication

    -- Organization
    project VARCHAR(255) NOT NULL,
    topic VARCHAR(255),
    type VARCHAR(50) NOT NULL CHECK (type IN (
        'decision', 'preference', 'discovery', 'event', 'advice', 'fact'
    )),

    -- Temporal validity
    valid_from TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT NOW(),
    valid_until TIMESTAMP WITH TIME ZONE,  -- NULL = ongoing/indefinite

    -- Agent ownership (NULL = shared memory)
    agent_owner VARCHAR(50),  -- qwen, codex, claude, gemini, or NULL

    -- Metadata
    tags TEXT[],  -- Additional categorization
    confidence FLOAT DEFAULT 1.0,  -- 0.0-1.0 confidence score
    source VARCHAR(255),  -- Where did this fact come from?

    -- Embeddings
    embedding_vector vector(1536),  -- For semantic search

    -- Audit
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    created_by VARCHAR(50),  -- Which agent/user created this
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    version INT DEFAULT 1,

    -- Indexes
    CONSTRAINT unique_content_project_time UNIQUE (content_hash, project, valid_from)
);

-- Indexes for performance
CREATE INDEX idx_temporal_facts_project ON temporal_facts(project);
CREATE INDEX idx_temporal_facts_topic ON temporal_facts(topic);
CREATE INDEX idx_temporal_facts_type ON temporal_facts(type);
CREATE INDEX idx_temporal_facts_agent ON temporal_facts(agent_owner);
CREATE INDEX idx_temporal_facts_valid_from ON temporal_facts(valid_from);
CREATE INDEX idx_temporal_facts_valid_until ON temporal_facts(valid_until);
CREATE INDEX idx_temporal_facts_composite ON temporal_facts(project, topic, type);

-- GiST index for vector similarity search
CREATE INDEX idx_temporal_facts_embedding ON temporal_facts
USING ivfflat (embedding_vector vector_cosine_ops);

-- Function to check if fact is valid at timestamp
CREATE OR REPLACE FUNCTION is_valid_at(
    fact temporal_facts,
    check_time TIMESTAMP WITH TIME ZONE
) RETURNS BOOLEAN AS $$
BEGIN
    RETURN check_time >= fact.valid_from AND
           (fact.valid_until IS NULL OR check_time <= fact.valid_until);
END;
$$ LANGUAGE plpgsql IMMUTABLE;

-- Function to check if fact is stale
CREATE OR REPLACE FUNCTION is_stale(
    fact temporal_facts,
    current_time TIMESTAMP WITH TIME ZONE
) RETURNS BOOLEAN AS $$
BEGIN
    RETURN fact.valid_until IS NOT NULL AND
           current_time > fact.valid_until;
END;
$$ LANGUAGE plpgsql IMMUTABLE;
```

### Migration Strategy

```sql
-- ai-stack/aidb/schema/migrations/001_temporal_facts.sql

-- Step 1: Create new table
-- (See schema above)

-- Step 2: Migrate existing data
INSERT INTO temporal_facts (content, project, topic, type, embedding_vector, created_at)
SELECT
    content,
    COALESCE(project, 'legacy') as project,
    COALESCE(category, 'general') as topic,
    'fact' as type,
    embedding as embedding_vector,
    timestamp as created_at
FROM existing_memories_table
WHERE content IS NOT NULL;

-- Step 3: Create view for backward compatibility
CREATE OR REPLACE VIEW memories AS
SELECT
    fact_id as id,
    content,
    project,
    topic as category,
    embedding_vector as embedding,
    created_at as timestamp
FROM temporal_facts
WHERE valid_until IS NULL OR valid_until > NOW();

-- Step 4: Update existing queries to use view or new table
-- (Done in application code)
```

---

## Component 3: Multi-Layer Loading (L0-L3)

### Layer Definitions

**L0: Identity (Always Loaded, ~50 tokens)**
- Who am I?
- What's my role?
- What system am I on?
- What's my primary focus?

**L1: Critical Facts (Always Loaded, ~170 tokens)**
- Must-know information for any task
- Recent decisions (last 7 days)
- Active projects
- Ongoing issues/blockers
- Key preferences

**L2: Topic-Specific (On-Demand, Variable)**
- Memories related to query topic
- Filtered by project + topic
- Sorted by relevance and recency
- Load until token budget reached

**L3: Full Semantic Search (Explicit Only, Heavy)**
- Complete vector similarity search
- No metadata filtering
- Highest recall but highest cost
- Only when explicitly requested

### Loading Strategy

```python
# ai-stack/aidb/layered_loading.py

class LayeredMemoryLoader:
    def __init__(self):
        self.identity_path = Path.home() / ".aidb" / "identity.txt"
        self.max_tokens = {
            "l0": 50,
            "l1": 170,
            "l2": 300,
            "l3": 1000
        }

    def load_progressive(self, query: str, max_tokens: int = 500, layers: List[str] = None):
        """
        Load memory layers progressively until token budget reached

        Args:
            query: Natural language query
            max_tokens: Maximum tokens to load
            layers: Which layers to load (default: ["l0", "l1", "l2"])

        Returns:
            str: Concatenated context from all layers
        """
        if layers is None:
            layers = ["l0", "l1", "l2"]

        context_parts = []
        budget_remaining = max_tokens

        # L0: Identity (always load if requested)
        if "l0" in layers:
            l0 = self.load_l0()
            tokens = count_tokens(l0)
            if tokens <= budget_remaining:
                context_parts.append(("L0_IDENTITY", l0))
                budget_remaining -= tokens

        # L1: Critical facts (always load if requested)
        if "l1" in layers and budget_remaining > 50:
            l1 = self.load_l1()
            tokens = count_tokens(l1)
            if tokens <= budget_remaining:
                context_parts.append(("L1_CRITICAL", l1))
                budget_remaining -= tokens

        # L2: Topic-specific (load relevant topics)
        if "l2" in layers and budget_remaining > 100:
            topics = extract_topics_from_query(query)
            project = extract_project_from_query(query)

            l2_facts = self.load_l2(topics, project, max_tokens=budget_remaining)
            if l2_facts:
                tokens = count_tokens(l2_facts)
                context_parts.append(("L2_TOPIC", l2_facts))
                budget_remaining -= tokens

        # L3: Full search (only if explicitly requested)
        if "l3" in layers and "deep_search" in query.lower() and budget_remaining > 200:
            l3_results = self.load_l3(query, max_tokens=budget_remaining)
            if l3_results:
                context_parts.append(("L3_FULL", l3_results))

        # Format context
        return self.format_context(context_parts)

    def load_l0(self) -> str:
        """Load identity file (~50 tokens)"""
        if self.identity_path.exists():
            return self.identity_path.read_text().strip()
        return self.generate_default_identity()

    def load_l1(self) -> str:
        """
        Load critical facts (~170 tokens)

        Criteria for L1:
        - Decisions made in last 7 days
        - Active blockers
        - Recent preferences
        - Key facts about active projects
        """
        query = """
        SELECT content, project, topic
        FROM temporal_facts
        WHERE
            (type = 'decision' AND valid_from > NOW() - INTERVAL '7 days')
            OR (type = 'preference' AND valid_from > NOW() - INTERVAL '30 days')
            OR (tags && ARRAY['critical', 'blocker', 'active'])
        ORDER BY valid_from DESC
        LIMIT 20
        """

        facts = execute_query(query)
        return self.compile_critical_facts(facts)

    def load_l2(self, topics: List[str], project: str = None, max_tokens: int = 300) -> str:
        """
        Load topic-specific memories

        Uses metadata filtering for 34% accuracy improvement
        """
        filters = []
        if topics:
            filters.append(f"topic IN ({', '.join(['%s'] * len(topics))})")
        if project:
            filters.append("project = %s")

        where_clause = " AND ".join(filters) if filters else "1=1"

        query = f"""
        SELECT content, project, topic, type, valid_from
        FROM temporal_facts
        WHERE {where_clause}
          AND (valid_until IS NULL OR valid_until > NOW())
        ORDER BY valid_from DESC
        LIMIT 50
        """

        params = topics + ([project] if project else [])
        results = execute_query(query, params)

        # Truncate to token budget
        return self.truncate_to_budget(results, max_tokens)

    def load_l3(self, query: str, max_tokens: int = 1000) -> str:
        """
        Full semantic search (expensive)

        Only use when explicitly requested
        """
        embedding = get_embedding(query)

        query_sql = """
        SELECT content, project, topic,
               embedding_vector <=> %s::vector AS distance
        FROM temporal_facts
        WHERE valid_until IS NULL OR valid_until > NOW()
        ORDER BY distance
        LIMIT 100
        """

        results = execute_query(query_sql, [embedding])
        return self.truncate_to_budget(results, max_tokens)
```

### Identity File Example

```
# ~/.aidb/identity.txt (50 tokens max)

I am the AI coordinator for NixOS-Dev-Quick-Deploy running on hyperd's desktop.
System: NixOS, 32GB RAM, RTX 3090 GPU.
My role: orchestrate local agents (qwen, codex, claude, gemini) for software development tasks.
Focus: local-first AI, declarative NixOS infrastructure, cost optimization, workflow automation.
```

---

## Component 4: Agent-Specific Diaries

### Isolation Strategy

**Goal:** Each agent builds expertise independently without cross-contamination

**Implementation:**
- Separate project namespace: `agent-{name}`
- Filter by `agent_owner` field
- Private read/write access only to own diary

### Schema Addition

```sql
-- Agent diary is just temporal_facts with agent_owner set
-- No separate table needed

-- Example: qwen's diary
INSERT INTO temporal_facts (content, project, topic, type, agent_owner)
VALUES (
    'Implemented JWT with bcrypt hashing and 7-day expiry',
    'agent-qwen',  -- Diary project
    'authentication',
    'discovery',
    'qwen'  -- Owner
);

-- Query qwen's diary
SELECT * FROM temporal_facts
WHERE agent_owner = 'qwen'
  AND project = 'agent-qwen'
ORDER BY valid_from DESC;
```

### API Interface

```python
# ai-stack/aidb/agent_diary.py

class AgentDiary:
    def __init__(self, agent_name: str):
        self.agent = agent_name
        self.project = f"agent-{agent_name}"

    def write(self, entry: str, topic: str = None, type: str = "discovery", tags: List[str] = None):
        """Write to agent's private diary"""
        fact = TemporalFact(
            content=entry,
            project=self.project,
            topic=topic or "general",
            type=type,
            agent_owner=self.agent,
            tags=tags or [],
            valid_from=datetime.now()
        )
        return self.store(fact)

    def read(self, topic: str = None, since: datetime = None, limit: int = 50):
        """Read from agent's diary"""
        filters = {
            "agent_owner": self.agent,
            "project": self.project
        }
        if topic:
            filters["topic"] = topic
        if since:
            filters["valid_from__gte"] = since

        return self.query(filters, limit=limit)

    def search(self, query: str, max_tokens: int = 300):
        """Semantic search within agent's diary"""
        return search_with_metadata(
            query,
            project=self.project,
            agent_owner=self.agent,
            max_tokens=max_tokens
        )
```

---

## Component 5: Metadata Filtering

### Performance Impact

**MemPalace Benchmark:**
- Without filtering: 60.9% recall @ 10 results
- With wing + room + hall: 94.8% recall @ 10 results
- **Improvement: +34 percentage points**

### Implementation

```python
# ai-stack/aidb/metadata_filter.py

def search_with_metadata(
    query: str,
    project: str = None,
    topic: str = None,
    type: str = None,
    agent_owner: str = None,
    valid_at: datetime = None,
    max_tokens: int = 500
) -> List[TemporalFact]:
    """
    Search with metadata filtering

    Combines semantic search with metadata for 34% accuracy improvement
    """

    # Build filter clauses
    filters = []
    params = []

    if project:
        filters.append("project = %s")
        params.append(project)

    if topic:
        filters.append("topic = %s")
        params.append(topic)

    if type:
        filters.append("type = %s")
        params.append(type)

    if agent_owner:
        filters.append("agent_owner = %s")
        params.append(agent_owner)

    # Temporal filter
    if valid_at:
        filters.append("valid_from <= %s")
        filters.append("(valid_until IS NULL OR valid_until >= %s)")
        params.extend([valid_at, valid_at])
    else:
        filters.append("(valid_until IS NULL OR valid_until > NOW())")

    # Get embedding for semantic search
    embedding = get_embedding(query)
    params.insert(0, embedding)

    # Combine semantic + metadata filtering
    where_clause = " AND ".join(filters) if filters else "1=1"

    query_sql = f"""
    SELECT
        fact_id, content, project, topic, type,
        valid_from, valid_until, agent_owner,
        embedding_vector <=> %s::vector AS distance
    FROM temporal_facts
    WHERE {where_clause}
    ORDER BY distance ASC
    LIMIT 100
    """

    results = execute_query(query_sql, params)

    # Truncate to token budget
    return truncate_to_budget(results, max_tokens)
```

---

## Performance Targets

### Query Latency

| Operation | Target | Rationale |
|-----------|--------|-----------|
| L0 load (identity) | < 10ms | File read |
| L1 load (critical) | < 100ms | ~20 rows, indexed |
| L2 load (topic) | < 300ms | ~50 rows, filtered |
| L3 load (full search) | < 500ms | Vector search, acceptable for deep search |
| Metadata-only filter | < 50ms | Index-only query |
| Combined semantic + metadata | < 400ms | Hybrid query |

### Recall Accuracy

| Scenario | Target | Baseline |
|----------|--------|----------|
| Unfiltered search | 65-70% | Current (estimated) |
| Project filtering | 75-80% | +10-15% |
| Project + topic filtering | 85-90% | +20-25% |
| Project + topic + type | 90-95% | +25-30% (MemPalace: 94.8%) |

### Token Efficiency

| Approach | Tokens | Reduction |
|----------|--------|-----------|
| Load all context | ~1000 | Baseline |
| L0 + L1 only | ~220 | 78% reduction |
| L0 + L1 + L2 | ~520 | 48% reduction |
| Progressive loading | ~300-600 | 40-70% reduction |

**Target:** 50%+ average token reduction via multi-layer loading

---

## Backward Compatibility

### Migration Path

**Phase 1: Additive (No Breaking Changes)**
- Create `temporal_facts` table alongside existing
- Create compatibility view for old queries
- Dual-write to both old and new tables

**Phase 2: Transition (Deprecation Warnings)**
- Update application code to use new table
- Add deprecation warnings to old APIs
- Monitor usage of old table

**Phase 3: Cleanup (Remove Old)**
- Drop old table once no usage detected
- Remove compatibility shims
- Update all documentation

### Compatibility View

```sql
CREATE OR REPLACE VIEW memories AS
SELECT
    fact_id::text as id,
    content,
    project,
    topic as category,  -- Map topic → category
    embedding_vector as embedding,
    created_at as timestamp
FROM temporal_facts
WHERE (valid_until IS NULL OR valid_until > NOW())
  AND agent_owner IS NULL;  -- Exclude agent diaries from shared view
```

---

## Security Considerations

### Agent Isolation

**Threat:** Agent A reads Agent B's private diary
**Mitigation:** Enforce `agent_owner` filter in all diary operations

```python
# INSECURE - Don't do this
def read_diary(agent_name):
    return query("SELECT * FROM temporal_facts WHERE project = %s", [f"agent-{agent_name}"])

# SECURE - Always verify ownership
def read_diary(requesting_agent, target_agent):
    if requesting_agent != target_agent:
        raise PermissionError(f"{requesting_agent} cannot read {target_agent}'s diary")

    return query(
        "SELECT * FROM temporal_facts WHERE agent_owner = %s",
        [requesting_agent]
    )
```

### Temporal Integrity

**Threat:** Malicious updates to `valid_until` to hide facts
**Mitigation:** Audit log all temporal updates, version history

```sql
-- Track all updates
CREATE TABLE temporal_facts_audit (
    audit_id SERIAL PRIMARY KEY,
    fact_id UUID REFERENCES temporal_facts(fact_id),
    field_changed VARCHAR(50),
    old_value TEXT,
    new_value TEXT,
    changed_by VARCHAR(50),
    changed_at TIMESTAMP DEFAULT NOW()
);

-- Trigger on UPDATE
CREATE OR REPLACE FUNCTION audit_temporal_changes()
RETURNS TRIGGER AS $$
BEGIN
    IF OLD.valid_until IS DISTINCT FROM NEW.valid_until THEN
        INSERT INTO temporal_facts_audit (fact_id, field_changed, old_value, new_value, changed_by)
        VALUES (NEW.fact_id, 'valid_until', OLD.valid_until::TEXT, NEW.valid_until::TEXT, current_user);
    END IF;
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

CREATE TRIGGER temporal_facts_audit_trigger
AFTER UPDATE ON temporal_facts
FOR EACH ROW EXECUTE FUNCTION audit_temporal_changes();
```

---

## Testing Strategy

### Unit Tests

```python
# ai-stack/aidb/tests/test_temporal_facts.py

def test_temporal_validity():
    """Test temporal validity checking"""
    fact = TemporalFact(
        content="Test fact",
        valid_from=datetime(2026, 4, 1),
        valid_until=datetime(2026, 4, 30)
    )

    assert fact.is_valid_at(datetime(2026, 4, 15)) == True
    assert fact.is_valid_at(datetime(2026, 3, 15)) == False
    assert fact.is_valid_at(datetime(2026, 5, 15)) == False

def test_staleness_detection():
    """Test staleness detection"""
    fact = TemporalFact(
        content="Stale fact",
        valid_from=datetime(2026, 3, 1),
        valid_until=datetime(2026, 3, 31)
    )

    assert fact.is_stale(datetime(2026, 4, 9)) == True
    assert fact.is_stale(datetime(2026, 3, 15)) == False

def test_metadata_filtering():
    """Test metadata filtering improves recall"""
    # Without filtering
    unfiltered = search("authentication")

    # With filtering
    filtered = search_with_metadata(
        "authentication",
        project="ai-stack",
        topic="security"
    )

    # Filtered should have higher precision
    assert precision(filtered) > precision(unfiltered)
```

### Integration Tests

```python
def test_multi_layer_loading():
    """Test L0-L3 progressive loading"""
    loader = LayeredMemoryLoader()

    # Load with small budget (should get L0+L1 only)
    context = loader.load_progressive("test query", max_tokens=250)
    assert "L0_IDENTITY" in context
    assert "L1_CRITICAL" in context
    assert "L2_TOPIC" not in context  # Budget exhausted

    # Load with large budget (should get L0+L1+L2)
    context = loader.load_progressive("test query", max_tokens=600)
    assert "L0_IDENTITY" in context
    assert "L1_CRITICAL" in context
    assert "L2_TOPIC" in context
```

### Benchmark Tests

```python
def test_recall_benchmark():
    """Test recall accuracy against benchmark corpus"""
    corpus = load_benchmark_corpus("test-data/memory-benchmark.json")

    results = {
        "unfiltered": [],
        "project_filter": [],
        "full_filter": []
    }

    for query, expected_facts in corpus:
        # Test different filtering levels
        unfiltered = search(query.text)
        project_filtered = search_with_metadata(query.text, project=query.project)
        full_filtered = search_with_metadata(
            query.text,
            project=query.project,
            topic=query.topic,
            type=query.type
        )

        results["unfiltered"].append(recall_at_k(unfiltered, expected_facts, k=10))
        results["project_filter"].append(recall_at_k(project_filtered, expected_facts, k=10))
        results["full_filter"].append(recall_at_k(full_filtered, expected_facts, k=10))

    # Assert improvement
    avg_unfiltered = mean(results["unfiltered"])
    avg_full = mean(results["full_filter"])

    assert avg_full > avg_unfiltered + 0.20  # At least 20% improvement
    print(f"Recall@10: {avg_unfiltered:.1%} → {avg_full:.1%} (+{avg_full-avg_unfiltered:.1%})")
```

---

## Implementation Checklist

### Phase 1 Slice 1.1 (This Document)
- [x] Define memory organization taxonomy
- [x] Design temporal validity schema
- [x] Specify multi-layer loading strategy
- [x] Design agent diary isolation
- [x] Create SQL schema
- [x] Define migration path
- [x] Document performance targets
- [x] Specify testing strategy

### Phase 1 Slice 1.2 (Next)
- [ ] Implement TemporalFact class
- [ ] Implement temporal query API
- [ ] Create database migration script
- [ ] Write unit tests

### Phase 1 Slice 1.3 (Parallel with 1.2)
- [ ] Implement metadata filtering
- [ ] Add metadata indexes
- [ ] Benchmark filtering performance
- [ ] Write integration tests

### Phase 1 Slice 1.7 (After 1.2+1.3)
- [ ] Implement LayeredMemoryLoader
- [ ] Create identity file management
- [ ] Implement L0-L3 loading
- [ ] Benchmark token reduction

### Phase 1 Slice 1.8 (After 1.7)
- [ ] Implement AgentDiary class
- [ ] Add agent isolation enforcement
- [ ] Create MCP tools for diary access
- [ ] Write security tests

---

## Open Questions for Review

1. **Taxonomy:** Confirm project/topic/type vs wing/room/hall
   - **Recommendation:** Use project/topic/type (more intuitive)

2. **Identity Storage:** File-based (~/.aidb/identity.txt) or database?
   - **Recommendation:** File-based for simplicity, database backup

3. **L1 Critical Facts:** Auto-compile or manual curation?
   - **Recommendation:** Auto-compile with manual override

4. **Agent Diary Access:** Should codex (reviewer) read others' diaries?
   - **Recommendation:** Yes, for review purposes, with audit log

5. **Staleness Threshold:** How many days until fact marked stale?
   - **Recommendation:** No automatic marking, must be explicit `valid_until`

---

## Next Steps

**Immediate (Phase 1 Slice 1.2):**
1. Implement `TemporalFact` class in `ai-stack/aidb/temporal_facts.py`
2. Create database migration script
3. Write unit tests

**Short-Term (Phase 1 Slices 1.3-1.6):**
1. Implement metadata filtering
2. Create `aq-memory` CLI
3. Build benchmark harness
4. Write documentation

**Medium-Term (Phase 1.5 Slices 1.7-1.8):**
1. Implement multi-layer loading
2. Create agent diary system
3. Benchmark token reduction
4. Test expertise accumulation

---

**Document Status:** READY FOR REVIEW
**Reviewer:** codex
**Approval Required:** Before proceeding to Slice 1.2

**Version History:**
- v1.0.0 (2026-04-09): Initial design by claude
