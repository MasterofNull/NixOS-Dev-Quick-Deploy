# PRD: Agentic-First Architecture Elevation

**Version:** 1.0
**Status:** DRAFT — Research-Driven
**Date:** 2026-05-14
**Phase Tracker:** `.agents/plans/phase-54-agentic-first-elevation.md`
**Collaborators:** Claude (orchestrator/author), Gemini (routing/topology analysis — task gemini-20260514-171425-i7ecuo)

---

## 1. Context and Motivation

This PRD is driven by two converging inputs:

1. **Research synthesis** — The 2025–2026 state of the art in agentic AI, RAG, DAG execution, AI memory operating systems, and spec-driven evaluation reveals a clear gap between where this harness is today and what world-class agentic infrastructure looks like.

2. **System self-assessment** — After 53+ phases of spec-driven development, the harness is functionally sound but architecturally fragmented. The 7-layer health model shows L1, L2, L6, and L7 as degraded or offline. RAG posture is "historical" (0 active retrieval calls). Routing is profile-based, not intent-aware. Memory is partial. Eval score is 83% but rising — the right moment to lock in architectural elevation before technical debt compounds.

### Research Drivers

| Domain | 2025–2026 State of the Art | Our Current Gap |
|--------|---------------------------|-----------------|
| **Memory** | MemOS: working + episodic + semantic + procedural stores; temporal validity; knowledge graphs with contradiction handling; 96.6% recall benchmarks | AIDB partially covers semantic; working/episodic/procedural not formalized; recall not benchmarked; no temporal validity |
| **Routing** | Intent-driven orchestration: NLU classification → agent selection → tool invocation; dynamic re-routing on failure | Profile-based switchboard; routing decisions don't use semantic intent; no real-time re-routing |
| **RAG** | Context engine pattern: hybrid retrieval (semantic + keyword + graph); active pipeline with every query; multimodal; compaction-aware | RAG posture "historical" — 0 retrieval calls in recent window; AIDB used for indexing, not query augmentation |
| **DAG Execution** | LangGraph 1.0: durable execution (checkpoint/resume after failure); human-in-the-loop gates; evolving orchestration (learns from perf feedback) | DAG executor exists (Phase 49) with retry/backoff (Phase 38); no durable state/checkpoint-resume; no evolving orchestration |
| **Observability** | Full request trace; logic pattern indexing; topology visualization; spec-driven continuous eval | Topology API added (Phase 52); logic pattern indexing added (Phase 52); eval running but not continuous; request trace incomplete |
| **Harness contracts** | Explicit input/output schemas per agent transition; structured handoff artifacts; phase gates with evidence | 7-step workflow contract exists; MCP blueprints exist; but schema enforcement is informal |
| **AI OS** | "Stateful AI Runtimes: Agent Memory Is the New OS" — memory layer as OS-level abstraction coordinating all stores | Memory scattered: AIDB for docs, Redis for cache, no unified memory abstraction |

---

## 2. Problem Statement

The harness is **functionally operational but not intentionally agentic**. Specifically:

**P1 — Memory is not a first-class citizen.**
Memory is scattered across AIDB (document store), Redis (semantic cache), and session logs. There is no unified memory abstraction. Recall is not benchmarked. Temporal validity is not implemented. The system cannot distinguish between what it _knew_, what it _knows now_, and what has been contradicted.

**P2 — Routing is profile-based, not intent-aware.**
The switchboard selects a routing profile (local, remote, embedded-assist) based on static configuration, not the semantic intent of the incoming query. The hybrid coordinator dispatches by mode, not by what the task actually needs. Result: misrouting is silent, untracked, and unrecoverable without manual intervention.

**P3 — RAG is indexing, not augmentation.**
AIDB holds indexed documents and logic patterns, but the coordinator does not inject retrieved context into query processing. The retrieval pipeline is _available_ but not _active_. Every query is answered from model weights alone — defeating the purpose of the knowledge store.

**P4 — DAG execution lacks durability.**
The workflow executor (Phase 49) and retry policy (Phase 38) exist, but there is no checkpoint/resume capability. A workflow interrupted mid-DAG must restart from scratch. For long-horizon agent tasks (8+ hour workflows per 2025 research), this is a critical reliability failure.

**P5 — L6 (Cognitive/Semantic) is offline.**
The layer that should handle context compression, retrieval augmentation, and semantic enrichment is marked unhealthy. Without L6, every agent interaction degrades to raw LLM inference with no harness intelligence applied.

**P6 — Evaluation is episodic, not continuous.**
Eval runs exist (83% latest, 2 runs in history). But there is no continuous eval loop, no regression detection between phases, and no automatic flag when a new phase degrades prior benchmarks.

---

## 3. Goals

### Primary Goal
Elevate this harness from a **functionally assembled AI stack** to a **world-class agentic-first architecture** — where memory, routing, retrieval, and execution are intentionally linked, continuously measured, and self-improving.

### Measurable Success Criteria

| Metric | Baseline (now) | Target |
|--------|---------------|--------|
| Layer health (L1–L7) | 3/7 healthy | 6/7 healthy |
| RAG posture | historical (0 calls) | active (>80% queries augmented) |
| Memory recall benchmark | not measured | ≥85% on harness-specific recall test |
| Intent classification accuracy | not measured | ≥80% correct route selection |
| Workflow checkpoint coverage | 0% (no resume) | 100% of DAG workflows checkpoint-resumable |
| Eval continuity | episodic (2 runs) | continuous (auto-triggered per phase) |
| Request trace coverage | partial | 100% of coordinator queries traced end-to-end |
| aq-qa total checks | 59 | ≥72 (13 new checks across 6 themes) |

---

## 4. Architecture Themes

### Theme A — Unified Memory Layer (MemOS Pattern)

**Goal:** One abstraction that coordinates all memory stores. Agents write to memory through a unified API; retrieval is automatic and type-aware.

**Memory taxonomy to implement:**
- **Working memory**: current task context (Redis, TTL-bounded)
- **Episodic memory**: per-session interaction history (AIDB project `episodic`)
- **Semantic memory**: factual knowledge, indexed patterns (AIDB — exists, extend)
- **Procedural memory**: learned tool sequences and delegation patterns (new AIDB project `procedural`)

**Key changes:**
- `MemoryBroker` class in hybrid-coordinator: unified read/write interface
- Temporal validity: every write carries `valid_from` + `valid_until`; reads filter by wall clock
- Contradiction resolution: when a new fact contradicts an existing one, flag + log both; prefer newer unless explicitly pinned
- Recall benchmark harness: 20-question test pack against AIDB; minimum 85% pass gate in aq-qa

**Relevant prior work:** Phase 13 (memory systems maturity), Phase 18 (agent mesh collective memory)

---

### Theme B — Intent-Aware Routing

**Goal:** Replace static profile dispatch with semantic intent classification before routing. The coordinator asks "what does this task _need_?" before deciding where to send it.

**Intent taxonomy (starter):**
- `code_generation` → local Qwen, agent loop
- `code_review` → local Qwen, structured output
- `knowledge_lookup` → AIDB retrieval first, then LLM synthesis
- `planning` → Claude (orchestrator), chain-of-thought
- `math_reasoning` → local Qwen, high temperature off
- `tool_execution` → local tool-calling mode
- `delegation` → multi-agent fanout

**Key changes:**
- `IntentClassifier` module: lightweight (sub-50ms) embedding-based intent detection using llama-embed :8081
- Intent → profile mapping table (config-driven, hot-reloadable)
- Routing decision logged per query: `{intent, profile_selected, model_used, latency}`
- aq-qa check: intent classifier registered + accuracy probe ≥80%

**Relevant prior work:** hints_engine (contextual bandit), switchboard profiles (46-SWITCHBOARD-PROFILES.md)

---

### Theme C — Active RAG Pipeline

**Goal:** Every coordinator query is augmented with retrieved context from AIDB before being sent to the LLM. RAG shifts from "available" to "default."

**Pipeline:**
```
Query → IntentClassifier → [knowledge_lookup OR other intent]
  → AIDB /vector/search (project=semantic, top_k=5)
  → Context injection into prompt template
  → LLM inference (local or remote)
  → Response + retrieved_sources logged
```

**Key changes:**
- `RagAugmentor` module: wraps every `/query` call; injects top-k retrieved docs into system prompt
- Project-aware retrieval: knowledge_lookup → `semantic`, code tasks → `logic-patterns`, planning → `episodic`
- Retrieval hit/miss logged to Redis; surfaced in aq-report as "active" posture
- L6 health gate: active RAG posture = L6 healthy
- aq-qa checks: RAG posture = active; retrieval calls per hour ≥ query volume × 0.8

**Relevant prior work:** AIDB re-indexing (Phase 52), logic pattern indexing (Phase 52), semantic cache (current)

---

### Theme D — Durable DAG Execution

**Goal:** Any workflow interrupted mid-execution can resume from its last successful checkpoint without data loss or task restart.

**Key changes:**
- `WorkflowCheckpoint` model: serializes DAG state (completed nodes, pending nodes, node outputs) to PostgreSQL at each node completion
- `POST /workflow/run/{id}/resume` endpoint: load checkpoint, re-enqueue pending nodes
- Dead-letter queue: failed nodes beyond retry limit → `workflow_dlq` Redis list; operator notification via dashboard alert
- Evolving orchestration: track `{workflow_id, pattern, latency, success}` → surface "prefer sequential over concurrent for code tasks" type insights in aq-report
- aq-qa checks: checkpoint table exists; resume endpoint registered; DLQ surfaced in dashboard

**Relevant prior work:** Phase 49 (DAG executor), Phase 38 (retry/backoff PAR-003), Phase 46 (rollback drill)

---

### Theme E — Observability Spine

**Goal:** Every coordinator query has a complete end-to-end trace: intent → routing decision → retrieval → LLM call → response → memory write.

**Trace schema:**
```json
{
  "trace_id": "uuid",
  "query": "...",
  "intent": "knowledge_lookup",
  "profile": "local-tool-calling",
  "retrieval": {"project": "semantic", "hits": 5, "latency_ms": 42},
  "llm": {"model": "qwen3", "tokens_in": 1200, "tokens_out": 300, "latency_ms": 9800},
  "memory_write": {"episodic": true, "working": true},
  "total_latency_ms": 10234,
  "trace_at": "ISO-8601"
}
```

**Key changes:**
- `TraceCollector` context manager: wraps every `/query` call; writes to PostgreSQL `query_traces` table
- `GET /api/traces` endpoint in dashboard: last 100 traces, filterable by intent/latency/model
- Slow trace alert: any trace >30s surfaced as dashboard alert
- Request trace coverage in aq-qa: ≥95% of queries have trace record

**Relevant prior work:** Phase 52 (topology + logic flow), Phase 37 (lifecycle trajectory/replay), PRSI loops

---

### Theme F — Continuous Spec-Driven Evaluation

**Goal:** Every phase commit triggers an automatic eval run. Regressions are caught before they merge.

**Key changes:**
- `POST /eval/run` endpoint: trigger 12-case benchmark + aq-qa full suite
- Pre-commit hook integration: `tier0-validation-gate.sh` calls eval gate; blocks commit if score drops >5% from last run
- Eval trend stored in PostgreSQL: `{phase, score, timestamp, checks_passed, checks_failed}`
- `GET /eval/trend` endpoint: last 10 runs; surfaced in dashboard eval panel
- Auto-flag: if any new aq-qa check fails that passed in previous phase, alert + block commit
- aq-qa checks: eval endpoint registered; trend table populated; pre-commit hook wired

**Relevant prior work:** Phase 43 (SWE benchmark), Phase 44 (unified harness runner + PAR-002 CI gate), eval score 83%

---

## 5. Non-Goals

- Replacing NixOS-first, flake-based infrastructure — all services remain declaratively managed
- Adding remote model dependencies — local-first remains the default; remote is optional offload
- Breaking existing MCP blueprint contracts or aq-qa checks
- Changing port assignments (source of truth: `nix/modules/core/options.nix`)
- Big-bang rewrites — each theme is delivered in atomic, validated slices

---

## 6. Risks and Mitigations

| Risk | Likelihood | Impact | Mitigation |
|------|-----------|--------|-----------|
| AIDB retrieval latency degrades query UX | Medium | High | Async retrieval with 500ms timeout fallback; skip augmentation on timeout |
| Intent classifier adds >50ms to every query | Medium | Medium | Use llama-embed :8081 (already running); cache classification by query embedding |
| PostgreSQL checkpoint table grows unbounded | Low | Medium | TTL policy: auto-purge checkpoints >7 days old |
| L6 activation causes routing regression | Low | High | Feature-flag each theme; rollback = disable flag; eval gate blocks regression |
| Gemini analysis contradicts Claude's routing findings | Low | Low | Merge both; surface disagreements in PRD notes; architect resolves |

---

## 7. Gemini Collaboration

Gemini CLI agent (task `gemini-20260514-171425-i7ecuo`) was dispatched to perform:
1. Routing flow audit (http_server.py + switchboard profiles)
2. AIDB/RAG gap analysis (active vs historical posture in code)
3. Memory architecture gap (Phase 13 vs current state)

**To retrieve Gemini's contribution:**
```bash
delegate-to-gemini --check gemini-20260514-171425-i7ecuo
```

Gemini's findings should be integrated into Themes B and C above once available. Conflicts with Claude's analysis should be flagged and resolved before Phase 54 execution begins.

---

## 8. Delivery Structure

Each theme maps to a sub-phase. All sub-phases follow the standard slice format:
- `[architect]` slice: design + risk
- `[implementer]` slice: code + test
- `[orchestrator]` gate: validation + commit

| Sub-Phase | Theme | Key Deliverable | New aq-qa Checks |
|-----------|-------|----------------|-----------------|
| 54.1 | A — Memory | `MemoryBroker`, temporal validity, recall benchmark | 3 |
| 54.2 | B — Intent Routing | `IntentClassifier`, intent→profile map, routing log | 2 |
| 54.3 | C — Active RAG | `RagAugmentor`, retrieval injection, L6 health gate | 2 |
| 54.4 | D — Durable DAG | `WorkflowCheckpoint`, resume endpoint, DLQ | 3 |
| 54.5 | E — Observability | `TraceCollector`, traces endpoint, slow-trace alert | 2 |
| 54.6 | F — Continuous Eval | eval trigger, trend table, pre-commit hook | 1 |

**Total new aq-qa checks: 13**
**aq-qa total after Phase 54: 72 checks**

---

## 9. Acceptance Criteria (Phase Gate)

Phase 54 is complete when ALL of the following pass:

- [ ] aq-qa reports ≥72 checks passing, 0 failing
- [ ] L6 health = healthy (active RAG posture confirmed)
- [ ] Memory recall benchmark ≥85%
- [ ] Intent classifier accuracy probe ≥80%
- [ ] At least 1 full DAG workflow checkpoint-resume cycle demonstrated
- [ ] `GET /api/traces` returns records for last 10 queries
- [ ] Eval trend table has entries for all Phase 54 sub-phases
- [ ] Gemini contribution integrated into Themes B and C

---

## 10. References

### Research Sources
- [Agentic AI: Comprehensive Survey — arxiv 2510.25445](https://arxiv.org/abs/2510.25445)
- [AI Agent Systems: Architectures, Applications, Evaluation — arxiv 2601.01743](https://arxiv.org/html/2601.01743v1)
- [Agentic RAG Survey — arxiv 2501.09136](https://arxiv.org/html/2501.09136v4)
- [State of AI Agent Memory 2026 — mem0.ai](https://mem0.ai/blog/state-of-ai-agent-memory-2026)
- [MemOS: Self-evolving Memory OS — GitHub MemTensor/MemOS](https://github.com/MemTensor/MemOS)
- [Stateful AI Runtimes: Agent Memory Is the New OS — buildmvpfast.com](https://www.buildmvpfast.com/blog/stateful-ai-runtime-agent-memory-operating-system-2026)
- [LangGraph Multi-Agent Orchestration — latenode.com](https://latenode.com/blog/ai-frameworks-technical-infrastructure/langgraph-multi-agent-orchestration/langgraph-multi-agent-orchestration-complete-framework-guide-architecture-analysis-2025)
- [The 2026 Guide to Agentic Workflow Architectures — stackai.com](https://www.stackai.com/blog/the-2026-guide-to-agentic-workflow-architectures)
- [Harness Design for Long-Running Apps — anthropic.com](https://www.anthropic.com/engineering/harness-design-long-running-apps)
- [Harness Engineering for AI Coding Agents — augmentcode.com](https://www.augmentcode.com/guides/harness-engineering-ai-coding-agents)
- [awesome-harness-engineering — GitHub ai-boost](https://github.com/ai-boost/awesome-harness-engineering)
- [RAG in 2026 — techment.com](https://www.techment.com/blogs/rag-in-2026/)
- [From RAG to Context — RAGFlow 2025 review](https://ragflow.io/blog/rag-review-2025-from-rag-to-context)
- [2026 Agentic Coding Trends Report — Anthropic](https://resources.anthropic.com/hubfs/2026%20Agentic%20Coding%20Trends%20Report.pdf)

### Internal Prior Work
- Phase 13: Memory systems maturity
- Phase 18: Agent mesh collective memory
- Phase 38: DAG retry/backoff (PAR-003)
- Phase 43: SWE benchmark integration
- Phase 44: Unified harness runner + PAR-002 CI gate
- Phase 49: Orchestration graph runner
- Phase 52: Logic error discovery + system org diagrams
- Phase 53: Command center dashboard revamp
