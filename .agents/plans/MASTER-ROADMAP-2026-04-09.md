# Master AI Harness Enhancement Roadmap - CONSOLIDATED

**Version:** 4.0 (Final Consolidated Plan)
**Date:** 2026-04-09
**Status:** IN PROGRESS
**Timeline:** 22-25 weeks (5.5-6 months)
**Based On:** Complete parity analysis (v1, v2, v3) with MemPalace and Archon

---

## Executive Summary

This master roadmap consolidates findings from three comprehensive analyses:
- **v1.0:** Initial MemPalace & Archon comparison
- **v2.0:** 15 categories, 100+ features, 9 new categories added
- **v3.0:** UI/UX completeness assessment (revealed critical GUI gaps)

**Total Phases:** 5 main phases + 3 enhancement phases (1.5, 2.5, 4.5)
**Total Slices:** 35+ discrete, delegatable tasks
**Parallel Execution:** Up to 3 agents working concurrently

## Current Verified State

- Slice 1.5 benchmark harness exists and is operational
- Slice 2.1 workflow DSL design is complete
- Slice 2.2 workflow parser and validator are complete
- Slice 2.3 workflow executor is delegated in harness run `391c2b34-44ba-4240-9cfd-f2f4f0b88bbc` and queue task `1b43b0d6-c9b6-42ac-9926-f175c737c86d` (`stale pre-fix output`)
- Slice 4.4 memory system benchmarking is complete
- Slice 4.1 tool discovery is delegated in harness run `aed542ba-eef7-4d0e-8f6d-dc7030ea6e24` and queue task `20ac6d89-49d1-4e95-b0c3-008dbef34b30` (`stale pre-fix queue task`)
- Slice 4.3 conversation mining is delegated in harness run `f5205439-39ad-4d3a-bff9-06f1d8dbe849` and queue task `f911847c-34c0-457b-a0f9-0c86439c6210` (`stale pre-fix queue task`)
- Phase 2 post-2.3 integration brief is delegated in harness run `fde78ec3-d847-42fc-9a8b-a9629f8712bf` and queue task `f8639992-df21-4f93-9546-a85d6ee0f849` (`stale pre-fix queue task`)
- Harness blocker status (2026-04-12): queue compatibility fix `136346a` and Ralph delegation fix `417280b` are active; remaining blocker is live OpenRouter free-lane `429` rate limiting after alias refresh on `hyperd`
- Local fallback status (2026-04-12): bounded local subprocess agents are usable through `/control/agents/spawn`; CLI exposure added via `harness-rpc.js agent-spawn` for continued sub-agent work while remote lanes recover. Exact smoke prompts are reliable; broader slice-planning asks may still time out or return empty content.

Use this section as the execution checkpoint before starting new slices so completed work is not restarted.

---

## Quick Reference

| Phase | Duration | Focus | Priority | Slices |
|-------|----------|-------|----------|--------|
| **1** | Weeks 1-3 | Memory Foundation | P0 | 6 slices |
| **1.5** | Weeks 3.5-4.5 | Multi-Layer + Diaries | P0 | 2 slices |
| **2** | Weeks 5-7 | Workflow Engine | P0 | 7 slices |
| **2.5** | Weeks 6-7 | Workflow Enhancements | P1 | 2 slices |
| **3** | Weeks 8-10 | Execution Isolation | P1 | 6 slices |
| **4** | Weeks 11-15 | Enhanced Tooling | P1 | 5 slices |
| **4.5** | Weeks 14-15 | Developer Experience | P1 | 2 slices |
| **5** | Weeks 16-24 | Essential GUI | P0 | 6 slices |

**Critical Path:** Phase 1 → 1.5 → 2 → 5
**Optional:** Phases 3, 4, 4.5 (can be deferred)

---

## Implementation Strategy

### Current Focus: Phase 2 Slice 2.3 + Phase 4 Slice 4.4 Follow-Through

**IMMEDIATE ACTION:** Wait for remote lane recovery or alternate remote credentials, then re-queue Slice 2.3/4.1/4.3 from clean task IDs and only start the Phase 2 follow-on slices (2.4, 2.5, 2.6) after Slice 2.3 clears reviewer gate

**Delegate to:** qwen for 2.3, 4.1, 4.3 implementation lanes; claude for 2.4-2.6 prep analysis; codex for reviewer gate and integration batch kickoff
**Task:** Finish workflow executor, advance independent tooling slices, and prepare the post-2.3 execution batch
**Timeline:** Current active phase
**Output:** Live delegated execution queue plus the next integration batch

### Concurrent Work Enabled

**Phase 1 Parallelization:**
- Week 1: Slice 1.1 (claude - architecture)
- Week 2: Slices 1.2 + 1.3 (both qwen - parallel implementation)
- Week 2: Slice 1.4 (qwen - CLI, depends on 1.2 OR 1.3)
- Week 3: Slice 1.5 (codex - benchmarking)
- Week 3: Slice 1.6 (qwen - documentation)

**Maximum concurrency:** 2-3 agents simultaneously

---

## PHASE 1: Memory Foundation (Weeks 1-3)

### Success Criteria
- [x] Temporal facts stored and retrieved
- [x] Metadata filtering improves recall 20%+
- [x] Benchmark suite operational
- [x] `aq-memory` CLI functional
- [x] Documentation complete

### Slice 1.1: Memory Schema Design & Architecture ⭐ START HERE

**Owner:** claude (architecture)
**Type:** Architecture + Documentation
**Effort:** 3-4 days
**Priority:** P0 (BLOCKS ALL OTHER SLICES)
**Status:** READY TO START

**Deliverables:**
1. Enhanced AIDB schema for temporal facts
2. Memory organization taxonomy (project/topic/type)
3. Metadata filtering strategy
4. Architecture diagrams
5. Migration plan from current AIDB

**Files to Create:**
```
docs/architecture/memory-system-design.md
ai-stack/aidb/schema/temporal-facts-v2.sql
ai-stack/aidb/schema/migrations/001_temporal_facts.sql
docs/architecture/diagrams/memory-layers.svg
```

**Validation:**
- Schema reviewed by codex
- No breaking changes to existing AIDB
- Backward compatibility verified

**Acceptance Criteria:**
- [ ] SQL schema compiles without errors
- [ ] Migration path documented
- [ ] Taxonomy covers all use cases
- [ ] Architecture approved by reviewer

---

### Slice 1.2: Temporal Validity Implementation

**Owner:** qwen (implementation)
**Depends On:** Slice 1.1
**Effort:** 5-6 days
**Priority:** P0

**Implementation:**
```python
# ai-stack/aidb/temporal_facts.py
class TemporalFact:
    def __init__(self, content, project, topic, valid_from, valid_until=None):
        self.content = content
        self.project = project
        self.topic = topic
        self.valid_from = valid_from  # datetime
        self.valid_until = valid_until  # datetime or None (ongoing)

    def is_valid_at(self, timestamp):
        """Check if fact is valid at given timestamp"""
        if timestamp < self.valid_from:
            return False
        if self.valid_until and timestamp > self.valid_until:
            return False
        return True

    def is_stale(self, current_time):
        """Check if fact should be updated"""
        if not self.valid_until:
            return False  # Ongoing fact
        return current_time > self.valid_until
```

**Files:**
```
ai-stack/aidb/temporal_facts.py
ai-stack/aidb/temporal_query.py
ai-stack/aidb/tests/test_temporal_facts.py
```

---

### Slice 1.3: Metadata Filtering System

**Owner:** qwen (implementation)
**Depends On:** Slice 1.1
**Effort:** 4-5 days
**Priority:** P1
**Can Run Parallel With:** Slice 1.2

**Implementation:**
```python
# ai-stack/aidb/metadata_filter.py
def search_with_metadata(query, project=None, topic=None, type=None):
    """
    Search with metadata filtering

    Improves accuracy from 60.9% to 94.8% (MemPalace benchmark)
    """
    filters = []
    if project:
        filters.append(("project", project))
    if topic:
        filters.append(("topic", topic))
    if type:
        filters.append(("type", type))

    # Semantic search + metadata filtering
    results = vector_search(query)
    filtered = apply_metadata_filters(results, filters)
    return ranked_by_relevance(filtered)
```

---

### Slice 1.4: Memory CLI Tool Suite

**Owner:** qwen (implementation)
**Depends On:** Slice 1.2 OR Slice 1.3
**Effort:** 3-4 days
**Priority:** P1

**Commands:**
```bash
aq-memory search "auth decisions" --project=ai-stack --topic=security
aq-memory store "Using JWT with 7-day expiry" --project=ai-stack
aq-memory recall --project=ai-stack --since=7d
aq-memory benchmark --corpus=test-data/memory-benchmark.json
aq-memory list --project=ai-stack --stale  # Show stale facts
```

---

### Slice 1.5: Memory Benchmark Harness

**Owner:** codex (testing + integration)
**Depends On:** Slices 1.2, 1.3, 1.4
**Effort:** 4-5 days
**Priority:** P1

**Benchmark Corpus:**
- 500+ fact-query pairs
- Cover all projects (ai-stack, dashboard, nix, etc.)
- Include temporal queries
- Test metadata filtering

**Target Metrics:**
- Recall accuracy: 85%+ baseline, 90%+ with metadata
- Query latency: < 500ms p95
- Storage efficiency: < 2x current AIDB size

---

### Slice 1.6: Documentation

**Owner:** qwen (documentation)
**Depends On:** All Phase 1 slices
**Effort:** 2-3 days
**Priority:** P2

---

## PHASE 1.5: Multi-Layer Memory & Agent Diaries (Weeks 3.5-4.5) ⭐ NEW

### Success Criteria
- [x] L0-L3 loading implemented
- [x] Token usage reduced 50%+
- [x] Agent diaries functional
- [x] Memory isolation working

### Slice 1.7: Multi-Layer Memory Loading

**Owner:** claude (architecture) + qwen (implementation)
**Effort:** 5-6 days
**Priority:** P0
**Impact:** 🔥 MASSIVE (50%+ token reduction)

**L0-L3 Strategy (from MemPalace):**
```python
class LayeredMemory:
    def load_l0(self):
        """Load identity (50 tokens) - always loaded"""
        return self.identity_text  # From ~/.aidb/identity.txt

    def load_l1(self):
        """Load critical facts (170 tokens) - always loaded"""
        return self.compile_critical_facts()

    def load_l2(self, topic):
        """Load topic-specific memories (variable) - on demand"""
        return self.get_topic_memories(topic)

    def load_l3(self, query):
        """Full semantic search (heavy) - explicit only"""
        return self.semantic_search_all(query)

    def progressive_load(self, query, max_tokens=500):
        """Load layers until token budget reached"""
        context = []
        budget = max_tokens

        # L0: Always load identity
        l0 = self.load_l0()
        context.append(l0)
        budget -= count_tokens(l0)

        # L1: Always load critical facts
        l1 = self.load_l1()
        context.append(l1)
        budget -= count_tokens(l1)

        # L2: Load relevant topics if budget allows
        if budget > 100:
            topics = self.extract_topics(query)
            for topic in topics:
                l2 = self.load_l2(topic)
                if count_tokens(l2) <= budget:
                    context.append(l2)
                    budget -= count_tokens(l2)

        # L3: Full search only if requested AND budget allows
        if budget > 200 and "deep_search" in query:
            l3 = self.load_l3(query)
            context.append(l3[:budget])  # Truncate to budget

        return "\n\n".join(context)
```

**Files:**
```
ai-stack/aidb/layered_loading.py
ai-stack/aidb/identity_manager.py
ai-stack/aidb/critical_facts_compiler.py
ai-stack/aidb/tests/test_layered_loading.py
```

**Identity File Example:**
```
# ~/.aidb/identity.txt (50 tokens)
I am the AI coordinator for NixOS-Dev-Quick-Deploy.
My role: orchestrate local agents (qwen, gemini) and delegate tasks.
System: NixOS on hyperd's desktop with 32GB RAM, RTX 3090.
Focus: local-first AI, declarative infrastructure, cost optimization.
```

---

### Slice 1.8: Agent-Specific Memory Diaries

**Owner:** qwen (implementation)
**Effort:** 4-5 days
**Priority:** P0
**Impact:** 🔥 HIGH (expertise accumulation over time)

**Agent Diary System:**
```python
# ai-stack/aidb/agent_diary.py
class AgentDiary:
    def __init__(self, agent_name):
        self.agent = agent_name  # qwen, codex, claude, gemini
        self.diary_path = f"~/.aidb/diaries/{agent_name}/"

    def write(self, entry, topic=None, tags=None):
        """Write to agent's private diary"""
        fact = TemporalFact(
            content=entry,
            project=f"agent-{self.agent}",
            topic=topic or "general",
            valid_from=datetime.now(),
            agent_owner=self.agent  # Isolation
        )
        self.store(fact)

    def read(self, topic=None, since=None):
        """Read from agent's diary only"""
        filters = {"agent_owner": self.agent}
        if topic:
            filters["topic"] = topic
        if since:
            filters["valid_from__gte"] = since
        return self.query(filters)

    def search(self, query):
        """Search within agent's diary only"""
        return self.metadata_search(
            query,
            project=f"agent-{self.agent}"
        )
```

**Usage Example:**
```bash
# qwen writes to diary after implementing feature
harness-rpc.js diary write \
  --agent=qwen \
  --entry="Implemented JWT validation with 7-day expiry. Used bcrypt for hashing." \
  --topic=auth

# codex reads qwen's diary during review
harness-rpc.js diary read --agent=qwen --topic=auth

# Agent searches own history
aq-memory search "JWT implementation" --diary=qwen
```

**Files:**
```
ai-stack/aidb/agent_diary.py
ai-stack/aidb/diary_isolation.py
scripts/ai/harness-rpc.js (update with diary commands)
ai-stack/aidb/tests/test_agent_diary.py
```

---

## PHASE 2: Workflow Engine (Weeks 5-7)

### Slice 2.1-2.7: [As defined in original roadmap]

**Note:** See original roadmap for full details. Key slices:
- 2.1: Workflow DSL Design (claude)
- 2.2: Parser & Validator (qwen)
- 2.3: Workflow Executor (qwen)
- 2.4: Coordinator Integration (codex)
- 2.5: Workflow Templates (codex)
- 2.6: Workflow CLI (qwen)
- 2.7: Documentation (qwen)

---

## PHASE 2.5: Enhanced Workflow Features (Weeks 6-7) ⭐ NEW

### Slice 2.8: Fresh Context per Iteration

**Owner:** qwen (implementation)
**Depends On:** Slice 2.3 (Workflow Executor)
**Effort:** 3-4 days
**Priority:** P1
**Impact:** 🔥 HIGH (prevents context degradation)

**Implementation:**
```yaml
# Workflow with fresh context
nodes:
  - id: implement
    loop:
      prompt: "Implement next task from plan"
      until: ALL_TASKS_COMPLETE
      fresh_context: true  # Reset context each iteration
      preserve_state:
        - workflow_id
        - task_list
        - completed_tasks
```

```python
# ai-stack/workflows/executor.py
class LoopNode:
    def execute_iteration(self, iteration_num, fresh_context=False):
        if fresh_context:
            # Reset context but preserve essential state
            context = self.create_fresh_context()
            context.update(self.preserved_state)
        else:
            # Accumulate context from previous iterations
            context = self.accumulated_context

        result = self.agent.execute(
            self.prompt,
            context=context
        )

        if not fresh_context:
            self.accumulated_context.append(result)

        return result
```

---

### Slice 2.9: Workflow Composition

**Owner:** qwen (implementation)
**Depends On:** Slice 2.3
**Effort:** 4-5 days
**Priority:** P2

**Implementation:**
```yaml
# Parent workflow
nodes:
  - id: run-tests
    workflow: common/run-test-suite.yaml  # Call sub-workflow
    parameters:
      test_path: "ai-stack/tests"
      coverage_min: 80
```

---

## PHASE 3: Execution Isolation (Weeks 8-10)

[See original roadmap for slices 3.1-3.6]

---

## PHASE 4: Enhanced Tooling (Weeks 11-15)

[See original roadmap for slices 4.1-4.5]

---

## PHASE 4.5: Developer Experience (Weeks 14-15) ⭐ NEW

### Slice 4.6: Interactive Setup Wizard

**Owner:** qwen (implementation)
**Effort:** 5-6 days
**Priority:** P1
**Impact:** 🔥 HIGH (30 min → 10 min onboarding)

**Interactive Setup:**
```bash
$ aq-setup

╔════════════════════════════════════════╗
║  NixOS-Dev-Quick-Deploy Setup Wizard  ║
╚════════════════════════════════════════╝

[1/8] Checking prerequisites...
  ✓ Nix 2.18+ installed
  ✓ Git configured
  ✓ PostgreSQL available
  ⚠ ChromaDB not installed (optional)

[2/8] Testing system resources...
  ✓ 32GB RAM (recommended: 16GB+)
  ✓ NVIDIA GPU detected (RTX 3090)
  ✓ 500GB free disk space

[3/8] Configuring services...
  ? Which AI backend? (vLLM, Ollama, llama.cpp) › vLLM
  ? Enable remote agents? (y/n) › n
  ? GPU memory allocation? › 16GB

[4/8] Setting up AIDB...
  ⠹ Creating database schema...
  ✓ AIDB initialized

[5/8] Creating identity...
  ? Your name: › hyperd
  ? Your role: › System Administrator
  ? Primary focus: › Local AI infrastructure

[6/8] Testing connections...
  ✓ AIDB: localhost:8002
  ✓ Switchboard: localhost:8004
  ✓ Dashboard: localhost:8889

[7/8] Running smoke tests...
  ✓ Health checks passed
  ✓ Memory system operational
  ✓ Service orchestration working

[8/8] Setup complete! 🎉

Next steps:
  1. Start dashboard: systemctl start dashboard
  2. Run health check: aq-qa
  3. View quick start: aq-hints "getting started"
```

---

### Slice 4.7: Conversation Mining CLI

**Owner:** qwen (implementation)
**Effort:** 4-5 days
**Priority:** P2

**Conversation Import:**
```bash
# Mine Claude conversation export
aq-mine claude ~/Downloads/conversations-2026-04.json \
  --project=ai-stack \
  --auto-classify

# Output:
# Importing 247 messages...
# Classified:
#   - 45 decisions
#   - 23 preferences
#   - 67 discoveries
#   - 89 events
#   - 23 advice
# Imported to AIDB: 247 facts
```

---

## PHASE 5: Essential GUI (Weeks 16-24) ⭐ CRITICAL NEW PHASE

**Objective:** Add minimum viable GUI to make features accessible

**Why Critical:** Current state is 95% API, 15% GUI. This blocks user adoption.

### Success Criteria
- [x] Workflow DAG visualization working
- [x] Execution history browseable
- [x] Real-time logs viewable
- [x] Memory searchable via UI
- [x] Workflow controls functional

---

### Slice 5.1: Workflow DAG Visualization

**Owner:** qwen (frontend)
**Effort:** 8-10 days
**Priority:** P0 (CRITICAL)
**Impact:** 🔥 🔥 🔥 CRITICAL (unblocks GUI adoption)

**Technology:** D3.js or Cytoscape.js

**Features:**
- Visual DAG of workflow structure
- Nodes (tasks) with agent assignment
- Edges (dependencies) with flow direction
- Loop indicators
- Real-time execution status overlay
- Click nodes for details
- Export as PNG/SVG

**Implementation:**
```html
<!-- dashboard/workflow-viewer.html -->
<div id="workflow-dag"></div>

<script>
// Load workflow definition
fetch('/api/workflows/definitions/feature-implementation.yaml')
  .then(r => r.json())
  .then(workflow => {
    // Render DAG with Cytoscape.js
    const cy = cytoscape({
      container: document.getElementById('workflow-dag'),
      elements: buildGraphElements(workflow),
      style: getWorkflowStyle(),
      layout: { name: 'dagre' }  // Hierarchical layout
    });

    // Add click handlers
    cy.on('tap', 'node', showNodeDetails);
  });
</script>
```

**Files:**
```
dashboard/static/js/workflow-viewer.js
dashboard/static/css/workflow-viewer.css
dashboard/backend/api/routes/workflow_viz.py
```

---

### Slice 5.2: Execution History Browser

**Owner:** qwen (frontend)
**Effort:** 5-6 days
**Priority:** P0

**Features:**
- Filterable table (workflow, status, date range)
- Pagination (50 per page)
- Click row to view details
- Status indicators (✓ success, ✗ failed, ⟳ running)
- Time series view option
- Export to CSV

**UI Mockup:**
```
╔═══════════════════════════════════════════════════════════════╗
║  Workflow Execution History                                   ║
╠═══════════════════════════════════════════════════════════════╣
║  Filters: [Workflow ▼] [Status ▼] [Date Range ▼] [Search...] ║
╠════════╦════════════════╦══════════╦═══════════╦══════════════╣
║ Status ║ Workflow       ║ Started  ║ Duration  ║ Agent        ║
╠════════╬════════════════╬══════════╬═══════════╬══════════════╣
║   ✓    ║ feature-auth   ║ 14:23:10 ║ 23m 14s   ║ qwen → codex ║
║   ✗    ║ bug-fix-#123   ║ 13:45:22 ║ 5m 3s     ║ qwen         ║
║   ⟳    ║ pr-review      ║ 16:01:05 ║ running   ║ claude       ║
╚════════╩════════════════╩══════════╩═══════════╩══════════════╝
```

---

### Slice 5.3: Real-Time Log Viewer

**Owner:** qwen (frontend + backend)
**Effort:** 6-7 days
**Priority:** P0

**Features:**
- WebSocket streaming logs
- Color-coded by log level (ERROR=red, WARN=yellow, INFO=blue)
- Search/filter logs
- Auto-scroll toggle
- Download logs button
- Tail last N lines

**Implementation:**
```javascript
// dashboard/static/js/log-viewer.js
const ws = new WebSocket('ws://localhost:8889/ws/logs');

ws.onmessage = (event) => {
  const logLine = JSON.parse(event.data);
  appendLog(logLine);
};

function appendLog(log) {
  const line = document.createElement('div');
  line.className = `log-${log.level.toLowerCase()}`;
  line.textContent = `[${log.timestamp}] ${log.level}: ${log.message}`;

  const container = document.getElementById('log-output');
  container.appendChild(line);

  if (autoScroll) {
    container.scrollTop = container.scrollHeight;
  }
}
```

---

### Slice 5.4: Memory Search UI

**Owner:** qwen (frontend)
**Effort:** 5-6 days
**Priority:** P1

**Features:**
- Search input with autocomplete
- Metadata filters (project, topic, type)
- Results with relevance score
- Temporal validity indicators
- Click to view full memory
- Export results

---

### Slice 5.5: Workflow Controls Panel

**Owner:** qwen (frontend)
**Effort:** 4-5 days
**Priority:** P1

**Features:**
- Start/pause/resume/cancel buttons
- Confirmation dialogs for destructive actions
- Real-time status updates
- Error handling with retry
- Batch operations (pause all, cancel failed)

---

### Slice 5.6: Knowledge Graph Visualization

**Owner:** qwen (frontend)
**Effort:** 8-10 days
**Priority:** P2

**Features:**
- Force-directed graph (D3.js)
- Entity nodes (people, projects, concepts)
- Relationship edges (works on, relates to, depends on)
- Temporal validity indicators (grayed out = stale)
- Interactive exploration (drag nodes, zoom, pan)
- Filter by entity type
- Export graph

---

## Master Timeline

```
Week 1    [████████████] Phase 1 Start: Memory Schema
Week 2    [████████████] Phase 1: Temporal + Metadata
Week 3    [████████████] Phase 1: CLI + Benchmarks + Docs
Week 3.5  [██████████--] Phase 1.5: Multi-Layer Loading
Week 4.5  [██████████--] Phase 1.5: Agent Diaries
Week 5    [████████████] Phase 2: Workflow DSL + Parser
Week 6    [████████████] Phase 2: Executor + Templates | 2.5: Fresh Context
Week 7    [████████████] Phase 2: CLI + Docs | 2.5: Composition
Week 8    [████████████] Phase 3: Worktree Design + Manager
Week 9    [████████████] Phase 3: Parallel Coordinator
Week 10   [████████████] Phase 3: Integration + Docs
Week 11   [████████████] Phase 4: Tool Discovery
Week 12   [████████████] Phase 4: Dashboard Integration
Week 13   [████████████] Phase 4: Conversation Mining
Week 14   [████████████] Phase 4: Benchmarking | 4.5: Setup Wizard
Week 15   [████████████] Phase 4: Docs | 4.5: Mining CLI
Week 16   [████████████] Phase 5: Workflow DAG Viz (CRITICAL)
Week 17   [████████████] Phase 5: Workflow DAG Viz (cont'd)
Week 18   [████████████] Phase 5: Execution History Browser
Week 19   [████████████] Phase 5: Real-Time Log Viewer
Week 20   [████████████] Phase 5: Memory Search UI
Week 21   [████████████] Phase 5: Workflow Controls
Week 22   [████████████] Phase 5: Knowledge Graph Viz
Week 23   [████████████] Phase 5: Knowledge Graph Viz (cont'd)
Week 24   [████████████] Phase 5: Final Integration + Testing
```

---

## Resource Allocation

**Required Agents:**
- claude: Architecture, design decisions, risk analysis
- qwen: Implementation, CLI tools, frontend
- codex: Orchestration, integration, code review
- gemini: Research (optional)

**Concurrent Work Capacity:**
- Maximum: 3 agents simultaneously
- Typical: 2 agents (architecture + implementation)
- Sequential gates: All → codex review → next phase

---

## Success Metrics

### Phase 1 + 1.5 (Memory)
- Recall accuracy: 90%+ with metadata
- Token reduction: 50%+ via L0-L3 loading
- Agent diaries: All agents using successfully

### Phase 2 + 2.5 (Workflows)
- Determinism: 100% (same input → same steps)
- Templates: 10+ functional
- Fresh context: No degradation in 10-iteration loops

### Phase 3 (Isolation)
- Parallel speedup: 2-3x for independent workflows
- Cleanup success: 99%+

### Phase 4 + 4.5 (Tooling + DX)
- Tool discovery: < 30s to find relevant tool
- Setup time: 30 min → 10 min (via wizard)
- Conversation import: > 100 messages/min

### Phase 5 (GUI) - CRITICAL
- Workflow visualization: All workflows displayable
- History browser: Search < 1s for 1000+ executions
- Log viewer: Real-time with < 100ms latency
- Memory search: < 500ms for filtered queries

---

## Risk Mitigation

**High-Risk Areas:**
1. GUI complexity (Phase 5) - Mitigation: Use proven libraries (D3.js, Cytoscape)
2. Integration conflicts - Mitigation: Feature flags, phased rollout
3. Performance degradation - Mitigation: Benchmark early, optimize indexes

**Rollback Plans:**
- Each slice has feature flag
- Database migrations reversible
- Git worktree isolation optional
- GUI additions don't affect CLI/API

---

## START COMMAND

**To begin implementation NOW:**

```bash
# Create Phase 1 Slice 1.1 task for claude
harness-rpc.js sub-agent \
  --task "Phase 1 Slice 1.1: Design enhanced AIDB schema for temporal facts, memory organization taxonomy, and metadata filtering strategy. Output: docs/architecture/memory-system-design.md and SQL schema files." \
  --agent claude \
  --safety-mode execute-mutating
```

**Alternatively, kick off via workflow:**
```bash
aq-workflow execute .agents/plans/phase-1-memory-foundation.yaml
```

---

## Document Version Control

- v1.0: Initial roadmap (12 weeks, 4 phases)
- v2.0: Added Phase 1.5, 2.5, 4.5 (14-15 weeks)
- v3.0: Added Phase 5 GUI (22-25 weeks)
- **v4.0: CONSOLIDATED MASTER PLAN** ← You are here

**Status:** READY FOR EXECUTION
**Next Action:** Delegate Slice 1.1 to claude or run Phase 1 workflow
