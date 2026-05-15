# Architecture Revamp PRD — Comprehensive Senior Review
**Date:** 2026-05-15
**Status:** ACTIVE — All agents complete, ready for slice execution
**Lead:** Claude Sonnet 4.6 (Orchestrator)
**Contributing Agents:** Gemini CLI (sec14), Codex CLI (sec13), Explorex3 (sec12/sec15/RELATIONAL-GRAPH)
**Scope:** System map, request routing flow, agentic harness logic, relational repo graph

---

## 1. Executive Summary

The current architecture documentation has four critical deficiencies that cause real confusion and operational risk:

1. **Routing direction is inverted in docs** — "continue-local and default lanes from switchboard to coordinator" do not exist. The actual arrows run in two independent directions (switchboard → coordinator for hints; coordinator → switchboard for LLM generation) and neither is labeled in the system map.
2. **Agents are absent as first-class actors** — Claude Code, Codex, Gemini, and the Qwen agent loop are real consumers of the harness but appear in zero system diagrams.
3. **Three orphaned routing taxonomies exist in parallel** — `routing_contract.py`, `local-orchestrator/router.py`, and `local-agents/task_router.py` all define their own backend names with no bridge between them.
4. **The relational graph covers only coordinator Python modules** — scripts, Nix modules, governance tooling, and the delegation layer are invisible to any graph.

---

## 2. Routing Flow Reality (vs. Current Docs)

### 2.1 What the docs claim (wrong framing)

The system map in `docs/architecture/AI-STACK-ARCHITECTURE.md` (dated 2026-03-05) shows:

```
hybrid-coordinator → switchboard → llama
```

This is correct for **orchestration-initiated queries** but describes only one of three request paths and implies a single direction of data flow.

### 2.2 Actual data paths (three independent flows)

**Path A — IDE Direct Chat** (most user-facing traffic)
```
Continue IDE / Claude Code Extension
    ↓  (HTTP POST /v1/chat/completions + x-ai-profile: continue-local|default|local-agent)
Switchboard :8085
    ├─ [if profile.injectHints=true] ──→ Coordinator :8003 GET /hints?q=...
    │                                     ← hints string returned
    └─ POST /v1/chat/completions ──→ llama-server :8080
                                      ← response streamed back
```

Profile behavior:
| Profile | injectHints | forceProvider | Coordinator Contact |
|---------|------------|---------------|---------------------|
| `continue-local` | false | local | **NONE** |
| `default` | true | auto | GET /hints only |
| `local-agent` | true | local | GET /hints only |
| `remote-*` | false | remote | **NONE** |

**Path B — Orchestration & Agent Tasks**
```
aq-* CLI / MCP tools / REST client
    ↓  (POST /query, /v1/orchestrate, /workflow/*, /control/*)
Coordinator :8003
    ├─ internal routing (task_classifier, route_handler, search_router)
    ├─ optional RAG: Qdrant :6333 + AIDB :8002
    └─ POST /v1/chat/completions ──→ Switchboard :8085 (as backend)
                                          └──→ llama :8080 or remote API
```

**Path C — Agent Delegation** (external AI agents as callers)
```
Claude Code / Codex / Gemini CLI
    ↓  (via delegate-to-* bash scripts OR MCP tools OR direct REST)
scripts/ai/lib/audit-write.sh ──→ POST /api/agent-events (Coordinator)
                                       └──→ tool-audit.jsonl + ContinuousLearning
Coordinator :8003
    ├─ POST /control/ai-coordinator/delegate ──→ remote API or local Qwen
    └─ GET /hints / POST /query / GET /api/memory/* (various)
```

### 2.3 The bidirectional switchboard ↔ coordinator relationship

```
Switchboard :8085
    ──→ Coordinator :8003  (GET /hints, for injectHints profiles)
    ←── Coordinator :8003  (receives /v1/chat/completions as LLM backend)
```

This bidirectional relationship is the root of all "lane" confusion. It must be shown explicitly in all diagrams. The switchboard is simultaneously:
- **Ingress proxy** for IDE/editor clients (Path A)
- **LLM execution backend** for the coordinator (Path B)

These are two completely separate request flows sharing the same service.

---

## 3. Missing Actors in System Maps

### 3.1 External AI agents (completely absent from all diagrams)

| Actor | Integration point | Protocol |
|-------|-------------------|----------|
| Claude Code CLI | `POST /query`, MCP tools, direct REST | HTTP + MCP |
| Claude Code Extension | Switchboard :8085 via `default` profile | OpenAI-compat |
| Codex CLI | `delegate-to-codex` → `/api/agent-events` | bash → HTTP |
| Gemini CLI | `delegate-to-gemini` → `/api/agent-events` | bash → HTTP |
| Qwen local agent (`aq-agent-loop`) | `POST /v1/chat/completions` direct to llama:8080 | HTTP |
| aq-* CLI tools | Various coordinator endpoints | HTTP |

### 3.2 Missing service: ralph-wiggum (:8004)

The ralph-wiggum secondary inference service at :8004 appears in port tables but in zero flow diagrams. It is a coordinator-adjacent service that receives `POST /task` with a `prompt` field. Its relationship to the coordinator is undocumented in all maps.

### 3.3 Missing service: dashboard (:8889)

The dashboard backend reads from coordinator endpoints but is not shown in any diagram. It is a read-only consumer of `/api/health/*`, `/api/topology`, `/api/traces`, `/api/memory/*`.

---

## 4. Module Naming Critique

### 4.1 "hybrid-coordinator" — the name is misleading

**What "hybrid" was intended to mean:** The coordinator speaks BOTH the MCP stdio protocol AND HTTP REST. "Hybrid" = dual protocol, not dual-backend.

**What users infer it means:** "hybrid local/remote routing" — which is the SWITCHBOARD's job, not the coordinator's.

**Recommendation:** Rename conceptually (not necessarily in code) to **"agent-orchestrator"** or **"orchestration-brain"** in all documentation. The code service name `ai-hybrid-coordinator` can stay for NixOS systemd compatibility, but docs should stop explaining it as "hybrid local+remote."

### 4.2 "local-orchestrator" — now a compatibility layer, named as if primary

`scripts/ai/local-orchestrator` is a shell CLI. It calls `/v1/orchestrate` on the coordinator first. The Python `LocalOrchestrator` class in `ai-stack/local-orchestrator/orchestrator.py` is a fallback if the coordinator is down.

The name implies it IS the orchestrator. It is not. It is a **CLI front-door** that delegates to the real orchestrator (coordinator). This causes agent confusion about which layer owns routing policy.

### 4.3 Three "agent" namespaces with no disambiguation

| Term | Actual meaning |
|------|----------------|
| `local-agents` (`ai-stack/local-agents/`) | Qwen executor loop — runs tasks locally via llama |
| `agent-mesh` (AGI scaffold) | Identity/affective/world-model peer network |
| `agent_registry.py` (coordinator) | Runtime registration of live agent sessions |
| `agents_task_handlers.py` (coordinator) | HTTP handlers for agent task management |
| `ai-agents` (systemd) | Possibly the above |

All use "agent" as a namespace with no qualifier. Cross-reading any two of these is actively misleading.

### 4.4 "continuous_learning.py" vs "real_time_learning_engine.py"

Two modules both imported by the coordinator that do overlapping things. The module map (`hybrid-coordinator-module-map.md`) flagged this but it was never resolved. This is an active source of behavior uncertainty.

### 4.5 Garbage collection duplicate

`garbage_collection.py` and `garbage_collector.py` are both present. Module map flagged both. Still unresolved.

---

## 5. Orphaned Routing Taxonomy Drift

Three routing systems exist in parallel with no canonical bridge:

| System | Location | Taxonomy | Status |
|--------|----------|----------|--------|
| `routing_contract.py` | `ai-stack/mcp-servers/hybrid-coordinator/` | `LOCAL, EDGE, REMOTE_FREE, REMOTE_PAID, REMOTE_FLAGSHIP` | **CANONICAL** |
| `router.py` | `ai-stack/local-orchestrator/router.py` | `AgentBackend.LOCAL, QWEN, CLAUDE_SONNET, CLAUDE_OPUS` | **ORPHANED** |
| `task_router.py` | `ai-stack/local-agents/task_router.py` | `REMOTE_CODEX, REMOTE_CLAUDE, REMOTE_QWEN` | **ORPHANED** |
| `switchboard profiles` | `nix/modules/services/switchboard.nix` | `continue-local, local-agent, remote-coding, ...` | **CANONICAL (separate domain)** |

None of the orphaned routers are adapters — they invent independent backend names that map to real vendor models (CLAUDE_SONNET, REMOTE_CODEX) which violates the architecture rule: "never hardcode remote model IDs."

The `routing_contract.py` tiers (LOCAL → REMOTE_FLAGSHIP) are the correct abstraction. The orphaned routers must be converted to thin adapters that emit `RoutingDecision` objects from `routing_contract.py`.

---

## 6. Relational Repo Graph — Critical Gaps

### 6.1 What exists

- `docs/architecture/hybrid-coordinator-module-map.md` — Python modules INSIDE coordinator only
- `docs/architecture/AI-STACK-ARCHITECTURE.md` — high-level service diagram (2026-03-05, stale)

### 6.2 What is missing

**Scripts layer** (`scripts/ai/`, `scripts/governance/`, `scripts/automation/`)
- Which scripts call which service endpoints
- Which scripts source other scripts
- Which files each script reads/writes

**Nix module → service mapping**
- Which `.nix` file declares which systemd service
- Which options flow into which service via environment variables
- Dependency order (which service waits on which)

**Delegation layer** (`.agents/delegation/`, `scripts/ai/delegate-to-*`)
- How external agents connect to the harness event bus
- Registry lifecycle (how entries age out)
- Audit trail flow: delegate-to-* → audit-write.sh → /api/agent-events → tool-audit.jsonl → ContinuousLearning → lesson registry

**Knowledge loop** (Phase 56 complete but not diagrammed)
```
work → agent-events (POST /api/agent-events)
     → ContinuousLearning
     → lesson registry (/var/lib/nixos-ai-stack/lessons/)
     → aq-lesson-promote
     → aq-session-start (next session inherits)
```

**Memory subsystem** (Phases 54–55, complete but only in PRD prose)
- memory_broker.py → MemoryBroker unified write path
- memory_superseder.py → supersession/history
- memory_crystallizer.py → crystallization from sessions
- drift_analyzer.py → traces drift detection
- All feed into AIDB and Qdrant collections but this is not diagrammed

---

## 7. Proposed Corrected System Map

### 7.1 Layer model (replaces flat diagram)

```
┌─────────────────────────────────────────────────────────────────────┐
│  LAYER 7: ACTOR LAYER (External Agents + Human IDEs)                │
│                                                                      │
│  Claude Code CLI/Ext  Codex CLI    Gemini CLI    Human (IDE)         │
│       ↓  ↓                ↓            ↓              ↓              │
│    MCP tools        delegate-to-*  delegate-to-*  Continue.dev       │
│    direct REST      audit-write    audit-write    :8085 (SWB)        │
└─────────────────────┬────────────┬──────────────────┬───────────────┘
                      │            │                  │
┌─────────────────────▼────────────▼──────────────────▼───────────────┐
│  LAYER 6: ORCHESTRATION BRAIN (hybrid-coordinator :8003)             │
│                                                                      │
│  Ingress surfaces:                                                   │
│    /v1/orchestrate  /query  /workflow/*  /control/*  /api/*          │
│                                                                      │
│  Internal subsystems:                                                │
│    route_handler → task_classifier → search_router                  │
│    hints_engine ← (called by switchboard for hints injection)        │
│    workflow_executor → DAG runner → checkpointer (DLQ)               │
│    memory_broker → superseder → crystallizer                         │
│    trace_collector → eval_runner → drift_analyzer                   │
│    lifecycle_fsm (UAG) → intake_gateway                              │
│    agent_registry / agent_capability_registry                        │
│    continuous_learning / real_time_learning_engine [AUDIT DUP]       │
│    ai_coordinator → POST /control/ai-coordinator/delegate            │
│                                                                      │
│  Egress to LLM:                                                      │
│    → Switchboard :8085 (as backend, for LLM generation)              │
│  Egress to knowledge:                                                │
│    → AIDB :8002  → Qdrant :6333                                      │
│    → ralph-wiggum :8004 (secondary inference)                        │
└─────────────────────┬────────────────────────────────────────────────┘
                      │
┌─────────────────────▼────────────────────────────────────────────────┐
│  LAYER 5: SWITCHBOARD (proxy + profile execution :8085)               │
│                                                                      │
│  Ingress:  ANY client (IDE, coordinator, aq-*, agent CLIs)           │
│  Profiles: continue-local | default | local-agent | remote-* | ...   │
│  Hooks:    injectHints? → GET coordinator:8003/hints (if enabled)    │
│  Egress:   → llama-server :8080 (local) OR remote API (remote-*)     │
└────────────────────────┬─────────────────────────────────────────────┘
                         │
┌────────────────────────▼─────────────────────────────────────────────┐
│  LAYER 4: INFERENCE (llama-server :8080, llama-embed :8081)          │
│    Chat model: Qwen3.6-35B (12 GPU layers, CPU+Vulkan)               │
│    Embed model: used by RAG pipeline + memory semantic dedup         │
└──────────────────────────────────────────────────────────────────────┘
                         │
┌────────────────────────▼─────────────────────────────────────────────┐
│  LAYER 3: PERSISTENCE                                                │
│    PostgreSQL :5432  (interaction history, audit log, eval trends)    │
│    Redis :6379       (session cache, rate limit buckets)              │
│    Qdrant :6333      (vector collections: memories, patterns, docs)   │
│    /var/lib/nixos-ai-stack/ (PRSI queue, lessons, audit JSONL)        │
└──────────────────────────────────────────────────────────────────────┘
                         │
┌────────────────────────▼─────────────────────────────────────────────┐
│  LAYER 2: KNOWLEDGE LAYER (AIDB :8002)                               │
│    document ingest → Qdrant collections                              │
│    vector search (POST /vector/search)                               │
│    logic pattern index (Phase 52)                                    │
└──────────────────────────────────────────────────────────────────────┘
                         │
┌────────────────────────▼─────────────────────────────────────────────┐
│  LAYER 1: INFRASTRUCTURE (NixOS + systemd)                           │
│    nix/modules/services/switchboard.nix → ai-switchboard.service     │
│    nix/modules/roles/ai-stack.nix → all other ai-*.service units     │
│    nix/modules/core/options.nix → port/config single source of truth │
│    nixos-rebuild switch → deploys all code changes (no hot-reload)    │
└──────────────────────────────────────────────────────────────────────┘

┌──────────────────────────────────────────────────────────────────────┐
│  LAYER 0: HARNESS CLI + GOVERNANCE (cross-cutting, not a service)    │
│    scripts/ai/aq-*     → call coordinator REST endpoints             │
│    scripts/ai/aqd      → CLI wrapper for coordinator APIs            │
│    scripts/ai/delegate-to-* → audit-write → /api/agent-events       │
│    scripts/governance/* → validation gates (pre-commit)              │
│    scripts/automation/ → PRSI orchestrator, AIDB reindex, timers     │
│    .agents/delegation/registry.jsonl → delegation audit trail        │
└──────────────────────────────────────────────────────────────────────┘
```

### 7.2 Corrected routing flow (replacing all "lane" language)

```
TWO DIRECTIONS on the Switchboard ↔ Coordinator relationship:

Direction 1 (INGRESS — editor/IDE traffic):
  Client → Switchboard(:8085, profile=X)
    if profile.injectHints: → GET coordinator:8003/hints → inject
    → local llama:8080

Direction 2 (GENERATION BACKEND — orchestration traffic):
  Coordinator(:8003) → Switchboard(:8085)
    → local llama:8080 OR remote API

These are SEPARATE request flows. "continue-local" and "default" are
Direction 1 profiles that differ in whether they call coordinator for hints.
Neither is a "lane from switchboard to coordinator" — they are profiles
that determine switchboard BEHAVIOR, not routing destination.
```

---

## 8. Comprehensive Relational Graph — Scripts Layer

### 8.1 Key script → service endpoint map

| Script | Coordinator :8003 | AIDB :8002 | llama :8080 | Files R/W |
|--------|-------------------|------------|-------------|-----------|
| `aq-qa` | GET /api/health/*, /query, /workflow/*, /api/agent-events, /stats/delegate | GET /health | GET /health | reads config/service-endpoints.sh |
| `aq-report` | GET /api/health/layered, /api/agent-ops/status | GET /health | GET /health | writes /tmp/aq-report-* |
| `aq-hints` | GET /hints | — | — | — |
| `aq-session-start` | GET /hints, /api/memory/facts | — | — | writes .agents/scratchpad/session-context-*.md |
| `aq-commit-facts` | POST /api/memory/facts | — | POST /v1/chat/completions | reads git diff |
| `aq-crystallize` | POST /memory/crystalline/run | — | — | reads ~/.continue/sessions/*.json |
| `aq-lesson-promote` | GET /api/agent-events, POST /api/memory/facts | — | — | reads/writes lesson JSONL |
| `delegate-to-gemini` | POST /api/agent-events (via audit-write.sh) | — | — | writes .agents/delegation/registry.jsonl, outputs/ |
| `delegate-to-codex` | POST /api/agent-events (via audit-write.sh) | — | — | same |
| `delegate-to-claude` | POST /api/agent-events (via audit-write.sh) | — | — | same |
| `delegate-to-local` | POST /api/agent-events (via audit-write.sh) | — | POST /v1/chat/completions | same |
| `aqd` | proxies to coordinator sub-APIs | — | — | — |
| `aq-agent-loop` | — | — | POST /v1/chat/completions (direct to llama) | reads/writes task output files |
| `aq-prime` | GET /api/health (quick) | — | — | reads git status |

### 8.2 Governance scripts

| Script | What it validates |
|--------|-------------------|
| `tier0-validation-gate.sh` | Python syntax (py_compile), bash -n, no hardcoded secrets, no forbidden imports, repo structure |
| `repo-structure-lint.sh` | File placement contract (.agent/, .agents/plans/, .claude/commands/) |
| `smoke-ide-adapter-compat.sh` | Continue + VSCode + CLI + MCP adapter endpoints |
| `drill-rollback.sh` | 6-stage live rollback drill |
| `run-benchmark-gate.sh` | SWE eval pack (12 cases) must pass threshold |

### 8.3 Nix module → systemd service map

| Nix file | Service created | Key options wired |
|----------|-----------------|-------------------|
| `nix/modules/services/switchboard.nix` | `ai-switchboard.service` | switchboard profile catalog, hybrid URL, hints, profile cards |
| `nix/modules/roles/ai-stack.nix` | `ai-hybrid-coordinator.service`, `llama-cpp.service`, `llama-cpp-embed.service`, `ai-aidb.service`, `ai-aidb-reindex.timer`, `ai-crystallize-sessions.timer`, and ~10 others | env vars, secrets, dependencies |
| `nix/modules/core/options.nix` | (options only, no services) | ALL port numbers — single source of truth |
| `nix/home/base.nix` | HM: Continue.dev config, MCP server config for Claude | `repoPath`, `mcpServers.*` |

---

## 9. Architecture Rationalization Plan

### Priority 0 — Diagram correctness (docs only, no code change)

- [ ] Rewrite `docs/architecture/AI-STACK-ARCHITECTURE.md`:
  - Add Layer 7 (external agents) as first-class actors
  - Show bidirectional switchboard ↔ coordinator relationship with labeled arrows
  - Add ralph-wiggum, dashboard, harness CLI layer
  - Remove all "lane" language; replace with "profiles" and "request paths"
  - Date-stamp to current phase (Phase 56.9 baseline)

- [ ] Create `docs/architecture/REQUEST-ROUTING-FLOW.md`:
  - Three canonical data paths (A/B/C) with sequence diagrams
  - Profile selection decision tree with correct direction labels
  - No vendor model names — coordinator tier names only

- [ ] Create `docs/architecture/RELATIONAL-GRAPH.md`:
  - Scripts → endpoints map (sec8.1 above)
  - Nix modules → services map (sec8.3 above)
  - Knowledge loop diagram (Phase 56)
  - Memory subsystem diagram (Phases 54–55)

### Priority 1 — Naming disambiguation (docs + one code location)

- [ ] Update `docs/agent-guides/00-SYSTEM-OVERVIEW.md`:
  - Define three "agent" namespaces clearly: local-agents (Qwen executor), agent-mesh (AGI), agent_registry (coordinator runtime)
  - Clarify "hybrid" in hybrid-coordinator = dual-protocol (MCP+HTTP), NOT dual-backend

- [ ] Rename conceptually: replace "hybrid coordinator" with "orchestration brain" in all new docs (old systemd unit name unchanged)

- [ ] Update `docs/architecture/ROUTING-ARCHITECTURE-DESIGN.md` sec3 to close D-3/D-4 as resolved in Phase 56 but add the new discovered issues

### Priority 2 — Orphaned router cleanup (targeted code changes)

- [ ] Audit `ai-stack/local-orchestrator/router.py`:
  - Does any live runtime path depend on it? If not, retire
  - If yes, convert to thin adapter over `routing_contract.RoutingDecision`

- [ ] Audit `ai-stack/local-agents/task_router.py`:
  - Does `agent_executor.py` call this, or is it bypassed?
  - If bypassed: delete
  - If needed: convert to emit `RoutingDecision` from `routing_contract.py`

### Priority 3 — Duplicate module resolution (code)

- [ ] `garbage_collection.py` vs `garbage_collector.py` — grep callers, delete dead one
- [ ] `continuous_learning.py` vs `real_time_learning_engine.py` — audit symbols, merge or deprecate
- [ ] `continuous_learning_daemon.py` — if just a wrapper, fold into `continuous_learning.py`

### Priority 4 — Coordinator module structure (structural refactor)

- [ ] Execute the Phase B.2 plan from `hybrid-coordinator-module-map.md`:
  - Move tests to `tests/` subdirectory
  - Create `core/`, `workflow/`, `knowledge/`, `extensions/` subdirs
  - Add import boundary validation to tier0 gate

---

## 10. Immediate Next Slices

| Slice | Type | Owner | Scope |
|-------|------|-------|-------|
| 10.1 | Docs | Claude | Rewrite AI-STACK-ARCHITECTURE.md (Priority 0) |
| 10.2 | Docs | Claude | Create REQUEST-ROUTING-FLOW.md (Priority 0) |
| 10.3 | Docs | Claude | Create RELATIONAL-GRAPH.md (Priority 0) |
| 10.4 | Docs | Claude | Update SYSTEM-OVERVIEW.md naming (Priority 1) |
| 10.5 | Code | Codex | Audit + retire local-orchestrator/router.py (Priority 2) |
| 10.6 | Code | Codex | Audit + retire local-agents/task_router.py (Priority 2) |
| 10.7 | Code | Claude | Resolve garbage_collection duplicate (Priority 3) |
| 10.8 | Struct | Claude+Codex | Begin coordinator module directory split (Priority 4) |

Slices 10.1–10.4 are documentation-only and can be executed without nixos-rebuild.
Slices 10.5–10.8 require code changes and a rebuild cycle.

---

## 11. Agent Collaboration Evidence

| Agent | Task | Finding |
|-------|------|---------|
| Claude (orchestrator) | switchboard.nix deep-read | Confirmed bidirectional flow; profile catalog at lines 202–352; hints injection via `_get_hints()` at switchboard.nix:1548 |
| Claude (orchestrator) | http_server.py route grep | Confirmed coordinator route surfaces; `/api/agent-events`, `/control/ai-coordinator/delegate`, `/stats/delegate` all present |
| Explore subagent 1 | switchboard Nix wiring | Still running at PRD commit time — findings incorporated from orchestrator direct read |
| Explore subagent 2 | orphaned router audit | **COMPLETE** — found 4 independent routing universes; specific fixes in sec12 below |
| Explore subagent 3 | scripts connection map | **COMPLETE** — confirmed audit bridge pattern, `config/service-endpoints.sh` as port SOT for scripts, institutional memory loop; findings in sec8 |
| Gemini CLI (re-run) | architecture critique on new docs | Launched — pending |

## 12. Subagent 2 Concrete Findings — Orphaned Router Audit (file:line citations)

**Five routing systems found — not three:**

| System | Location | Status | Taxonomy |
|--------|----------|--------|----------|
| Shell front-door | `scripts/ai/local-orchestrator:303` | CANONICAL entry, but has Python fallback | OpenClaude aliases → coordinator profiles via env `AI_LOCAL_FRONTDOOR_*_PROFILE` |
| local-orchestrator Python | `ai-stack/local-orchestrator/router.py:14-20` | **ORPHANED** — fallback-live when shell fails | `AgentBackend` enum: LOCAL, QWEN, CLAUDE_SONNET, CLAUDE_OPUS (hardcoded model names) |
| local-agents executor | `ai-stack/local-agents/agent_executor.py:316` + `task_router.py:31-38` | PARTIALLY INTEGRATED | `AgentTarget` enum: LOCAL_AGENT, REMOTE_CODEX, REMOTE_CLAUDE, REMOTE_QWEN |
| aq-agent-loop | `scripts/ai/aq-agent-loop:125-148` | **ORPHANED** — coordinator on `--fallback` only | Binary local/remote; no routing contract |
| Coordinator canonical | `ai-stack/mcp-servers/hybrid-coordinator/core/routing_contract.py:40-50` | CANONICAL | `RoutingTier`: LOCAL → EDGE → REMOTE_FREE → REMOTE_PAID → REMOTE_FLAGSHIP |

**Critical nuance:** The local-orchestrator Python layer is **NOT dead code** — it is a **fallback-live** path that executes whenever the shell front door fails or in interactive/plan mode (`scripts/ai/local-orchestrator:149-189`). This is more dangerous than dead code because it can silently reintroduce obsolete routing policy under fault conditions.

**Hidden 6th taxonomy: `model_coordinator.py` inside the coordinator itself**
- `extensions/model_coordinator.py:48-113`: `ModelRole` enum (ORCHESTRATOR, REASONING, CODING, EMBEDDING, FAST_CHAT) with `ROLE_SIGNALS` dict
- Called from `llm_router_handlers.py:56` via `classify_and_route_task()` callback, wired at `http_server.py:120`
- Does NOT map directly to `RoutingTier` — `intent_classifier.py` bridges the gap but adds complexity
- This is a shadow taxonomy **inside** the canonical coordinator, creating cognitive load even for maintainers

**Specific component analysis:**

**local-orchestrator shell + Python duality** (`scripts/ai/local-orchestrator:278-320`, `router.py:326-402`)
- Shell: POST `/v1/orchestrate` to coordinator — correct
- Python fallback (`orchestrator.py:116-128`): own `TaskRouter` with `AgentBackend` (LOCAL, QWEN, CLAUDE_SONNET, CLAUDE_OPUS) — completely independent
- Remote routing: `RemoteAgentClient` at `orchestrator.py:280-328` bypasses coordinator entirely

**agent_executor routing inversion** (`agent_executor.py:251-293`, `agent_executor.py:511`, `agent_executor.py:535`)
- `route_task()` at line 316 makes binary local/remote decision FIRST
- Only then calls `/control/ai-coordinator/delegate` at line 511 (if remote chosen)
- Falls back to `/query` at line 535 if delegate fails — circumvents full coordinator pipeline
- Fix: call `/v1/orchestrate` FIRST, execute per returned `RoutingTier`

**agent_registry.py status** (resolved — not a routing concern)
- `agent_registry.py` just re-exports from `workflow/agent_registry.py:33-39` — file-backed lessons/evaluations storage
- NOT used for routing decisions; safe to leave as-is

**Specific fixes (with file:line targets):**

| Component | Fix | Target lines | Impact |
|-----------|-----|-------------|--------|
| `local-orchestrator/router.py` | Delete entirely | All | HIGH — eliminates shadow taxonomy |
| `local-orchestrator/orchestrator.py:116-128` | Wire to call `/v1/orchestrate` instead of TaskRouter | 116–128 | HIGH — closes fallback-live gap |
| `agent_executor.py:251-316` | Invert: call `/v1/orchestrate` first, execute per RoutingTier | 251–316 | HIGH — brings local-agents under coordinator control |
| `agent_executor.py:535` | Remove `/query` bypass fallback | 535 | MEDIUM — forces coordinator-path integrity |
| `task_router.py:31-38` | Convert AgentTarget → RoutingTier thin adapter | 31–38 | MEDIUM — unifies naming |
| `aq-agent-loop:125-148` | Change `--fallback` default to `True`; rename to `--bypass-coordinator` | 125–148 | MEDIUM — makes coordinator-first |
| `model_coordinator.py:48-113` | Map ROLE_SIGNALS → RoutingTier at call site; remove parallel taxonomy | 48–113 | LOW-MEDIUM — internal consistency |

**Target state:** All entry points route through `/v1/orchestrate` before any execution decision. Python fallback paths are either removed or explicitly coordinator-first.

## 12.5 Subagent 3 Additional Finding — config/service-endpoints.sh

Scripts in `scripts/ai/` do NOT hardcode port numbers — they source `config/service-endpoints.sh` at runtime. This is the **scripts-layer source of truth** for ports (parallel to `nix/modules/core/options.nix` for the Nix layer). Both must be kept in sync. Add this to RELATIONAL-GRAPH.md sec8.3.

Agent findings will be incorporated into slice execution as they complete.

## 13. Codex CLI Findings — Routing Taxonomy Audit + Code Bugs

### 13.1 Routing taxonomy per system (live/dead status)

| System | Status | Taxonomy | Verdict |
|--------|--------|----------|---------|
| `routing_contract.py` | LIVE, canonical, not universally enforced | `RoutingTier`: LOCAL → EDGE → REMOTE_FREE → REMOTE_PAID → REMOTE_FLAGSHIP | **KEEP** |
| `local-orchestrator/router.py` | **FALLBACK-LIVE** — activates on front-door failure + interactive mode | `AgentBackend`: LOCAL, QWEN, CLAUDE_SONNET, CLAUDE_OPUS; hardcoded per-backend prices at lines 301-324 | **RETIRE** |
| `local-agents/task_router.py` | **PRODUCTION-DEAD** — no real routing callers; only exports/tests | `AgentTarget`: LOCAL_AGENT, LOCAL_PLANNER, LOCAL_CHAT, REMOTE_CODEX, REMOTE_CLAUDE, REMOTE_QWEN | **RETIRE** (or thin adapter if import path needed) |
| switchboard profiles | LIVE, central surface | Abstract capability lanes; `remote-gemini` is a vendor-named **exception** | **KEEP, normalize `remote-gemini`** |

### 13.2 Naming inconsistencies (high-severity only)

| File A | Name | File B | Name | Severity |
|--------|------|--------|------|----------|
| `core/routing_contract.py:73-89` | `RoutingDecision` | `local-orchestrator/router.py:35-46` | `RouteDecision` | Medium |
| `core/routing_contract.py:40-50` | `RoutingTier.REMOTE_FLAGSHIP` | `local-orchestrator/router.py:18-20` | `CLAUDE_OPUS` | **High** |
| `core/routing_contract.py:40-50` | `RoutingTier.REMOTE_PAID` | `local-orchestrator/router.py:18-19` | `CLAUDE_SONNET` | **High** |
| `core/routing_contract.py:185-215` | `remote-free/coding/reasoning` profiles | `local-agents/task_router.py:36-38` | `REMOTE_CODEX/CLAUDE/QWEN` | **High** |
| `agent_executor.py:559-566` | `remote-reasoning/coding/free` profiles | `task_router.py:36-38` | `REMOTE_CLAUDE/CODEX/QWEN` | **High** |

**Most damaging semantic mismatch:** In the canonical system, "flagship" is a tier. In legacy systems, it is encoded as `CLAUDE_OPUS`. In the executor fallback, it is silently collapsed to `remote-reasoning` because no actual flagship profile exists. References: `routing_contract.py:253-263,279-282`, `local-orchestrator/router.py:255-279`, `agent_executor.py:559-566`.

### 13.3 Keep/Adapt/Retire with thin adapter example

| Component | Decision | Rationale |
|-----------|----------|-----------|
| `routing_contract.py` | KEEP | Only correct contract; abstract tiers, env-sourced costs, unified decision object |
| `local-orchestrator/router.py` | **RETIRE** | Vendor-named backends, hardcoded pricing, divergent classification — still reachable on failure |
| `local-agents/task_router.py` | **RETIRE** | Production-dead taxonomy; no operational value in keeping a second universe |
| `agent_executor.py` routing logic | **ADAPT** | Executor is needed; its private binary router is not. Consume canonical `RoutingDecision` from coordinator |
| switchboard profiles | KEEP + normalize `remote-gemini` | Live and mostly abstract; one naming blemish |

**Thin adapter pattern (if compatibility transition needed):**
```python
from routing_contract import RoutingDecision, RoutingTier, profile_for_tier

class TaskRouter:
    async def route(self, objective: str, **context) -> RoutingDecision:
        raw = await coordinator_client.orchestrate(
            prompt=objective, context=context, generate_response=False,
        )
        tier = RoutingTier(raw["tier"])
        return RoutingDecision(
            tier=tier,
            profile=raw.get("profile") or profile_for_tier(tier),
            model_alias=raw.get("model_alias", ""),
            task_type=raw.get("task_type", "unknown"),
            reason=raw.get("reason", "coordinator_route"),
            confidence=float(raw.get("confidence", 0.0)),
        )
```
**Rule:** Callers may keep an adapter, but no adapter may invent a second routing universe.

### 13.4 New bugs/risks not in sec12

**BUG-C1: `REMOTE_FLAGSHIP` is a phantom tier** (`routing_contract.py:253-263,266-286`)
- `profile_for_tier()` maps `REMOTE_FLAGSHIP` → `remote-reasoning`
- Claude-opus aliases also collapse to `remote-reasoning`
- The type system promises a highest tier the runtime cannot actually express
- Callers requesting "flagship" receive "reasoning" with no downgrade signal

**BUG-C2: Remote health probe treats auth failures as healthy** (`agent_executor.py:654-663`)
- `_probe_remote_fallback()` returns healthy for any status < 500, including 401, 403, 404
- A broken auth config or wrong endpoint is considered "healthy"
- Executor routes to remote → fails later on actual delegate call → adds latency + obscures real fault

**BUG-C3: "Can you implement X" misclassified as QUERY → forced local** (`local-orchestrator/router.py:97-108,139-143`)
- Query regex includes `^can (you|i|we)` — matches "Can you implement OAuth?"
- Routes to `QUERY` category with confidence 0.9 → forced LOCAL
- Concrete correctness bug: most natural implementation prompt forms biased to cheapest path

**BUG-C4: Hardcoded service endpoints in LocalAgentExecutor** (`agent_executor.py:201-207`)
- `llama_endpoint="http://127.0.0.1:8080"` hardcoded
- `fallback_endpoint="http://127.0.0.1:8003"` hardcoded
- Violates port SSOT rule; creates independent failure mode from Nix-driven system

**RISK-C5: Legacy fallback reactivates exactly when canonical path fails** (`scripts/ai/local-orchestrator:303-320`)
- During coordinator outage, shell falls back to legacy Python orchestrator (not error or retry)
- Means: **worst routing behavior occurs under worst observability conditions**
- Confirmed independently by both Explore subagent 2 and Codex

### 13.5 New slices from Codex findings

| Slice | Type | Priority | Description |
|-------|------|----------|-------------|
| 13.1 | Code | P0 | Fix `_probe_remote_fallback()` to treat 4xx as unhealthy (`agent_executor.py:654-663`) |
| 13.2 | Code | P0 | Add `REMOTE_FLAGSHIP` dedicated profile to switchboard + routing_contract (or explicitly document downgrade) |
| 13.3 | Code | P1 | Fix hardcoded endpoints in `LocalAgentExecutor` (`agent_executor.py:201-207`) — read from env vars |
| 13.4 | Code | P1 | Fix "Can you implement" misclassification in legacy router (retire or patch regex at `router.py:97-108`) |
| 13.5 | Code | P1 | Rename `remote-gemini` profile to `remote-synthesis` or `remote-discovery` (abstract, not vendor) |
| 13.6 | Code | P2 | Shell local-orchestrator: fail-closed on coordinator outage, not fallback-to-legacy (`local-orchestrator:303-320`) |

## 14. Gemini CLI Findings — Senior Architecture Critique (2026-05-15)

**Overall verdict:** "Documentation has caught up to technical debt. We now have a clear map of a complex, slightly fragile system. Priority must shift from documenting complexity to **decoupling the services**."

### 14.1 Implementation bugs found (switchboard.nix)

**BUG-1: Stale hints across multi-turn conversations** (`switchboard.nix:~1555`)
- `_get_hints()` fetches based on **first user message only**, not latest
- In a 20-turn conversation, hints remain locked to the initial query even if topic shifts (e.g., "Fixing Nix" → "Python performance")
- Architecture chose cache-locality over hint-relevance (changing to latest_user would bust llama-server KV cache every turn since system prompt prefix changes)
- **Not documented** — feels like an undocumented trade-off, currently reads as a bug
- **Recommendation:** Document this trade-off explicitly in switchboard.nix and ROUTING-FLOW docs; add `--hints-mode=first|latest` toggle

**BUG-2: Hint append to last system message** (`switchboard.nix:~1572`)
- Hints appended to the LAST system message in the payload
- If a client sends its own system message AFTER the profile card, hints are injected there, potentially breaking the client's prompt structure
- **Recommendation:** Always inject hints as the FIRST system message, not appended to last

**GAP-1: `default` profile missing-header fallback not documented**
- When `x-ai-profile` header is absent, the request falls through to `default` profile
- This is implied but never stated explicitly in docs
- **Fix:** Add one sentence to REQUEST-ROUTING-FLOW.md: "If no `x-ai-profile` header is present, `default` profile is applied."

**GAP-2: `forceProvider=null` auto-resolution undocumented**
- `default` profile has `forceProvider=null` (auto)
- "auto" defaults to `local` when `REMOTE_URL` is unset — which is the out-of-the-box state
- **Fix:** Document explicitly in the profile table

**INCONSISTENCY-1: Auth header naming in docs**
- `AI-STACK-ARCHITECTURE.md` states coordinator requires `hybrid_coordinator_api_key`
- `switchboard.nix` sends `X-API-Key` when contacting coordinator for hints
- `auth_middleware.py` accepts both, but this is undocumented
- **Risk:** Config/security trap when debugging auth failures

### 14.2 Architectural risks confirmed by Gemini

| Risk | Severity | Gemini description |
|------|----------|-------------------|
| Switchboard Python in Nix string | HIGH | "2000+ line Nix-script-mulch — impossible to unit test Python in isolation; any Python f-string failure requires Nix rebuild" → Move to `pkgs.writers.writePython3Bin` |
| Concurrency starvation | HIGH | "`LOCAL_CONCURRENCY=1` + 503 busy-fail — single PRSI background task can lock developer out of IDE for 5 minutes; lacks priority lane for human-interactive traffic" |
| Cyclic dependency brittleness | MEDIUM | "Switchboard→Coordinator(hints)→Switchboard(LLM) = distributed monolith; if hints_engine hangs, IDE hangs for `HINTS_TIMEOUT_S` on EVERY request" |

### 14.3 Gemini naming recommendations

- "Hybrid Coordinator" misnomer causes 90% of confusion → rename to `ai-orchestrator` or `ai-brain` in docs (systemd unit unchanged)
- Rename `ai-stack/local-agents/` directory to `agent-executors/` to disambiguate from `local-agent` profile and `agent_registry`

### 14.4 New slices from Gemini findings

| Slice | Type | Priority | Description |
|-------|------|----------|-------------|
| 14.1 | Docs | P1 | Document `default` as missing-header fallback + `forceProvider=null` auto-resolution |
| 14.2 | Docs | P1 | Document stale-hints trade-off explicitly in routing docs |
| 14.3 | Docs | P1 | Fix auth header naming inconsistency (`hybrid_coordinator_api_key` vs `X-API-Key`) |
| 14.4 | Code | P1 | Fix hint append to LAST system message — inject as FIRST instead |
| 14.5 | Infra | P2 | Extract switchboard Python to standalone file (out of Nix string) using `pkgs.writers.writePython3Bin` |
| 14.6 | Code | P2 | Add priority lane for IDE traffic over background agent tasks (avoid LOCAL_CONCURRENCY=1 starvation) |
| 14.7 | Infra | P2 | Add circuit-breaker on hints fetch (switchboard should degrade gracefully if coordinator hints hang, not block IDE) |
| 14.8 | Naming | P3 | Rename `ai-stack/local-agents/` → `agent-executors/` in docs and eventually in code |

## 15. Explore Subagent 1 Findings — Switchboard Nix Wiring Deep-Dive

### 15.1 Critical: Coordinator → Switchboard call uses `default` profile → circular hints risk

When the coordinator calls the switchboard for LLM generation (Path B), it sends **no `x-ai-profile` header**. The switchboard therefore applies the `default` profile, which has `injectHints=true`. This means:

```
Coordinator:8003 → POST /v1/chat/completions → Switchboard:8085 (no profile header → default profile)
  → Switchboard: injectHints=true → GET coordinator:8003/hints  ← BACK TO COORDINATOR
```

**This is a circular dependency:** coordinator calls switchboard, which calls coordinator for hints. The hints call is a `GET /hints` (read-only, no LLM involvement), so it doesn't cause an infinite loop, but it:
- Adds a coordinator round-trip to EVERY coordinator-initiated LLM call
- Means the coordinator is fetching hints for its own requests — hints that were designed for human-initiated IDE traffic
- If the coordinator's hints endpoint is slow or down, it blocks its own LLM calls

**Fix:** Coordinator should set `x-ai-profile: local-agent` or a new `x-coordinator-internal` profile that disables hints injection when calling the switchboard as a backend.

### 15.2 `continue-local` UX bug: no forced streaming

`continue-local` profile does not force streaming (`stream=true`). Inference on this hardware takes ~90–120 seconds. Without forced streaming, the IDE shows a blank screen for the full duration, then the response appears all at once.

**Fix:** Set `stream=true` by default for `continue-local` profile (and all local profiles) in the switchboard Python logic.

### 15.3 Remote budget fallback is silent

When `SWB_REMOTE_DAILY_TOKEN_CAP` is exceeded, remote-profile requests silently fall back to local inference. The user receives an HTTP 200 with a local response — no indication that the fallback occurred.

**Fix:** Add `X-AI-Fallback: budget-exceeded` response header and/or a top-of-response note when fallback activates.

### 15.4 New slices from subagent 1 findings

| Slice | Type | Priority | Description |
|-------|------|----------|-------------|
| 15.1 | Code | **P0** | Coordinator must tag its switchboard calls with a non-hints-injecting profile (e.g., `x-ai-profile: local-agent` or new `internal` profile) to break circular hints fetch |
| 15.2 | Code | P1 | Force `stream=true` for all local profiles in switchboard to eliminate 90s blank-screen UX |
| 15.3 | Code | P2 | Add `X-AI-Fallback` response header + logging when remote budget fallback activates |
