# Context Rot and Recall System Design

**Objective:** Prevent context rot while preserving critical long-term memory and development data. Implement smart compaction triggering before automatic thresholds.

**Created:** 2026-03-15
**Status:** Design Phase

---

## Problem Statement

A system that remembers everything effectively remembers nothing. Context windows have hard limits, and indiscriminate retention leads to:

1. **Context Dilution** - Important information buried in noise
2. **Degraded Relevance** - Old context becomes stale and misleading
3. **Token Waste** - Precious context budget consumed by low-value data
4. **Compaction Churn** - Reactive compaction loses important nuance

**Solution:** Implement intelligent context lifecycle management with importance scoring, decay modeling, and proactive compaction.

---

## Core Principles

1. **Importance-Based Retention** - Keep what matters, prune what doesn't
2. **Decay Modeling** - Context relevance degrades over time
3. **Semantic Clustering** - Group related context for efficient recall
4. **Proactive Compaction** - Trigger before forced summarization
5. **Persistent Memory** - Critical data survives compaction cycles

---

## Context Lifecycle States

```
FRESH (0-1h)      → High relevance, full detail preserved
  ↓
ACTIVE (1-8h)     → Medium relevance, detail preserved
  ↓
AGING (8-24h)     → Declining relevance, summarization candidate
  ↓
STALE (1-7d)      → Low relevance, compact or archive
  ↓
ARCHIVED (7d+)    → Long-term storage, recall on demand
```

---

## Importance Scoring Algorithm

**Context Importance Score (CIS):** 0.0 - 1.0

### Factors

| Factor | Weight | Description |
|--------|--------|-------------|
| Recency | 0.25 | Exponential decay from creation time |
| Reference Count | 0.20 | How often context is referenced |
| Code Changes | 0.25 | Associated with committed code |
| User Interaction | 0.15 | Explicit user engagement |
| Semantic Centrality | 0.10 | Connection to other important context |
| Error Resolution | 0.05 | Led to successful problem resolution |

### Formula

```python
CIS = (
    0.25 * recency_score +
    0.20 * min(1.0, reference_count / 10) +
    0.25 * (1.0 if has_code_changes else 0.0) +
    0.15 * user_interaction_score +
    0.10 * semantic_centrality +
    0.05 * (1.0 if resolved_error else 0.0)
)
```

### Decay Model

```python
recency_score = e^(-λt)
where:
  λ = decay_constant (0.1 for typical dev work)
  t = time_since_creation (hours)
```

---

## Database Schema

### `context_memory` Table

```sql
CREATE TABLE IF NOT EXISTS context_memory (
    id TEXT PRIMARY KEY,
    created_at TIMESTAMP NOT NULL,
    last_accessed TIMESTAMP NOT NULL,
    lifecycle_state TEXT NOT NULL,  -- fresh, active, aging, stale, archived
    importance_score REAL NOT NULL,
    reference_count INTEGER DEFAULT 0,

    -- Content
    context_type TEXT NOT NULL,  -- conversation, file_read, code_change, error, decision
    content TEXT NOT NULL,
    summary TEXT,  -- Generated summary for quick recall

    -- Metadata
    session_id TEXT,
    task_id TEXT,
    tags TEXT,  -- JSON array

    -- Associations
    related_files TEXT,  -- JSON array of file paths
    related_commits TEXT,  -- JSON array of commit hashes
    related_context_ids TEXT,  -- JSON array of related context IDs

    -- Flags
    is_pinned BOOLEAN DEFAULT FALSE,  -- Never auto-prune
    is_archived BOOLEAN DEFAULT FALSE,
    is_error_resolution BOOLEAN DEFAULT FALSE
);

CREATE INDEX idx_context_lifecycle ON context_memory(lifecycle_state);
CREATE INDEX idx_context_importance ON context_memory(importance_score DESC);
CREATE INDEX idx_context_created ON context_memory(created_at DESC);
CREATE INDEX idx_context_session ON context_memory(session_id);
CREATE INDEX idx_context_task ON context_memory(task_id);
```

### `context_references` Table

```sql
CREATE TABLE IF NOT EXISTS context_references (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    context_id TEXT NOT NULL,
    referenced_at TIMESTAMP NOT NULL,
    reference_type TEXT NOT NULL,  -- recall, reuse, citation
    session_id TEXT,
    FOREIGN KEY (context_id) REFERENCES context_memory(id)
);

CREATE INDEX idx_ref_context ON context_references(context_id);
CREATE INDEX idx_ref_time ON context_references(referenced_at DESC);
```

---

## Smart Compaction Strategy

### Proactive Trigger Thresholds

| Metric | Threshold | Action |
|--------|-----------|--------|
| Context Window Usage | >75% | Trigger compaction planning |
| Token Count | >150k | Begin aggressive pruning |
| Stale Context Ratio | >40% | Archive stale low-importance |
| Session Duration | >4h | Proactive summarization |

### Compaction Algorithm

```python
def smart_compact(current_token_count, window_limit):
    """
    Proactive context compaction with importance preservation.

    Returns:
        - Contexts to keep (full)
        - Contexts to summarize
        - Contexts to archive
    """

    # Load all context sorted by importance
    contexts = load_contexts(order_by="importance_score DESC")

    # Calculate target retention
    target_tokens = window_limit * 0.70  # Keep 70% headroom
    budget_remaining = target_tokens

    keep_full = []
    summarize = []
    archive = []

    for ctx in contexts:
        # Always keep pinned context
        if ctx.is_pinned:
            keep_full.append(ctx)
            budget_remaining -= ctx.token_count
            continue

        # Keep high-importance fresh context
        if ctx.importance_score >= 0.8 and ctx.lifecycle_state in ("fresh", "active"):
            keep_full.append(ctx)
            budget_remaining -= ctx.token_count
            continue

        # Summarize medium-importance aging context
        if ctx.importance_score >= 0.5 and ctx.lifecycle_state == "aging":
            summarize.append(ctx)
            budget_remaining -= (ctx.token_count * 0.2)  # 80% reduction via summary
            continue

        # Archive low-importance or stale context
        if ctx.importance_score < 0.5 or ctx.lifecycle_state == "stale":
            archive.append(ctx)
            budget_remaining -= 0  # Archived context uses no window
            continue

        # If budget exhausted, archive remaining
        if budget_remaining <= 0:
            archive.append(ctx)

    return keep_full, summarize, archive
```

---

## Context Recall System

### On-Demand Recall

When an archived context becomes relevant:

1. **Trigger:** User mentions related file, task, or error
2. **Semantic Search:** Find archived contexts by similarity
3. **Restore:** Load archived context summary into active window
4. **Promote:** Update lifecycle state to FRESH

### Recall Query

```python
def recall_context(query: str, max_results: int = 5) -> List[Context]:
    """
    Recall archived context based on semantic similarity.

    Args:
        query: Natural language query or file path
        max_results: Maximum contexts to recall

    Returns:
        List of recalled contexts (summary form)
    """
    # Embed query
    query_embedding = embed_text(query)

    # Search archived contexts
    results = vector_search(
        collection="context_archive",
        query_vector=query_embedding,
        limit=max_results,
        filter={"is_archived": True}
    )

    # Promote recalled contexts
    for result in results:
        update_context_state(result.id, lifecycle_state="FRESH")
        increment_reference_count(result.id)

    return results
```

---

## Implementation Tasks

### Phase 1: Database Schema (Immediate)
- [ ] Create `context_memory` table in AIDB
- [ ] Create `context_references` table
- [ ] Add indices for efficient querying
- [ ] Implement importance score calculation function

### Phase 2: Context Capture (Next)
- [ ] Hook into conversation summarization
- [ ] Capture file reads, edits, writes as context
- [ ] Capture code changes and commits
- [ ] Capture error resolutions
- [ ] Store with full metadata

### Phase 3: Lifecycle Management (Next)
- [ ] Implement lifecycle state transitions
- [ ] Create background job for state updates
- [ ] Implement decay model
- [ ] Calculate importance scores continuously

### Phase 4: Smart Compaction (Critical)
- [ ] Implement proactive trigger monitoring
- [ ] Create compaction planning algorithm
- [ ] Generate summarization candidates
- [ ] Execute compaction with preservation

### Phase 5: Recall System (Enhancement)
- [ ] Implement semantic search over archived context
- [ ] Create recall triggers (file mention, task reference)
- [ ] Build recall ranking by relevance
- [ ] Promote recalled context to active

---

## Compaction Trigger Logic

```python
def should_trigger_compaction() -> bool:
    """
    Proactive compaction trigger logic.

    Returns True if compaction should be triggered before auto-threshold.
    """
    current_tokens = get_current_token_count()
    window_limit = 200000  # Claude Code limit

    # Trigger at 75% threshold (150k tokens)
    if current_tokens > (window_limit * 0.75):
        logger.warning(f"Context at {current_tokens/1000}k tokens (75% threshold), triggering compaction")
        return True

    # Trigger if stale context ratio high
    stale_ratio = get_stale_context_ratio()
    if stale_ratio > 0.40:
        logger.info(f"Stale context ratio {stale_ratio:.1%}, triggering compaction")
        return True

    # Trigger after long session
    session_duration = get_session_duration()
    if session_duration > 4 * 3600:  # 4 hours
        logger.info(f"Session duration {session_duration/3600:.1f}h, triggering compaction")
        return True

    return False
```

---

## Preservation Rules

**Never Prune:**
1. Pinned contexts (is_pinned=True)
2. Contexts with importance_score >= 0.9
3. Error resolutions from last 24h
4. Code changes not yet committed
5. Active session contexts

**Always Summarize (not archive):**
1. Contexts with importance_score 0.5-0.8
2. Aging contexts with references
3. Task-related contexts (preserve task lineage)

**Safe to Archive:**
1. Contexts with importance_score < 0.5
2. Stale contexts (7d+) with no references
3. Purely informational reads (no decisions made)

---

## Token Budget Allocation

For 200k token window:

| Category | Tokens | Percentage |
|----------|--------|------------|
| Active Conversation | 60k | 30% |
| Fresh Context (0-1h) | 40k | 20% |
| Active Context (1-8h) | 30k | 15% |
| Aging Context (summaries) | 20k | 10% |
| System/Framework | 20k | 10% |
| Recalled Context | 20k | 10% |
| Reserve/Headroom | 10k | 5% |

---

## Success Metrics

1. **Context Relevance Score** - Average importance of retained context >0.6
2. **Recall Hit Rate** - Archived context successfully recalled when needed >80%
3. **Compaction Frequency** - Proactive compaction triggered before auto-threshold >90%
4. **Token Efficiency** - <70% window usage under normal operation
5. **Preservation Accuracy** - Critical context never auto-pruned (100%)

---

## Next Steps

1. Implement database schema in AIDB
2. Create importance scoring service
3. Implement proactive compaction trigger
4. Hook into Claude Code conversation lifecycle
5. Test with current session before triggering compaction

---

**Status:** Ready for Implementation
**Priority:** CRITICAL - Affects all future operations

