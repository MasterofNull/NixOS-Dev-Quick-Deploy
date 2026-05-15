# Request Routing Flow
**Status:** Active — replaces stale "lanes" language in AI-STACK-ARCHITECTURE.md
**Phase baseline:** 56.9 (2026-05-15)
**Owner:** Architecture

---

## The Core Confusion — Resolved

> "What are the separate continue-local and default profile lanes from the switchboard to the hybrid coordinator?"

**There are no lanes from the switchboard to the coordinator.** This misreads the data flow direction. The correct model:

- **Switchboard → Coordinator:** Only for hints injection (`GET /hints`). Only for profiles where `injectHints=true`. This is a one-call sidecar fetch, not a routing lane.
- **Coordinator → Switchboard:** For LLM generation when the coordinator needs to produce text. The coordinator uses the switchboard as its LLM execution backend.

These are two independent, bidirectional relationships on the same pair of services. They are not the same request path.

---

## Three Canonical Request Paths

### Path A — IDE / Editor Direct Chat

```
┌──────────────────────────────────────────────────────────────┐
│ Client: Continue.dev IDE, Claude Code Extension              │
│         Any OpenAI-compatible caller                         │
└──────────────────────┬───────────────────────────────────────┘
                       │ POST /v1/chat/completions
                       │ Header: x-ai-profile: <profile>
                       ▼
┌──────────────────────────────────────────────────────────────┐
│ Switchboard :8085                                            │
│                                                              │
│  1. Read x-ai-profile header → look up profile in catalog   │
│  2. Apply token limits (maxInputTokens, maxMessages)         │
│  3. Apply loop detection (last 3 turns similarity check)     │
│  4. [if profile.injectHints=true]                            │
│       GET coordinator:8003/hints?q=<first user message>      │
│       ← hints string returned                               │
│       inject as system message prefix                        │
│  5. Apply profile card as system message (if enabled)        │
│  6. Forward to backend                                       │
└──────────────────────┬───────────────────────────────────────┘
                       │
           ┌───────────┴─────────────┐
           ▼                         ▼
   forceProvider=local          forceProvider=remote
   (or auto→local when          (remote-* profiles)
    REMOTE_URL unset)
           │                         │
   POST /v1/chat/completions    POST to remote API
   llama-server :8080           (OpenRouter, etc.)
```

**Profile behavior table:**

| Profile | injectHints | forceProvider | Coordinator contact | Typical caller |
|---------|-------------|---------------|---------------------|----------------|
| `continue-local` | **no** | local | **none** | Continue.dev inline chat |
| `default` | **yes** | auto | GET /hints only | Untagged callers, Claude Code ext |
| `local-agent` | **yes** | local | GET /hints only | Agent tasks, PRSI, harness ops |
| `embedded-assist` | no | local | none | Compact Q&A |
| `local-tool-calling` | no | local | none | Tool execution |
| `embedding-local` | no | local (embed) | none | RAG embeddings |
| `remote-*` | no | remote | **none** | Remote inference |

**Key insight:** `continue-local` and `default` differ in ONE way — hints injection. Neither creates a "lane to the coordinator." The coordinator contact, when it occurs, is a GET sidecar call to `/hints`, not a routing lane.

**forceProvider resolution:** `forceProvider=null` (or unset) means **auto** — the switchboard routes to local when `REMOTE_URL` is unset (the default out-of-the-box configuration). With `REMOTE_URL` set, `auto` checks the remote budget and falls back to local when the budget is exhausted. Setting `forceProvider=remote` makes the profile always target remote; `forceProvider=local` always targets local regardless of `REMOTE_URL`.

**Stale hints (intended behavior):** When `injectHints=true`, hints are fetched using the **first user message** in the conversation and locked for the lifetime of that request. This is intentional — locking hints to the first message preserves KV-cache locality across turns on the local model. The same cache slot is reused when the prompt prefix is stable, reducing per-turn latency significantly. If the query context shifts mid-conversation, the next request's first user message will produce fresh hints.

---

### Path B — Orchestration & Agent Tasks

```
┌──────────────────────────────────────────────────────────────┐
│ Client: aq-* CLIs, aqd, MCP tools, REST callers              │
│         Claude Code via MCP, direct HTTP                     │
└──────────────────────┬───────────────────────────────────────┘
                       │
         ┌─────────────┼─────────────────────────────┐
         ▼             ▼                             ▼
  POST /query   POST /v1/orchestrate          POST /workflow/*
  (retrieval +  (front-door route aliases:    (DAG execution,
   synthesis)    Explore, Reasoning, Code)     planning, replay)
         │             │                             │
         └─────────────┼─────────────────────────────┘
                       ▼
┌──────────────────────────────────────────────────────────────┐
│ Coordinator :8003 — internal routing                         │
│                                                              │
│  route_handler.py                                            │
│    → task_classifier.py (classify task type)                 │
│    → search_router.py (multi-source search if needed)        │
│    → RAG: Qdrant :6333 + AIDB :8002                          │
│    → IntentClassifier → RAG augmentor                        │
│    → hints_engine.py (context hints for this query)          │
│    → tooling_manifest.py (tool injection)                    │
│    → memory_broker.py (working memory check)                 │
│                                                              │
│  ai_coordinator.py                                           │
│    → POST /control/ai-coordinator/delegate (remote work)     │
│                                                              │
│  llm_router.py / llm_client.py                               │
│    → POST /v1/chat/completions → Switchboard :8085           │
│                                  → llama :8080 or remote     │
└──────────────────────────────────────────────────────────────┘
                       │
           Switchboard :8085 (as backend, not as ingress)
                       │
           llama-server :8080 or remote API
```

---

### Path C — Agent Delegation (External AI Agents)

```
┌──────────────────────────────────────────────────────────────┐
│ External Agents:                                             │
│   Claude Code CLI          → direct REST + MCP tools         │
│   Codex CLI                → scripts/ai/delegate-to-codex    │
│   Gemini CLI               → scripts/ai/delegate-to-gemini   │
│   Local Qwen (aq-agent-loop) → direct llama :8080            │
└──────────────────────┬───────────────────────────────────────┘
                       │
         scripts/ai/delegate-to-*
           → sources scripts/ai/lib/audit-write.sh
           → POST /api/agent-events to coordinator
                       │
                       ▼
┌──────────────────────────────────────────────────────────────┐
│ Coordinator :8003 /api/agent-events                          │
│   → tool-audit.jsonl (append)                                │
│   → ContinuousLearning (lesson extraction)                   │
│   → lesson registry (/var/lib/nixos-ai-stack/lessons/)        │
│                                                              │
│ /control/ai-coordinator/delegate                             │
│   → bounded remote delegation (remote model or local)        │
│                                                              │
│ MCP tools (Claude Code specific):                            │
│   harness_health, get_hints, hybrid_search,                  │
│   store_memory, recall_memory, get_working_memory, ...       │
└──────────────────────────────────────────────────────────────┘
```

**Note:** `aq-agent-loop` (local Qwen executor) posts DIRECTLY to llama :8080, bypassing the switchboard and coordinator. This is intentional for low-latency local tool execution. It does NOT go through the coordinator routing stack.

---

## Knowledge & Memory Loop (Phase 56)

```
Work artifact / agent action
    ↓
POST /api/agent-events (coordinator ingest)
    ↓
ContinuousLearning / real_time_learning_engine
    ↓
lesson registry (JSONL on disk)
    ↓
aq-lesson-promote (human review gate)
    ↓
aq-session-start (next session hydration)
    ↓
next agent session inherits promoted lessons
    ↓
(loop — institutional memory accumulates)
```

**Memory subsystem (Phases 54–55):**
```
Any write path → memory_broker.py (dedup via embedding similarity)
    ├─ POST /api/memory/facts → PostgreSQL + Qdrant
    ├─ POST /memory/supersede → mark old fact superseded
    └─ POST /memory/crystalline/run → distill session contexts

drift_analyzer.py
    → GET /api/traces/drift → detect query distribution shift
    → triggers agent-ops profile if drift_alert_threshold=0.7 exceeded
```

---

## What Calls What — Quick Reference

```
Coordinator :8003 CALLS:
  → Switchboard :8085 (LLM generation backend)
  → AIDB :8002 (document/knowledge search)
  → Qdrant :6333 (vector search direct)
  → PostgreSQL :5432 (history, audit, eval)
  → Redis :6379 (session cache)
  → ralph-wiggum :8004 (secondary inference, POST /task)

Switchboard :8085 CALLS:
  → Coordinator :8003 (GET /hints ONLY, when injectHints=true)
  → llama-server :8080 (local LLM generation)
  → remote API (when forceProvider=remote and REMOTE_URL set)
  → llama-embed :8081 (semantic prune, loop detection similarity)

AIDB :8002 CALLS:
  → Qdrant :6333 (vector storage)
  → PostgreSQL :5432 (document metadata)
```

---

## Anti-Patterns to Avoid in Docs

| Wrong | Correct |
|-------|---------|
| "continue-local lane FROM switchboard TO coordinator" | "continue-local profile: switchboard sends to local llama, no coordinator contact" |
| "default lane from switchboard to coordinator" | "default profile: switchboard fetches hints from coordinator GET /hints, then sends to local llama" |
| "hybrid coordinator routes between local and remote" | "switchboard routes between local and remote; coordinator orchestrates workflow and calls switchboard as backend" |
| "local-orchestrator is the orchestrator" | "local-orchestrator is a CLI front-door; the coordinator is the actual orchestrator" |
| "local-agents are agents in the coordinator" | "local-agents (ai-stack/local-agents/) is the Qwen executor loop, separate from coordinator's agent_registry" |
