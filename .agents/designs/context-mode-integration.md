# Context-Mode Integration Design

**Created:** 2026-03-15
**Purpose:** Integrate context-mode strategies into NixOS AI harness
**Priority:** HIGH - Enhances Phase 2 & Phase 3 capabilities

---

## Executive Summary

Context-mode solves critical AI context management challenges through:
1. **Sandbox execution** (98% context reduction)
2. **Session persistence** (SQLite + FTS5)
3. **Event tracking** (file edits, git ops, tasks)
4. **Intelligent retrieval** (BM25 ranking)
5. **Progressive disclosure** (smart throttling)

These strategies directly support our **System Excellence Roadmap** goals:
- Phase 2: Real-time monitoring with context-efficient logging
- Phase 3: Agentic storage with vector DB + semantic search
- Overall: Seamless integration, no bolt-ons

---

## Integration Strategy

### Phase 2 Enhancements (Immediate)

**2.1 Deployment Event Tracking → Context-Aware Logging**
- ✅ Already implemented: Deployment tracking API (dashboard/backend/api/routes/deployments.py)
- 🔄 Enhance: Add SQLite session persistence
- 🔄 Enhance: Add FTS5 indexing for deployment logs
- 🔄 Enhance: Implement progressive disclosure for log retrieval

**2.2 Dashboard Integration → Intelligent Retrieval**
- Use BM25 ranking for deployment history search
- Smart snippet extraction for error messages
- Levenshtein distance for fuzzy search

**2.3 Monitoring Data Flows → Context-Efficient Collection**
- Sandbox metric collection (prevent raw prometheus data bloat)
- Index time-series data with FTS5
- Query with semantic matching

### Phase 3 Preparation (Foundation)

**3.1 Agentic Storage Architecture**
```
┌─────────────────────────────────────────────────┐
│ Context-Mode Layer (Session + Index)            │
│  - SQLite for events, edits, git ops            │
│  - FTS5 with BM25 for text search               │
│  - Porter stemming + trigram matching           │
└─────────────────────────────────────────────────┘
                     ↓
┌─────────────────────────────────────────────────┐
│ Vector Storage Layer (Semantic Search)          │
│  - Qdrant for embeddings                        │
│  - Deployment history vectors                   │
│  - Code snippet embeddings                      │
└─────────────────────────────────────────────────┘
                     ↓
┌─────────────────────────────────────────────────┐
│ Knowledge Graph Layer (Relationships)           │
│  - Service dependencies                         │
│  - Deployment causality                         │
│  - Error patterns                               │
└─────────────────────────────────────────────────┘
```

**3.2 Hybrid Search Strategy**
1. **Full-text search (FTS5)** for exact/fuzzy matches
2. **Vector search (Qdrant)** for semantic similarity
3. **Graph traversal** for relationship discovery
4. **Re-ranking** with BM25 + embedding scores

---

## Implementation Plan

### Batch 2.1B: Context-Aware Deployment Tracking

**Tasks:**
- [ ] Add SQLite backend to deployment tracking
- [ ] Implement FTS5 indexing for deployment logs
- [ ] Create ctx_execute wrapper for deploy commands
- [ ] Add session continuity hooks
- [ ] Implement progressive throttling for log queries

**Deliverables:**
- `lib/deploy/context-manager.sh` - Session tracking helper
- `dashboard/backend/api/services/context_store.py` - SQLite + FTS5
- Updated deployment routes with context-aware retrieval

**Benefits:**
- 98% reduction in deployment log context consumption
- Intelligent log search with typo correction
- Session recovery after context compaction
- Foundation for Phase 3 vector storage

### Batch 2.2B: MCP Context Integration

**Tasks:**
- [ ] Create context-mode MCP server wrapper
- [ ] Integrate with ai-hybrid-coordinator
- [ ] Add batch execution support for multi-service ops
- [ ] Implement sandbox execution for health checks

**Deliverables:**
- `ai-stack/mcp-servers/context-coordinator/` - Context-mode wrapper
- Updated hybrid-coordinator with batch support
- Sandbox health check execution

**Benefits:**
- Context-efficient multi-service operations
- Prevents metric bloat in AI context
- Batch health checks reduce round-trips

### Batch 2.3B: Intelligent Dashboard Queries

**Tasks:**
- [ ] Add FTS5 search to dashboard API
- [ ] Implement BM25 ranking for deployments
- [ ] Add smart snippet extraction
- [ ] Progressive disclosure UI component

**Deliverables:**
- Updated dashboard with intelligent search
- Real-time query performance
- Context-aware result limiting

**Benefits:**
- Fast, relevant deployment history search
- Reduced frontend data transfer
- Better user experience

---

## Technical Architecture

### Context Store Schema (SQLite + FTS5)

```sql
-- Events table
CREATE TABLE IF NOT EXISTS deployment_events (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    deployment_id TEXT NOT NULL,
    event_type TEXT NOT NULL,
    timestamp DATETIME DEFAULT CURRENT_TIMESTAMP,
    message TEXT NOT NULL,
    metadata JSON,
    progress INTEGER,
    user TEXT
);

-- FTS5 index for full-text search
CREATE VIRTUAL TABLE IF NOT EXISTS deployment_events_fts USING fts5(
    message,
    metadata,
    content='deployment_events',
    content_rowid='id',
    tokenize='porter'
);

-- Triggers to keep FTS5 in sync
CREATE TRIGGER deployment_events_ai AFTER INSERT ON deployment_events BEGIN
    INSERT INTO deployment_events_fts(rowid, message, metadata)
    VALUES (new.id, new.message, new.metadata);
END;

-- Git operations tracking
CREATE TABLE IF NOT EXISTS git_operations (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    operation TEXT NOT NULL,
    branch TEXT,
    commit_hash TEXT,
    timestamp DATETIME DEFAULT CURRENT_TIMESTAMP,
    files_changed TEXT
);

-- File edits tracking
CREATE TABLE IF NOT EXISTS file_edits (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    file_path TEXT NOT NULL,
    operation TEXT NOT NULL,
    timestamp DATETIME DEFAULT CURRENT_TIMESTAMP,
    size_before INTEGER,
    size_after INTEGER
);
```

### Context Manager Helper

```bash
# lib/deploy/context-manager.sh

# Track deployment event with context awareness
track_event() {
    local event_type="$1"
    local message="$2"
    local metadata="${3:-{}}"

    # Store in SQLite
    sqlite3 "${CONTEXT_DB}" <<EOF
INSERT INTO deployment_events (deployment_id, event_type, message, metadata)
VALUES ('${DEPLOYMENT_ID}', '${event_type}', '${message}', '${metadata}');
EOF

    # Also send to dashboard if enabled
    if [[ "${DASHBOARD_ENABLED}" == "true" ]]; then
        dashboard_notify_progress "${DEPLOYMENT_PROGRESS}" "${message}"
    fi
}

# Search deployment history with FTS5
search_deployments() {
    local query="$1"
    local limit="${2:-10}"

    sqlite3 "${CONTEXT_DB}" <<EOF
SELECT
    de.deployment_id,
    de.message,
    de.timestamp,
    bm25(deployment_events_fts) as rank
FROM deployment_events de
JOIN deployment_events_fts ON de.id = deployment_events_fts.rowid
WHERE deployment_events_fts MATCH '${query}'
ORDER BY rank
LIMIT ${limit};
EOF
}
```

### MCP Context Wrapper

```python
# ai-stack/mcp-servers/context-coordinator/server.py

from mcp import Server
import sqlite3
import subprocess

class ContextAwareMCPServer(Server):
    def __init__(self):
        super().__init__()
        self.db = sqlite3.connect("context.db")
        self.setup_fts5()

    @server.tool()
    async def ctx_execute_deployment(self, command: str) -> str:
        """Execute deployment command in sandbox, only return summary"""
        result = subprocess.run(
            command,
            shell=True,
            capture_output=True,
            text=True,
            timeout=300
        )

        # Store full output in context DB
        self.store_output(command, result.stdout, result.stderr)

        # Return only summary (context-efficient)
        return {
            "exit_code": result.returncode,
            "summary": self.summarize_output(result.stdout),
            "errors": self.extract_errors(result.stderr),
            "context_saved": True
        }

    def summarize_output(self, output: str) -> str:
        """Intelligent summarization (98% reduction)"""
        lines = output.split('\n')
        important = [l for l in lines if any(k in l.lower() for k in
                    ['error', 'fail', 'success', 'complete'])]
        return '\n'.join(important[:10])
```

---

## Integration with Existing Systems

### Deploy CLI Enhancement

**Before (Context-Bloat):**
```bash
./deploy system
# Outputs 50KB of logs to terminal
# All logs enter AI context window
# 30 minutes → 40% context consumed
```

**After (Context-Efficient):**
```bash
./deploy system
# Outputs summary only (5KB)
# Full logs stored in SQLite + FTS5
# AI queries specific logs as needed
# Context consumption: 2-3%
```

### Dashboard API Enhancement

**Before:**
```python
# Returns all deployment logs (315 KB)
@router.get("/deployments/{id}/logs")
async def get_logs(deployment_id: str):
    deployment = get_deployment(deployment_id)
    return {"logs": deployment.logs}  # All 315 KB
```

**After:**
```python
# Returns intelligent excerpts (5.4 KB)
@router.get("/deployments/{id}/logs")
async def get_logs(deployment_id: str, query: str = ""):
    if query:
        # BM25-ranked search results
        results = fts5_search(deployment_id, query, limit=20)
        return {"logs": results, "context_saved": True}
    else:
        # Smart summary only
        return {"summary": summarize_logs(deployment_id)}
```

---

## Success Metrics

| Metric | Before | After | Target |
|--------|--------|-------|--------|
| Deployment log size | 315 KB | 5.4 KB | 98% reduction |
| Context window usage | 40% (30 min) | 2-3% | 95% improvement |
| Search relevance | N/A | BM25-ranked | >90% accuracy |
| Session recovery | Manual | Automatic | 100% |
| Query response time | N/A | <100ms | <200ms |

---

## Phase Alignment

| Phase | Context-Mode Integration |
|-------|-------------------------|
| **Phase 1** ✅ | Foundation laid with deployment tracking |
| **Phase 2** ⏳ | SQLite + FTS5 for deployment logs |
| **Phase 3** 📋 | Hybrid search (FTS5 + Qdrant vectors) |
| **Phase 4** 📋 | End-to-end context-aware workflows |
| **Phase 5** 📋 | Performance optimization with batching |
| **Phase 6** 📋 | Full context-mode MCP server |

---

## Next Steps

**Immediate (This Session):**
1. Create SQLite context store for deployments
2. Implement FTS5 indexing
3. Add search endpoint to dashboard API
4. Test context-efficient deployment tracking

**Short-term (Phase 2 completion):**
1. MCP context-coordinator wrapper
2. Batch execution support
3. Dashboard UI with intelligent search
4. Session continuity hooks

**Long-term (Phase 3):**
1. Vector embeddings integration
2. Hybrid search (FTS5 + Qdrant)
3. Knowledge graph for relationships
4. Full context-mode MCP server

---

## References

- Context-Mode GitHub: https://github.com/mksglu/context-mode
- System Excellence Roadmap: .agents/plans/SYSTEM-EXCELLENCE-ROADMAP-2026-Q2.md
- Deployment Tracking API: dashboard/backend/api/routes/deployments.py
- Phase 3 Agentic Storage: Planned for Weeks 5-6
