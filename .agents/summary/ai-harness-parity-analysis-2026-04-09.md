# AI Harness Parity Analysis and Best Practices Review

**Date:** 2026-04-09
**Purpose:** Comparative analysis of NixOS-Dev-Quick-Deploy AI harness vs. MemPalace and Archon
**Status:** Active Analysis
**Reviewers:** System Architect, AI Stack Lead

---

## Executive Summary

This document provides a comprehensive comparison of three AI harness/orchestration systems:
1. **MemPalace** - Memory-centric AI system with 96.6% recall benchmark
2. **Archon** - Deterministic workflow engine for AI coding agents
3. **NixOS-Dev-Quick-Deploy** (Ours) - NixOS-first AI stack harness with hybrid orchestration

**Key Finding:** Each system excels in different domains. MemPalace leads in memory/recall, Archon in workflow determinism, and our system in declarative infrastructure and local-first orchestration.

**Recommendation:** Incorporate selective features from both systems to enhance our capabilities while maintaining our declarative-first and local-first philosophy.

---

## Comparison Matrix

### Architecture & Philosophy

| Aspect | MemPalace | Archon | NixOS-Dev-Quick-Deploy (Ours) |
|--------|-----------|--------|--------------------------------|
| **Core Philosophy** | Memory-first, verbatim storage | Workflow determinism & repeatability | Declarative infra + local-first AI |
| **Primary Language** | Python 3.9+ | TypeScript (Bun runtime) | Python + Bash + Nix |
| **Architecture Pattern** | Memory palace metaphor | DAG-based workflow engine | Hybrid coordinator + delegation |
| **Configuration Style** | MCP tools + palace structure | YAML workflow definitions | Nix modules + MCP bridge |
| **Isolation Model** | None (shared context) | Git worktrees per execution | Subprocess agents + safety modes |

### Memory & Context Management

| Feature | MemPalace | Archon | NixOS-Dev-Quick-Deploy |
|---------|-----------|--------|------------------------|
| **Memory Storage** | ✅ ChromaDB vector + SQLite | ❌ No persistent memory | ⚠️ AIDB knowledge base (partial) |
| **Recall Accuracy** | ✅ 96.6% (LongMemEval benchmark) | ❌ No memory system | ⚠️ Not benchmarked |
| **Temporal Validity** | ✅ Time-windowed facts | ❌ Not applicable | ❌ Not implemented |
| **Conversation Mining** | ✅ Claude, ChatGPT, Slack | ❌ Not applicable | ⚠️ Session summaries only |
| **Metadata Filtering** | ✅ Wing/room/hall (94.8% accuracy) | ❌ Not applicable | ⚠️ Basic category/project filters |
| **Knowledge Graph** | ✅ Temporal graph with contradictions | ❌ Not applicable | ❌ Not implemented |
| **Verbatim Storage** | ✅ Complete history, no summarization | ❌ Not applicable | ⚠️ Partial (session logs) |

### Workflow & Orchestration

| Feature | MemPalace | Archon | NixOS-Dev-Quick-Deploy |
|---------|-----------|--------|------------------------|
| **Workflow Definition** | ❌ No workflow system | ✅ YAML DAG workflows | ⚠️ Hybrid coordinator + hints |
| **Deterministic Execution** | ❌ Not applicable | ✅ Guaranteed repeatability | ⚠️ Role-based routing (semi-deterministic) |
| **Loop Constructs** | ❌ Not applicable | ✅ Until conditions + fresh context | ⚠️ Manual iteration |
| **Parallel Execution** | ❌ Not applicable | ✅ Git worktree isolation | ✅ Subprocess agent spawning |
| **Interactive Gates** | ❌ Not applicable | ✅ Human approval checkpoints | ⚠️ Manual coordination |
| **Workflow Library** | ❌ Not applicable | ✅ 17 pre-built templates | ⚠️ Skill-based patterns |
| **Multi-Agent Delegation** | ⚠️ Agent discovery via MCP | ⚠️ Sequential/parallel agents | ✅ Priority-based delegation + failover |

### Tool Integration & MCP

| Feature | MemPalace | Archon | NixOS-Dev-Quick-Deploy |
|---------|-----------|--------|------------------------|
| **MCP Support** | ✅ 19 MCP tools | ⚠️ Not primary integration | ✅ MCP bridge + hybrid coordinator |
| **Tool Count** | 19 memory-specific tools | ❌ Bash + git operations | 25+ skills + MCP servers |
| **Platform Integration** | Claude, ChatGPT, Cursor, Gemini | Web UI, CLI, Telegram, Slack, Discord, GitHub | CLI, Continue.dev, MCP bridge |
| **Auto-Discovery** | ✅ Agent discovery tools | ❌ Not applicable | ⚠️ Tool registry + capability catalog |
| **GitHub Integration** | ❌ Not applicable | ✅ Issue triage, PR creation, webhooks | ⚠️ Via gh CLI |

### Monitoring & Observability

| Feature | MemPalace | Archon | NixOS-Dev-Quick-Deploy |
|---------|-----------|--------|------------------------|
| **Centralized Dashboard** | ❌ Not applicable | ✅ Web UI with multi-platform aggregation | ✅ Dashboard with AI insights |
| **Execution Tracking** | ❌ Not applicable | ✅ Run state persistence | ✅ Workflow run tracking |
| **Performance Metrics** | ✅ Recall benchmarks | ❌ Not mentioned | ✅ Token usage, cost tracking |
| **Health Monitoring** | ❌ Not applicable | ❌ Not mentioned | ✅ Multi-layer health checks |

### Cost & Resource Management

| Feature | MemPalace | Archon | NixOS-Dev-Quick-Deploy |
|---------|-----------|--------|------------------------|
| **API Cost** | ✅ Zero (local only) | ⚠️ Claude API costs | ⚠️ Mixed (local + optional remote) |
| **Local Model Support** | ✅ Llama, Mistral | ⚠️ Claude/Codex only | ✅ Ollama, vLLM, llama.cpp |
| **Token Optimization** | ⚠️ AAAK (experimental, regresses perf) | ❌ Not addressed | ✅ Local-first routing |
| **Resource Constraints** | ✅ Designed for local | ⚠️ Requires cloud access | ✅ Hardware-tier aware |

---

## Detailed Analysis

### MemPalace Strengths

#### 1. Superior Memory Architecture
- **96.6% recall accuracy** on LongMemEval (500 questions) using verbatim mode
- No summarization loss - complete conversation history preserved
- Metadata filtering improves retrieval from 60.9% to 94.8%
- Temporal knowledge graph with validity windows

**Example Use Case:**
```
Fact: "Kai works on Project Orion (2025-06 to 2026-03)"
Query in 2026-02: Returns fact as valid
Query in 2026-04: Marks as stale, prompts update
```

#### 2. Structured Memory Organization
- Palace metaphor: Wings (people/projects) → Rooms (topics) → Halls (memory types)
- Tunnels for cross-wing connections
- Drawer/Closet pattern (verbatim + summaries)

**Impact:** Structure itself provides 34% accuracy improvement via metadata filtering

#### 3. Transparent Development
- Published correction acknowledging AAAK limitations
- Open benchmark data and reproducible tests
- MIT licensed, zero cost

#### 4. MCP Tool Ecosystem
19 specialized tools including:
- `mempalace_search` - Semantic query
- `mempalace_wake_up` - Load critical facts (~170 tokens)
- `mempalace_diary_read/write` - Agent-specific persistent memory
- `mempalace_list_agents` - Discover specialist agents

### Archon Strengths

#### 1. Deterministic Workflow Engine
- YAML-based DAG definitions guarantee repeatability
- Same input → same execution sequence every time
- Eliminates unpredictability in AI agent behavior

**Example Workflow:**
```yaml
nodes:
  - id: plan
    prompt: "Explore codebase and create implementation plan"
  - id: implement
    depends_on: [plan]
    loop:
      prompt: "Implement next task. Run validation."
      until: ALL_TASKS_COMPLETE
      fresh_context: true
  - id: approve
    depends_on: [implement]
    loop:
      prompt: "Present changes for review"
      until: APPROVED
      interactive: true
```

#### 2. Git Worktree Isolation
- Each workflow run gets isolated git worktree
- Enables parallel execution without conflicts
- Automatic cleanup after completion

#### 3. Loop Constructs
- Native AI iteration loops with completion conditions
- Fresh context option prevents context poisoning
- Interactive gates for human approval

#### 4. Multi-Platform Access
- Single orchestrator, multiple interfaces
- CLI, Web UI, Telegram, Slack, Discord, GitHub webhooks
- Centralized monitoring dashboard

#### 5. Pre-Built Workflow Library
17 default workflows covering:
- Bug fixes
- Feature development
- PR reviews (simple, comprehensive, smart)
- Refactoring
- Architectural improvements

### Our System Strengths

#### 1. Declarative Infrastructure
- NixOS modules for reproducible system configuration
- Flake-based dependency pinning
- Hardware-tier aware (desktop/laptop/SBC)
- Rollback-safe deployments

#### 2. Local-First AI Stack
- Multiple local model backends (Ollama, vLLM, llama.cpp)
- Hardware-optimized routing
- Zero cloud dependency option
- Cost optimization through local execution

#### 3. Hybrid Coordination
- Priority-based delegation with automatic failover
- Role-aware routing (codex, claude, qwen, gemini)
- Subprocess agent spawning for isolation
- Safety modes (read-only, execute-mutating)

#### 4. Progressive Disclosure
- Token-efficient documentation loading
- Context cards and agent guides
- Tier-based policy enforcement
- Repository structure governance

#### 5. Comprehensive Tooling
- 25+ skills across development, data, design, utilities
- MCP bridge with tool discovery
- AIDB knowledge base integration
- Health monitoring and validation gates

---

## Gap Analysis

### Critical Gaps in Our System

#### 1. Memory & Recall (vs MemPalace)
**Gap:** No benchmarked memory system with high recall accuracy
- AIDB exists but lacks:
  - Structured memory organization (palace pattern)
  - Temporal validity tracking
  - Contradiction detection
  - Conversation mining tools
  - Verbatim storage guarantees

**Impact:** Agents cannot reliably recall past decisions, context degrades over sessions

#### 2. Workflow Determinism (vs Archon)
**Gap:** No declarative workflow definitions with guaranteed repeatability
- Current approach relies on:
  - Human-readable workflow hints
  - Role-based delegation (non-deterministic routing)
  - Manual coordination

**Impact:** Same task may execute differently across runs, debugging is harder

#### 3. Execution Isolation (vs Archon)
**Gap:** No git worktree isolation for parallel executions
- Subprocess agents provide process isolation
- But no file-level isolation for concurrent workflows

**Impact:** Limited safe parallel execution, potential conflicts

#### 4. Interactive Workflow Gates (vs Archon)
**Gap:** No formal human approval checkpoints in workflows
- Manual coordination required
- No built-in approval loops

**Impact:** Harder to enforce human-in-the-loop requirements

---

## Improvement Recommendations

### Priority 1: High-Impact, Lower Effort

#### 1.1 Implement Structured Memory Layer
**Inspired by:** MemPalace
**Effort:** Medium
**Impact:** High

**Approach:**
- Extend AIDB with structured memory organization
- Add temporal validity to facts
- Implement metadata filtering (project/topic/type)
- Create conversation mining tools for session logs

**Deliverables:**
- Enhanced AIDB schema with temporal validity
- Memory organization API (wings/rooms/halls or equivalent)
- `aq-memory` CLI tool suite
- Benchmark against LongMemEval or custom corpus

#### 1.2 Add Workflow Definition Format
**Inspired by:** Archon
**Effort:** Medium
**Impact:** High

**Approach:**
- Create YAML-based workflow DSL (subset of Archon's features)
- Support sequential dependencies and basic loops
- Integrate with existing harness coordination
- Store workflows in `.agent/workflows/definitions/`

**Deliverables:**
- Workflow schema definition (YAML)
- Workflow executor integrated with hybrid coordinator
- 5-10 common workflow templates
- `aq-workflow` CLI for execution

**Example:**
```yaml
# .agent/workflows/definitions/feature-implementation.yaml
name: Feature Implementation
description: Standard feature development workflow
nodes:
  - id: research
    agent_profile: claude
    prompt: "Research codebase and create implementation plan"

  - id: implement
    depends_on: [research]
    agent_profile: qwen
    loop:
      prompt: "Implement next task from plan"
      until: ALL_TASKS_COMPLETE
      validation: "scripts/governance/tier0-validation-gate.sh --pre-commit"

  - id: review
    depends_on: [implement]
    agent_profile: codex
    prompt: "Review implementation for integration quality"
    approval_required: true
```

#### 1.3 Enhanced Tool Discovery UI
**Inspired by:** MemPalace agent discovery
**Effort:** Low
**Impact:** Medium

**Approach:**
- Create `aq-tools list` command showing all available tools
- Categorize by: skills, MCP servers, harness APIs, bash utilities
- Include examples and when-to-use guidance

**Deliverables:**
- `aq-tools list [--category=<cat>]`
- Interactive tool browser (TUI or web)
- Auto-generated tool documentation

### Priority 2: High-Impact, Higher Effort

#### 2.1 Execution Isolation via Git Worktrees
**Inspired by:** Archon
**Effort:** High
**Impact:** High

**Approach:**
- Wrapper around workflow executions creating isolated worktrees
- Automatic cleanup after success/failure
- Support for parallel workflow execution
- Integration with existing `nixos-quick-deploy.sh`

**Deliverables:**
- `aq-workflow run --isolated <workflow-id>`
- Worktree lifecycle management
- Conflict detection and resolution
- Parallel execution coordinator

#### 2.2 Unified Monitoring Dashboard
**Inspired by:** Archon's multi-platform aggregation
**Effort:** High
**Impact:** Medium

**Approach:**
- Extend existing dashboard with workflow run tracking
- Aggregate logs from all agent sessions
- Real-time status updates
- Historical run analysis

**Deliverables:**
- Enhanced dashboard with workflow views
- Session aggregation across all agent types
- Real-time status WebSocket updates
- Run history and analytics

#### 2.3 Benchmarked Memory System
**Inspired by:** MemPalace's 96.6% recall
**Effort:** High
**Impact:** High

**Approach:**
- Build memory benchmark suite
- Test against LongMemEval or create custom dataset
- Iterate on retrieval algorithms
- Document recall accuracy metrics

**Deliverables:**
- Memory benchmark harness
- Documented recall metrics
- Retrieval optimization recommendations
- Comparison with MemPalace baseline

### Priority 3: Nice-to-Have Enhancements

#### 3.1 Multi-Platform Access
**Inspired by:** Archon
**Effort:** High
**Impact:** Low (we're CLI-focused)

**Approach:**
- Web UI for workflow execution (extend existing dashboard)
- Telegram/Slack bot integration (optional)
- GitHub webhook integration

**Deliverables:**
- Web-based workflow launcher
- Optional messaging platform bots
- GitHub Actions integration

#### 3.2 Conversation Mining
**Inspired by:** MemPalace
**Effort:** Medium
**Impact:** Medium

**Approach:**
- Import Claude.ai conversation exports
- Parse session logs into AIDB
- Extract facts and decisions
- Build searchable history

**Deliverables:**
- `aq-import --source=claude-export <file>`
- Session log parser
- Fact extraction pipeline
- Searchable conversation history

---

## Proposed Roadmap

### Phase 1: Memory Foundation (Weeks 1-3)

**Objectives:**
- Extend AIDB with structured memory
- Implement temporal validity
- Create memory organization API
- Build basic recall benchmarks

**Tasks:**
1. Design enhanced AIDB schema
2. Implement temporal validity tracking
3. Add metadata filtering (project/topic/type)
4. Create `aq-memory` CLI suite
5. Build recall benchmark harness
6. Document memory API

**Success Criteria:**
- [ ] Temporal facts stored and retrieved correctly
- [ ] Metadata filtering improves recall accuracy
- [ ] Benchmark suite operational
- [ ] Documentation complete

**Assignable Slices:**
- Schema design → claude (architecture)
- Implementation → qwen (code)
- CLI tools → qwen (code)
- Benchmarking → codex (integration)
- Documentation → qwen (docs)

### Phase 2: Workflow Engine (Weeks 4-6)

**Objectives:**
- Define workflow YAML schema
- Implement workflow executor
- Create workflow templates
- Integrate with hybrid coordinator

**Tasks:**
1. Design workflow DSL (YAML schema)
2. Implement workflow parser and validator
3. Build workflow executor
4. Create 5-10 common templates
5. Integrate with hybrid coordinator
6. Add `aq-workflow` CLI
7. Document workflow system

**Success Criteria:**
- [ ] YAML workflows execute deterministically
- [ ] Templates cover common use cases
- [ ] Integration with existing harness
- [ ] CLI operational
- [ ] Documentation complete

**Assignable Slices:**
- DSL design → claude (architecture)
- Parser/executor → qwen (code)
- Templates → codex (patterns)
- Integration → codex (coordinator)
- Documentation → qwen (docs)

### Phase 3: Isolation & Parallelism (Weeks 7-9)

**Objectives:**
- Implement git worktree isolation
- Enable parallel workflow execution
- Add conflict detection
- Integrate with quick-deploy

**Tasks:**
1. Design worktree lifecycle management
2. Implement isolation wrapper
3. Add parallel execution coordinator
4. Build conflict detection
5. Integrate with `nixos-quick-deploy.sh`
6. Add cleanup automation
7. Document isolation system

**Success Criteria:**
- [ ] Parallel workflows execute without conflicts
- [ ] Automatic cleanup works reliably
- [ ] Integration with quick-deploy seamless
- [ ] Documentation complete

**Assignable Slices:**
- Design → claude (architecture)
- Worktree management → qwen (code)
- Parallel coordinator → qwen (code)
- Integration → codex (integration)
- Documentation → qwen (docs)

### Phase 4: Enhanced Tooling (Weeks 10-12)

**Objectives:**
- Build tool discovery UI
- Enhance monitoring dashboard
- Add conversation mining
- Create benchmarks

**Tasks:**
1. Implement `aq-tools list` command
2. Build interactive tool browser
3. Extend dashboard with workflow views
4. Add session aggregation
5. Create conversation import tools
6. Build memory benchmarks
7. Document all enhancements

**Success Criteria:**
- [ ] Tool discovery functional
- [ ] Dashboard shows workflow runs
- [ ] Conversation mining operational
- [ ] Benchmarks documented
- [ ] Full documentation

**Assignable Slices:**
- Tool discovery → qwen (code)
- Dashboard enhancements → qwen (frontend)
- Conversation mining → qwen (code)
- Benchmarking → codex (testing)
- Documentation → qwen (docs)

---

## Architecture Integration Plan

### Memory Layer Integration

```
┌─────────────────────────────────────────────────────────┐
│                    AIDB Enhanced                        │
│  ┌──────────────┐  ┌──────────────┐  ┌──────────────┐  │
│  │   ChromaDB   │  │   PostgreSQL │  │  Temporal    │  │
│  │   Vectors    │  │   Metadata   │  │  Knowledge   │  │
│  │              │  │              │  │  Graph       │  │
│  └──────────────┘  └──────────────┘  └──────────────┘  │
│         ▲                 ▲                  ▲          │
│         └─────────────────┴──────────────────┘          │
│                          │                              │
│                 Memory Organization API                 │
│         (Wings/Rooms/Halls or Project/Topic/Type)       │
└─────────────────────────────────────────────────────────┘
                           ▲
                           │
┌──────────────────────────┴──────────────────────────────┐
│              Hybrid Coordinator                         │
│  ┌────────────────────────────────────────────────────┐ │
│  │  Workflow Executor                                 │ │
│  │  - YAML parser                                     │ │
│  │  - DAG execution                                   │ │
│  │  - Loop constructs                                 │ │
│  │  - Approval gates                                  │ │
│  └────────────────────────────────────────────────────┘ │
│                         │                               │
│  ┌────────────────────────────────────────────────────┐ │
│  │  Delegation Protocol                               │ │
│  │  - Priority-based routing                          │ │
│  │  - Failover chains                                 │ │
│  │  - Subprocess agents                               │ │
│  └────────────────────────────────────────────────────┘ │
└─────────────────────────────────────────────────────────┘
                           ▲
                           │
┌──────────────────────────┴──────────────────────────────┐
│              Execution Isolation Layer                  │
│  ┌────────────────────────────────────────────────────┐ │
│  │  Git Worktree Manager                              │ │
│  │  - Parallel execution                              │ │
│  │  - Conflict detection                              │ │
│  │  - Automatic cleanup                               │ │
│  └────────────────────────────────────────────────────┘ │
└─────────────────────────────────────────────────────────┘
```

### Workflow Execution Flow

```
User Request
     │
     ▼
┌─────────────────┐
│ Workflow Parser │ ← YAML definition
└────────┬────────┘
         │
         ▼
┌─────────────────┐
│ Memory Recall   │ ← Load relevant context
└────────┬────────┘
         │
         ▼
┌─────────────────┐
│ Create Worktree │ ← Isolation (if --isolated)
└────────┬────────┘
         │
         ▼
┌─────────────────────────┐
│ Execute Node Sequence   │
│  - Plan (claude)        │
│  - Implement (qwen)     │
│  - Review (codex)       │
│  - Approval gate        │
└────────┬────────────────┘
         │
         ▼
┌─────────────────┐
│ Store Results   │ → Memory layer
└────────┬────────┘
         │
         ▼
┌─────────────────┐
│ Cleanup/Merge   │ ← Worktree cleanup
└─────────────────┘
```

---

## Risk Assessment

### Risks & Mitigations

#### 1. Memory System Complexity
**Risk:** MemPalace-style memory may be over-engineered for our use case
**Mitigation:**
- Start with simplified version (project/topic/type instead of full palace)
- Benchmark early to validate value
- Iterate based on actual usage patterns

#### 2. Workflow Determinism vs Flexibility
**Risk:** Rigid workflows may limit AI agent autonomy
**Mitigation:**
- Support hybrid mode (workflow + freeform)
- Allow workflow overrides at runtime
- Maintain current hint-based approach as alternative

#### 3. Worktree Overhead
**Risk:** Git worktree isolation may slow down execution
**Mitigation:**
- Make isolation optional (--isolated flag)
- Implement efficient worktree reuse
- Profile and optimize hot paths

#### 4. Integration Complexity
**Risk:** Adding features from two systems may create architectural conflicts
**Mitigation:**
- Phased rollout with clear boundaries
- Maintain existing functionality during transition
- Comprehensive testing at each phase

---

## Success Metrics

### Phase 1 Metrics (Memory)
- Memory recall accuracy: Target 90%+ on custom benchmark
- Query response time: < 500ms for metadata-filtered queries
- Storage efficiency: < 2x size increase vs current AIDB

### Phase 2 Metrics (Workflows)
- Workflow execution consistency: 100% (same input → same steps)
- Template coverage: 10+ common development workflows
- Integration overhead: < 10% latency vs direct execution

### Phase 3 Metrics (Isolation)
- Parallel execution speedup: 2-3x for independent workflows
- Conflict rate: < 1% with proper worktree isolation
- Cleanup success rate: 99%+

### Phase 4 Metrics (Tooling)
- Tool discovery time: < 30 seconds to find relevant tool
- Dashboard response time: < 2 seconds for run status
- Conversation import throughput: > 100 messages/minute

---

## Resource Requirements

### Development Resources
- **Phase 1:** 1 architect + 2 implementers (3 weeks)
- **Phase 2:** 1 architect + 2 implementers (3 weeks)
- **Phase 3:** 1 architect + 2 implementers (3 weeks)
- **Phase 4:** 2 implementers (3 weeks)

**Total:** ~12 weeks with 2-3 concurrent developers

### Infrastructure Requirements
- PostgreSQL for temporal knowledge graph
- Additional 10-20GB storage for memory system
- ChromaDB instance (can reuse existing AIDB)

### Testing Requirements
- Memory benchmark corpus (500-1000 fact-query pairs)
- Workflow test suite (20+ test workflows)
- Integration test environment
- Performance benchmarking tools

---

## Conclusion

### Summary of Findings

**MemPalace** provides proven memory architecture with 96.6% recall. Their structured organization and temporal validity features would significantly enhance our context retention.

**Archon** demonstrates how deterministic workflows improve repeatability and debugging. Their git worktree isolation enables safe parallel execution.

**Our System** has strong declarative infrastructure and local-first AI capabilities, but lacks advanced memory and workflow features.

### Recommended Action

**Proceed with phased implementation:**
1. ✅ **Phase 1 (Weeks 1-3):** Memory foundation - High ROI
2. ✅ **Phase 2 (Weeks 4-6):** Workflow engine - High ROI
3. ⚠️ **Phase 3 (Weeks 7-9):** Isolation - Medium ROI (evaluate after Phase 2)
4. ⚠️ **Phase 4 (Weeks 10-12):** Enhanced tooling - Lower priority

### Next Steps

1. **Stakeholder Review:** Present this analysis to system architects
2. **Phase 1 Kickoff:** Assign memory system design to claude (architecture)
3. **Benchmark Setup:** Create initial memory benchmark corpus
4. **Resource Allocation:** Assign qwen/codex slices for implementation
5. **Progress Tracking:** Weekly check-ins on roadmap progress

---

## Appendix A: Detailed Feature Comparison

### MemPalace Features Deep Dive

**Memory Organization:**
- Wings: Top-level grouping (people, projects)
- Rooms: Topic categories within wings
- Halls: Memory types (facts, events, discoveries, preferences, advice)
- Tunnels: Cross-wing connections
- Closets: Summary pointers
- Drawers: Original verbatim storage

**Storage Backend:**
- ChromaDB for vector embeddings
- SQLite for temporal knowledge graph
- No external dependencies

**Query Interface:**
- Semantic search across all memories
- Metadata filtering (wing + room + hall)
- Temporal validity queries
- Contradiction detection

**Integration:**
- 19 MCP tools
- Claude Code plugin
- Local model support (Llama, Mistral)
- Export to various AI platforms

**Benchmarks:**
- LongMemEval: 96.6% recall (verbatim mode)
- Metadata filtering: 94.8% vs 60.9% baseline
- Zero API calls for recall

### Archon Features Deep Dive

**Workflow Definition:**
```yaml
nodes:
  - id: <node-id>
    prompt: <ai-prompt>
    bash: <shell-command>
    depends_on: [<dependencies>]
    loop:
      prompt: <loop-prompt>
      until: <condition>
      fresh_context: <bool>
      interactive: <bool>
```

**Execution Model:**
- DAG topological sort for ordering
- Sequential dependency resolution
- Loop iteration with conditions
- Fresh context per loop iteration

**Isolation:**
- Git worktree per workflow run
- Automatic branch creation
- PR creation on completion
- Cleanup on success/failure

**Platform Support:**
- CLI (primary interface)
- Web UI (monitoring + execution)
- Telegram bot
- Slack integration
- Discord bot
- GitHub webhooks

**Persistence:**
- SQLite or PostgreSQL
- 7 core tables (runs, nodes, messages, etc.)
- Run state tracking
- Message history

---

## Appendix B: Code Examples

### MemPalace MCP Tool Usage

```python
# Wake up with critical facts
response = await mcp.call_tool(
    "mempalace_wake_up",
    {}
)
# Returns ~170 tokens of critical context

# Search for specific memories
response = await mcp.call_tool(
    "mempalace_search",
    {
        "query": "authentication implementation decisions",
        "wing": "project-auth",
        "room": "architecture",
        "hall": "decisions"
    }
)

# Write to agent diary
await mcp.call_tool(
    "mempalace_diary_write",
    {
        "agent": "qwen",
        "entry": "Implemented JWT validation with 7-day expiry"
    }
)
```

### Archon Workflow Example

```yaml
# .archon/workflows/feature-development.yaml
name: Feature Development
description: Standard feature implementation workflow

nodes:
  - id: explore
    prompt: |
      Explore the codebase and understand:
      1. Existing patterns
      2. Related functionality
      3. Test coverage
      Create a detailed implementation plan.

  - id: implement
    depends_on: [explore]
    loop:
      prompt: |
        Implement the next task from the plan.
        Run validation after each change.
        Mark task complete when tests pass.
      until: ALL_TASKS_COMPLETE
      fresh_context: true

  - id: test
    depends_on: [implement]
    bash: "pytest tests/ --cov"

  - id: review
    depends_on: [test]
    loop:
      prompt: |
        Review the implementation:
        1. Code quality
        2. Test coverage
        3. Documentation

        Present findings and await approval.
      until: APPROVED
      interactive: true

  - id: pr
    depends_on: [review]
    bash: |
      git add -A
      git commit -m "Implement feature: ${FEATURE_NAME}"
      gh pr create --title "${FEATURE_NAME}" --body "$(cat PR_DESCRIPTION.md)"
```

### Proposed Integration Example

```python
# scripts/ai/aq-workflow-execute.py
from hybrid_coordinator import WorkflowExecutor, MemoryRecall

async def execute_workflow(workflow_path: str, isolated: bool = False):
    """Execute a workflow with memory-enhanced context."""

    # Load workflow definition
    workflow = WorkflowExecutor.load_yaml(workflow_path)

    # Recall relevant memories
    memory = MemoryRecall()
    context = await memory.search(
        query=workflow.description,
        project=workflow.project,
        topic=workflow.topic
    )

    # Create isolated environment if requested
    if isolated:
        worktree = await create_worktree(workflow.id)
        os.chdir(worktree.path)

    try:
        # Execute workflow nodes
        for node in workflow.topological_order():
            result = await execute_node(
                node,
                context=context,
                memory=memory
            )

            # Store results in memory
            await memory.store(
                fact=result.summary,
                project=workflow.project,
                topic=node.topic,
                valid_from=now(),
                valid_until=None  # Indefinite unless updated
            )

            # Check approval gates
            if node.approval_required:
                approved = await await_approval(result)
                if not approved:
                    raise WorkflowRejected(node.id)

    finally:
        # Cleanup worktree
        if isolated:
            await cleanup_worktree(worktree)
```

---

## Appendix C: References

### External Links
- [MemPalace GitHub](https://github.com/milla-jovovich/mempalace)
- [Archon GitHub](https://github.com/coleam00/archon)
- [LongMemEval Benchmark](https://github.com/Bui1dMySea/LongMemEval) (inferred)
- [MCP Specification](https://modelcontextprotocol.io/)

### Internal Documents
- [AGENTS.md](/home/hyperd/Documents/NixOS-Dev-Quick-Deploy/AGENTS.md)
- [docs/AGENTS.md](/home/hyperd/Documents/NixOS-Dev-Quick-Deploy/docs/AGENTS.md)
- [CLAUDE.md](/home/hyperd/Documents/NixOS-Dev-Quick-Deploy/CLAUDE.md)
- [Hybrid Coordinator](/home/hyperd/Documents/NixOS-Dev-Quick-Deploy/ai-stack/mcp-servers/hybrid-coordinator/)
- [Local Orchestrator](/home/hyperd/Documents/NixOS-Dev-Quick-Deploy/ai-stack/local-orchestrator/)

---

**Document Version:** 1.0.0
**Last Updated:** 2026-04-09
**Next Review:** After Phase 1 completion (Week 3)
**Owner:** AI Stack Architecture Team
