# Agent Routing & Harness Interconnection Design

**Date:** 2026-04-26  
**Status:** Active  
**Scope:** switchboard, hybrid-coordinator, local-orchestrator, local-agents

---

## 1. Executive Summary

The harness has already partially converged on a coordinator-owned routing model, but the documentation and a few compatibility modules still describe the older world where multiple routers make independent policy decisions.

The current repo evidence shows:

- `scripts/ai/local-orchestrator` is now the primary human-facing CLI front door and posts to `POST /v1/orchestrate` by default.
- `ai-stack/mcp-servers/hybrid-coordinator/routing_contract.py` already exists and acts as the canonical tier/profile registry for coordinator-side routing.
- `ai-stack/local-orchestrator/router.py` and `ai-stack/local-agents/task_router.py` still contain standalone routing enums and heuristics that are not the canonical authority for live harness ingress.
- `ai-stack/local-agents/agent_executor.py` previously bypassed coordinator delegation on remote fallback by posting directly to `/query`.

This document updates the design target:

1. The **hybrid coordinator owns routing policy**.
2. The **switchboard owns profile execution**.
3. The **shell front door and agent layers must consume coordinator profiles**, not invent parallel backend taxonomies.
4. Legacy local routers are **compatibility layers to absorb or retire**, not peer routing authorities.

---

## 2. Repo-Grounded Current State

### Canonical ingress and execution paths

```
┌──────────────────────────────────────────────────────────────┐
│ Human / agent entrypoints                                   │
│                                                              │
│ Continue IDE / VSCode                                        │
│     ↓                                                        │
│ switchboard (:8085)                                          │
│     ↓                                                        │
│ local or remote profile execution                            │
│                                                              │
│ local-orchestrator CLI                                       │
│     ↓                                                        │
│ POST /v1/orchestrate on hybrid-coordinator (:8003)           │
│     ↓                                                        │
│ route_aliases.py -> ai_coordinator -> switchboard profiles   │
│                                                              │
│ aq-* CLIs / harness tooling                                  │
│     ↓                                                        │
│ /workflow/*, /hints, /query, /control/* on coordinator       │
└──────────────────────────────────────────────────────────────┘
```

### Live coordinator-owned routing surfaces

| Surface | Current role | Owner |
|--------|--------------|-------|
| `/v1/orchestrate` | Canonical front door for route aliases like `Explore` and `Reasoning` | `http_server.py` + `route_aliases.py` + `ai_coordinator.py` |
| `/control/ai-coordinator/delegate` | Canonical bounded remote delegation path | `ai_coordinator.py` |
| `/query` | Retrieval + synthesis lane, not the primary orchestration front door | `route_handler.py` + `search_router.py` + `task_classifier.py` |
| `/control/llm/execute` | Legacy/auxiliary routed execution lane still backed by `llm_router.py` | `llm_router.py` |

### Compatibility / legacy layers

| Module | Actual status |
|-------|----------------|
| `scripts/ai/local-orchestrator` | Active front door, but already coordinator-first |
| `ai-stack/local-orchestrator/router.py` | Legacy Python routing policy used by fallback/interactive path, not canonical ingress authority |
| `ai-stack/local-agents/task_router.py` | Standalone router taxonomy not used by `agent_executor.py` remote fallback path |
| `ai-stack/local-agents/agent_executor.py` | Active local execution path; now should delegate remote work through coordinator |

---

## 3. Confirmed Drift and Design Problems

### D-1: Documentation was ahead in some places and behind in others

The earlier design review correctly identified duplicate routing logic, but it became stale after:

- `routing_contract.py` was added to coordinator code,
- `scripts/ai/local-orchestrator` was switched to `/v1/orchestrate`,
- `llm_router.py` fixes landed for advisor guidance consumption and profile-contract usage.

The design problem is no longer "build a canonical contract from scratch." It is now "finish migrating callers onto the canonical contract and stop presenting compatibility routers as equal peers."

### D-2: Local router taxonomies still diverge from coordinator profiles

The stack still carries parallel names:

| Layer | Taxonomy |
|------|----------|
| Coordinator contract | `default`, `remote-free`, `remote-coding`, `remote-reasoning`, `local-tool-calling`, etc. |
| `local-orchestrator/router.py` | `AgentBackend.LOCAL`, `QWEN`, `CLAUDE_SONNET`, `CLAUDE_OPUS` |
| `local-agents/task_router.py` | `REMOTE_CODEX`, `REMOTE_CLAUDE`, `REMOTE_QWEN` |

Those local taxonomies are acceptable only if they are treated as adapters onto coordinator profiles. They should not remain independent authorities.

### D-3: `local-agents` previously bypassed coordinator delegation

Before this design pass, `ai-stack/local-agents/agent_executor.py` remote fallback posted directly to `/query`. That path skipped:

- coordinator profile selection,
- consistent remote delegation metadata,
- the same bounded delegation lane used elsewhere in the harness.

That behavior made local agents less interconnected than the rest of the stack.

### D-4: The old Python local orchestrator path is now a fallback, not the product direction

`scripts/ai/local-orchestrator` only uses the Python `LocalOrchestrator` path after front-door failure. The shell CLI therefore already tells us the intended architecture:

- front-door alias routing is primary,
- legacy in-process orchestration is compatibility fallback.

The architecture docs should say that directly.

---

## 4. Target Architecture

### Routing ownership

Use this ownership model consistently:

| Concern | Canonical owner |
|--------|------------------|
| Route aliases | `config/route-aliases.json` + `route_aliases.py` |
| Tier/profile registry | `routing_contract.py` |
| Front-door orchestration | `/v1/orchestrate` |
| Remote delegation | `/control/ai-coordinator/delegate` |
| Profile execution | switchboard |
| Retrieval classification | `task_classifier.py` for `/query` lane |

### Design rule

All user-facing or agent-facing callers should reduce to:

1. choose a coordinator profile or alias,
2. call coordinator front-door or delegate surface,
3. let switchboard execute the profile,
4. capture metrics and feedback in the coordinator-owned path.

They should not:

- invent new remote backend names,
- map directly to vendor/model assumptions,
- bypass the coordinator when asking for remote execution.

### Updated architecture map

```
┌──────────────────────────────────────────────────────────────┐
│ Shared contract + profile registry                           │
│   ai-stack/mcp-servers/hybrid-coordinator/routing_contract.py│
└──────────────────────────────┬───────────────────────────────┘
                               │
              ┌────────────────┼────────────────┐
              ▼                ▼                ▼
      /v1/orchestrate      /control/...       /query
      front door           delegate           retrieval lane
              │                │                │
              └────────────┬───┴────────────────┘
                           ▼
                     ai_coordinator
                           ▼
                      switchboard
                           ▼
                  local / remote profiles

Compatibility layers:
- scripts/ai/local-orchestrator -> must call /v1/orchestrate first
- local-agents executor -> must call /control/ai-coordinator/delegate for remote work
- local Python routers -> adapt or retire
```

---

## 5. Design Passes

### Pass 1: Make the docs match the product

Decision:

- Treat `local-orchestrator` shell CLI plus `/v1/orchestrate` as the canonical front door.
- Treat `local-orchestrator/router.py` and `local-orchestrator/orchestrator.py` as compatibility fallback internals.
- Treat `local-agents/task_router.py` as a non-canonical standalone router until it is either adapted or removed.

Acceptance signals:

- docs stop presenting isolated routers as equal peers,
- operators can identify one authoritative ingress path.

### Pass 2: Route all remote execution through coordinator delegation

Decision:

- Any layer that wants remote help should use `/control/ai-coordinator/delegate` with a coordinator profile.
- `/query` remains valid for retrieval/synthesis behavior, but not as the primary remote fallback API for local-agent execution.

Implemented in this pass:

- `ai-stack/local-agents/agent_executor.py` now selects a coordinator profile and attempts `/control/ai-coordinator/delegate` first.
- It preserves a `/query` compatibility fallback if the delegate lane fails.

### Pass 3: Collapse duplicate routing authority

Recommended next action:

- either adapt `local-orchestrator/router.py` and `local-agents/task_router.py` into thin translators that emit coordinator profiles,
- or retire them once no runtime path depends on their standalone heuristics.

The important point is not whether those modules survive; it is whether they continue to own routing policy independently. They should not.

### Pass 4: Externalize switchboard Python from `switchboard.nix`

This remains a valid design goal.

Status:

- still not complete,
- still worth doing for testability and cleaner diffs,
- no longer the first-order integration blocker.

---

## 6. Keep / Integrate / Remove Matrix

| Component | Decision | Rationale |
|----------|----------|-----------|
| `routing_contract.py` | Keep and expand | Already the best canonical profile/tier contract |
| `route_aliases.py` + `config/route-aliases.json` | Keep | Clean front-door abstraction |
| `/v1/orchestrate` | Keep as primary ingress | Human-facing and harness-friendly |
| `/control/ai-coordinator/delegate` | Keep as primary remote execution API | Unifies delegation behavior |
| `task_classifier.py` | Keep | Good bounded classifier for retrieval lane |
| `local-orchestrator/router.py` | Integrate or retire | Acceptable only as adapter/fallback |
| `local-agents/task_router.py` | Integrate or retire | Not canonical, currently detached from active executor fallback |
| direct `/query` remote fallback from local agents | Remove as primary path | Use only as compatibility fallback |

---

## 7. Immediate Implementation Priorities

| Priority | Item | Status |
|----------|------|--------|
| P0 | coordinator contract remains canonical | already true |
| P0 | local-agent remote fallback uses coordinator delegate first | implemented in this pass |
| P0 | architecture docs reflect actual ingress ownership | implemented in this pass |
| P1 | convert legacy local routers into thin profile adapters | next |
| P1 | add explicit profile validation anywhere local layers still emit remote names | next |
| P2 | externalize switchboard Python from Nix string | later |
| P2 | feed routing metrics back into decision logic | later |

---

## 8. Files Changed or Relevant

Primary implementation files:

- `ai-stack/local-agents/agent_executor.py`
- `ai-stack/mcp-servers/hybrid-coordinator/routing_contract.py`
- `ai-stack/mcp-servers/hybrid-coordinator/route_aliases.py`
- `ai-stack/mcp-servers/hybrid-coordinator/http_server.py`
- `scripts/ai/local-orchestrator`

Relevant docs:

- `docs/architecture/front-door-routing.md`
- `docs/operations/ai-stack-tooling-exposure.md`
- `docs/operations/AI-AGENT-SURFACE-MATRIX.md`

---

## 9. Reviewer Notes

This design pass intentionally does not remove legacy Python orchestration modules yet. The safer sequence is:

1. make coordinator-first routing explicit,
2. move active callers onto coordinator profiles,
3. then delete or shrink any remaining duplicate routers.

That preserves current behavior while steadily reducing architectural ambiguity.
