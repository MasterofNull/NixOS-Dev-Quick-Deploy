# Agent Routing & Switchboard Architecture — Design Review

**Date:** 2026-04-25
**Status:** Active
**Scope:** hybrid-coordinator routing stack, switchboard proxy, local-orchestrator router

---

## 1. Executive Summary

The system has **four independent routing implementations** that evolved in parallel with no shared contract. They can produce contradictory decisions for the same input, have no feedback loops between them, and accumulate technical debt at each integration layer. This document maps the current state, identifies concrete bugs and design defects, and proposes an incremental path to a coherent routing architecture.

---

## 2. Current Architecture Map

```
┌─────────────────────────────────────────────────────────┐
│  Client Paths                                           │
│                                                         │
│  Continue IDE / VSCode                                  │
│       ↓                                                 │
│  Switchboard (port 8085) — inline Python in .nix        │
│  OpenAI-compatible proxy, profile-based routing         │
│       ↓                   ↓                             │
│  local llama.cpp      remote (OpenRouter / API)         │
│                                                         │
│  aq-* CLIs / harness tools                              │
│       ↓                                                 │
│  hybrid-coordinator (port 8003)                         │
│  ├── /query  ─────────────────────────────────┐         │
│  │    route_handler.route_search()            │         │
│  │    task_classifier.classify()              │         │  ← LIVE PATH A
│  │    search_router.select_backend()          │         │
│  │         ↓ "local"  ↓ "remote"             │         │
│  │    llama_cpp   switchboard_client          │         │
│  │                                            │         │
│  ├── /control/llm/execute ──────────────┐     │         │
│  │    llm_router.execute_with_advisor() │     │         │  ← LIVE PATH B
│  │    llm_router.route_task()           │     │         │
│  │         ↓ tier-based keyword match   │     │         │
│  │    _execute_local()                  │     │         │
│  │    _execute_via_coordinator()        │     │         │
│  │                                      │     │         │
│  └── /v1/orchestrate ────────────────┐  │     │         │
│       ai_coordinator profile routing │  │     │         │  ← LIVE PATH C
│       _REMOTE_AVAIL_CACHE            │  │     │         │
│                                      │  │     │         │
│  local-orchestrator (standalone)     │  │     │         │
│    local-orchestrator/router.py      │  │     │         │  ← ISOLATED
│    AgentBackend enum (no HTTP)       │  │     │         │
│                                      │  │     │         │
│  local-agents (standalone)           │  │     │         │
│    local-agents/task_router.py       │  │     │         │  ← ISOLATED
│    AgentTarget enum (no HTTP)        │  │     │         │
└─────────────────────────────────────────────────────────┘
```

### Live Request Paths

| Path | Entry Point | Classifier | Decision | Output |
|------|-------------|-----------|----------|--------|
| A — `/query` | `route_handler.route_search()` | `task_classifier.classify()` regex heuristic | `search_router.select_backend()` → `"local"` or `"remote"` | llama.cpp or switchboard_client |
| B — `/control/llm/execute` | `llm_router.execute_with_advisor()` | `llm_router.classify_complexity()` keyword-set | `AgentTier` enum | `_execute_local()` or `_execute_via_coordinator()` |
| C — `/v1/orchestrate` | `http_server.py` orchestrate handler | profile string in payload | `_coordinator_prefer_local()`, `_is_remote_profile()` | ai_coordinator profile execution |

### Isolated Routers (Not on Live HTTP Paths)

- `local-orchestrator/router.py` — `TaskRouter` w/ `AgentBackend` enum. Used by local-orchestrator process only, no feedback to coordinator.
- `local-agents/task_router.py` — `TaskRouter` w/ `AgentTarget` enum. Used by local-agents process only, no feedback to coordinator.

---

## 3. Confirmed Bugs

### BUG-1: `advisor_guidance` is computed but never consumed

**File:** `llm_router.py`, `execute_with_advisor()` (line ~574)
**Severity:** Medium — advisor consultation wastes tokens/time with zero effect

```python
# execute_with_advisor():
advisor_guidance = await self._consult_advisor(decision_point, tier.value, model)
task["advisor_guidance"] = advisor_guidance   # ← injected into task dict

# Then calls:
result = await self.execute_with_routing(task)

# But execute_with_routing() → _execute_local() / _execute_free() / _execute_paid()
# → _build_prompt(task) — does NOT read task["advisor_guidance"]
```

The advisor response is stored in `task["advisor_guidance"]` but `_build_prompt()` only reads `task["description"]` and `task["context"]`. The advisor call adds latency and cost with no observable effect.

**Fix:** `_build_prompt()` must read `task.get("advisor_guidance")` and prepend it to the context section.

---

### BUG-2: Use-after-close in `get_advisor_metrics()`

**File:** `llm_router.py`, `get_advisor_metrics()` (lines 1056–1063)
**Severity:** High — raises `ProgrammingError: Cannot operate on a closed database`

```python
conn.close()      # ← line 1056

# 7 lines later:
total_tasks = conn.execute(   # ← BUG: connection already closed
    "SELECT COUNT(*) FROM routing_decisions"
).fetchone()[0] if total_consultations > 0 else 0
```

**Fix:** Move the `total_tasks` query before `conn.close()`, or open a new connection.

---

### BUG-3: `classify_complexity` in `llm_router.py` and `task_classifier.classify()` are dual-classifiers with no coordination

**File:** `llm_router.py::classify_complexity()` (line 163) vs `task_classifier.classify()` (standalone module)
**Severity:** Medium — two systems route the same query differently depending on which path is taken

`llm_router.classify_complexity()` uses raw keyword set membership (string `in` dict). `task_classifier.classify()` uses compiled regex patterns with context/token awareness. They share no signal. Path A uses `task_classifier`; Path B uses `llm_router.classify_complexity`. A query like "briefly explain how does X work" would be routed to `remote_required=False` by `task_classifier` (bounded reasoning detection) but to `AgentTier.FREE` by `llm_router` (matched `sub_agent_tasks` keyword "create").

---

### BUG-4: `_execute_free()` routes "qwen-coder" through coordinator but profile names don't align

**File:** `llm_router.py` line 317
```python
profile = "remote-coding" if "coder" in model else "remote-free"
```

The coordinator delegates based on profile names. These profiles are defined in `switchboard.nix` as `[profile-card:remote-coding]` etc. There is no validation that the profile name passed from `llm_router` actually exists in the switchboard config. If the profile name drifts, the call silently falls back to default.

---

## 4. Design Defects

### D-1: No Canonical Routing Contract

Model names, tier names, profile names, and backend names exist as magic strings scattered across at least 8 files:

| File | Model/Tier Reference |
|------|---------------------|
| `llm_router.py` | `"qwen-coder"`, `"gemini-free"`, `"claude-sonnet"`, `"claude-opus"` |
| `llm_router.py` | `AgentTier.LOCAL/FREE/PAID/CRITICAL` |
| `search_router.py` | `"local"`, `"remote"` |
| `http_server.py` | `"remote-gemini"`, `"remote-free"`, `"remote-coding"`, `"remote-reasoning"` |
| `local-orchestrator/router.py` | `AgentBackend.LOCAL/QWEN/CLAUDE_SONNET/CLAUDE_OPUS` |
| `local-agents/task_router.py` | `AgentTarget.LOCAL_AGENT/REMOTE_CODEX/REMOTE_CLAUDE/REMOTE_QWEN` |
| `switchboard.nix` | `[profile-card:remote-coding]`, `[profile-card:default]` etc |

A change to a profile name in `switchboard.nix` silently breaks `llm_router.py` with no type error.

### D-2: Binary `select_backend()` Discards Tier Information

`search_router.select_backend()` returns `"local"` or `"remote"` — a binary decision. This loses the classifier's task_type information entirely. The downstream `route_handler` cannot distinguish "remote because reasoning" from "remote because token limit exceeded." Escalation, metrics, and fallback logic are all blind to the reason.

### D-3: Switchboard Logic is Untestable and Opaque

The switchboard is defined as a `pkgs.writeText "ai-switchboard.py"` inline in `switchboard.nix` — approximately 1,300 lines of Python embedded in a Nix string. Problems:
- Cannot be unit tested without nixos-rebuild
- Cannot be imported or type-checked independently
- Git blame/diff on logic changes is noisy (mixed with Nix structure)
- Profile definitions live in the same file as routing code, request handling, and tracing

### D-4: Escalation Is Error-Only, Not Quality-Aware

`llm_router._escalate()` triggers only on exception (HTTP error, timeout). A response that succeeds HTTP-wise but produces garbage output (hallucination, incomplete answer) cannot trigger escalation. There is no quality signal propagated back.

### D-5: No Feedback Loop from Routing Metrics to Routing Decisions

The `routing_metrics.db` records routing decisions and escalations. The `get_metrics()` method surfaces tier distribution and cost. But nothing reads these metrics back into the routing decision logic. The router always makes static heuristic decisions regardless of observed escalation rates.

### D-6: Cost Estimates Are Stale

```python
# llm_router.py
AgentBackend.CLAUDE_SONNET: 0.018,  # ~$18/MTok total  (actual: ~$3/MTok in/out in 2026)
AgentBackend.CLAUDE_OPUS: 0.090,    # ~$90/MTok total  (actual: varies)
```

These are not read from `config.py` or `options.nix`, so they diverge from actual pricing silently.

---

## 5. Proposed Architecture

### 5.1 Routing Layers (Target)

```
┌─────────────────────────────────────────────────────────┐
│           Routing Contract (routing_contract.py)         │
│  - Canonical tier enum (LOCAL, EDGE, REMOTE_FREE,       │
│    REMOTE_PAID, REMOTE_FLAGSHIP)                         │
│  - Canonical profile registry (validated at startup)    │
│  - Model alias → profile mapping                        │
│  - Cost estimates read from Config                      │
└──────────────────────────┬──────────────────────────────┘
                           │ imported by
         ┌─────────────────┼──────────────────┐
         ▼                 ▼                  ▼
  task_classifier    llm_router.py     local-orchestrator/
  (already good)     (use contract)    router.py (align)
         │                 │
         └────────┬────────┘
                  ▼
        RoutingDecision (dataclass)
        {tier, profile, model_alias,
         reason, confidence, task_type}
                  │
       ┌──────────┴──────────────┐
       ▼                         ▼
  local execution          profile lookup
  (llama.cpp direct)       → switchboard or
                             coordinator delegate
```

### 5.2 `routing_contract.py` — Single Source of Truth

A new module imported by all routing components that defines:
- `RoutingTier` enum: `LOCAL | EDGE | REMOTE_FREE | REMOTE_PAID | REMOTE_FLAGSHIP`
- `PROFILE_REGISTRY`: validated dict of real switchboard profile names → tier + model alias
- `RoutingDecision`: unified dataclass shared by all routers
- `CostEstimates`: read from `Config`, not hardcoded

Note: the current switchboard does not expose a dedicated flagship profile, so `REMOTE_FLAGSHIP`
must resolve to the strongest existing reasoning lane until that profile is added declaratively.

### 5.3 Improve `_build_prompt()` to Consume `advisor_guidance`

Once BUG-1 is fixed, the advisor pattern becomes useful:
```python
def _build_prompt(self, task: Dict, optimize_for: str = "local") -> str:
    guidance_note = ""
    if task.get("advisor_guidance"):
        ag = task["advisor_guidance"]
        guidance_note = f"\n[Advisor guidance — {ag.get('action','proceed')}]: {ag.get('reasoning','')[:300]}\n"
    # ... rest of prompt building
```

### 5.4 Move Switchboard Script Out of Nix Inline

Extract `switchboard.nix` inline Python to `ai-stack/mcp-servers/switchboard/server.py`. The Nix module keeps only `pkgs.writeScript`-style glue that copies the file. This enables:
- Unit testing without nixos-rebuild
- Independent py_compile validation in pre-commit
- Clean git history for logic changes

### 5.5 Propagate Task Type Through `select_backend()`

Extend `SearchRouter.select_backend()` return type:

```python
@dataclass
class BackendDecision:
    backend: str          # "local" | "remote"
    reason: str
    reason_class: str     # "confidence" | "health" | "capability" | etc.
    task_type: str        # from task_classifier (lookup/format/code/reasoning/synthesize)
    tier_hint: str        # "edge" | "remote-free" | "remote-paid"
```

This lets `route_handler` record the task type in telemetry and make profile selection more precise.

---

## 6. Implementation Priority

| Priority | Item | Effort | Impact |
|----------|------|--------|--------|
| P0 — Fix now | BUG-2: use-after-close in `get_advisor_metrics()` | Small | Prevents crash |
| P0 — Fix now | BUG-1: advisor guidance ignored | Small | Fixes silent waste |
| P1 — Next sprint | `routing_contract.py` canonical registry | Medium | Eliminates magic strings |
| P1 — Next sprint | Align `llm_router` to use `task_classifier` | Medium | Single classifier |
| P2 — Phase 10 | Quality-aware escalation signal | Large | Better tier utilization |
| P2 — Phase 10 | Switchboard script externalized | Large | Testability |
| P3 — Backlog | Metrics → routing feedback loop | Large | Adaptive routing |

---

## 7. What to Leave Alone

- `task_classifier.py` — well-designed, regex-based, zero-latency. Keep as-is.
- `search_router.select_backend()` — binary output is appropriate for the /query search generation path. Only extend the dataclass, don't redesign.
- `_REMOTE_AVAIL_CACHE` in `http_server.py` — correct availability caching pattern for remote profiles.
- `advisor_detector.py` — the detection logic is sound; the bug is in consumption, not detection.

---

## 8. Files to Change for P0/P1 Fixes

### P0 Fixes
- `ai-stack/mcp-servers/hybrid-coordinator/llm_router.py` — fix BUG-1 and BUG-2

### P1 — New File
- `ai-stack/mcp-servers/hybrid-coordinator/routing_contract.py` — canonical tier/profile registry

### P1 — Updates
- `ai-stack/mcp-servers/hybrid-coordinator/llm_router.py` — use `routing_contract` for tiers and profiles
- `ai-stack/mcp-servers/hybrid-coordinator/config.py` — add cost estimate options sourced from Nix

---

*Reviewed by: Claude Sonnet 4.6 (engineering audit pass)*
