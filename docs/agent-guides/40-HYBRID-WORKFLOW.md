# Hybrid Workflow Guide — Unified Agent Orchestration Gateway

Phase 26: This guide supersedes the archived 2026-03 version.

## Overview

Every user prompt — from Continue, Codex extension, Claude extension, or any future
client — enters through a **single intake endpoint** and is driven through a
deterministic lifecycle before any code is changed.

```
POST /agent/intake
        │
        ▼
┌───────────────────────────────────────────────────────┐
│  LIFECYCLE FSM: 8 phases                              │
│                                                       │
│  INTAKE → DISCOVER → PRD → PLAN → ASSIGN → DELEGATE  │
│                                          │            │
│              VALIDATE ←─────────────────┘            │
│                 │                                     │
│              COMMIT → DONE                            │
└───────────────────────────────────────────────────────┘
```

Simple tasks (typo fix, rename) auto-skip DISCOVER+PRD and start at PLAN.

---

## Entry Point

```bash
# MCP tool (Continue / Codex extension / Claude extension)
agent_intake(prompt="add a new NixOS service for X", domain="nixos")
# → {session_id, current_phase, sequence, routing_preview, pruned_context}

# HTTP (any agent, script, or CLI)
curl -s -X POST http://127.0.0.1:8003/agent/intake \
  -H "Content-Type: application/json" \
  -H "X-AI-Profile: local-agent" \
  -d '{"prompt": "fix the switchboard routing bug"}'
```

**No client name or model ID is hardcoded.** The gateway reads `X-AI-Profile`,
`X-Caller-Id`, and `User-Agent` headers to normalize the caller. New clients
are automatically supported without any code change.

---

## Phase Descriptions

| Phase    | Purpose                                         | Key Outputs                            |
|----------|-------------------------------------------------|----------------------------------------|
| INTAKE   | Normalize caller, detect complexity + domain    | complexity, domain, caller_profile     |
| DISCOVER | Codebase scan, health check, existing plans     | codebase_summary, existing_plans       |
| PRD      | Generate/locate PRD; scope the work             | prd_scope, acceptance_checks           |
| PLAN     | Phased execution plan + tool assignments        | phases[], tool_assignments             |
| ASSIGN   | Match agents/teams to each plan phase           | agent_assignments, team_routing        |
| DELEGATE | Execute via delegated agents/teams              | sub_agent_summaries, artifacts_created |
| VALIDATE | aq-qa, syntax checks, test gates                | validation_passed, qa_score            |
| COMMIT   | Guided commit + tier0-validation-gate           | commit_sha, files_changed              |

---

## Context Pruning (Critical)

Sub-agents receive a **pruned context slice**, not the full accumulated session context.
This prevents irrelevant search results, unrelated tool outputs, and previous-phase
noise from inflating the prompt context.

```
Phase PLAN receives:     {complexity, domain, codebase_summary, existing_plans, prd_scope}
Phase ASSIGN receives:   {complexity, domain, prd_scope, phases[], tool_assignments}
Phase DELEGATE receives: {prd_scope, phases[], tool_assignments, agent_assignments}
```

When recording phase completion, pass **only structured key outputs** in `context_updates`:

```python
# CORRECT — structured summary of what was found
lifecycle_advance(session_id, context_updates={
    "codebase_summary": "FastAPI app, 1700-line http_server.py, 25 phases complete",
    "existing_plans": ["phase-25-system-hardening-brainstem.md"],
    "health_status": "61/61 aq-qa checks passing"
})

# WRONG — raw tool output inflates context for all future phases
lifecycle_advance(session_id, context_updates={
    "full_search_results": "...50KB of grep output...",
})
```

---

## Domain Routing

After the PLAN phase, the domain classifier routes to the appropriate team:

| Domain   | Team Composition                                | Key Tools                              |
|----------|-------------------------------------------------|----------------------------------------|
| nixos    | architect(remote) + implementer(local)          | simulate_nix_change, validate_service_config |
| python   | implementer(local/codex) + reviewer(self)       | hybrid_search, qa_check                |
| security | architect(remote) + auditor(local)              | hybrid_search, qa_check                |
| trading  | tradingagents 5-team pipeline                   | trading_analyze, trading_forecast      |
| design   | impeccable design intelligence                  | impeccable_design                      |
| infra    | implementer(local) + reviewer(self)             | hybrid_search, workflow_plan           |
| general  | local-agent profile                             | hybrid_search, workflow_plan           |

Domain is **auto-classified** from prompt keywords. Override with `domain=` param.

No team member has a hardcoded model name. Agents are discovered dynamically from:
- `SWITCHBOARD_REMOTE_ALIAS_*` env vars (set by Nix)
- Local switchboard profiles at `:8085`
- Dynamic registration in `agent_capability_registry.py`

---

## Agent Capability Registry

```bash
# View current agent inventory
curl -s http://127.0.0.1:8003/agent/registry | python3 -m json.tool

# View domain team catalog
curl -s http://127.0.0.1:8003/agent/domains | python3 -m json.tool
```

Agents are tagged by **capability** (architect, implementer, reviewer, domain:nixos, etc.)
not by model name. When a subscription changes, update the Nix env vars — no Python
source changes needed.

---

## Self-Delegation

When the current agent (Continue, Claude, Codex) is the implementer for a task,
the DELEGATE phase routes back to itself with the **plan + pruned context** injected.
This avoids a round-trip through a sub-agent when the work is already in scope.

Self-delegation is the default for `general` domain and `simple` complexity tasks.

---

## Phase Tracking

```bash
# Check session state
lifecycle_status(session_id="abc-123")
# → {current_phase, phases[], pruned_context, next_action}

# Advance after completing a phase
lifecycle_advance(
    session_id="abc-123",
    status="passed",
    output_summary="Found 2 relevant files, existing phase-25 plan, health OK",
    context_updates={"codebase_summary": "...", "existing_plans": ["phase-25.md"]}
)

# List recent sessions
curl -s http://127.0.0.1:8003/agent/lifecycle | python3 -m json.tool
```

---

## Workflow Blueprints

Three new blueprints added in Phase 26 (`config/workflow-blueprints.json`):

| Blueprint ID             | Use Case                                      |
|--------------------------|-----------------------------------------------|
| `lifecycle-aware-intake` | Full 8-phase workflow for standard tasks      |
| `simple-task-direct`     | Skips DISCOVER+PRD for trivial changes        |
| `domain-delegated-task`  | Sub-agent entry after planning is complete    |

Select via `/workflow/run/start` with `blueprint=lifecycle-aware-intake`.

---

## Validation Gates

Before every commit, regardless of which agent executed:

```bash
aq-qa 0                                                    # 0 failures required
scripts/governance/tier0-validation-gate.sh --pre-commit   # full validation gate
```

The VALIDATE phase must pass these before COMMIT is entered.

---

## Key Files

```
ai-stack/mcp-servers/hybrid-coordinator/
  intake_gateway.py              — UAG HTTP handlers (POST /agent/intake + lifecycle routes)
  lifecycle_fsm.py               — 8-state FSM + session persistence + context pruning
  agent_capability_registry.py   — dynamic agent discovery (no hardcoded IDs)
  domain_router.py               — domain classifier + team routing

config/workflow-blueprints.json  — lifecycle-aware-intake, simple-task-direct, domain-delegated-task
config/agent-routing-policy.json — agent-intake, lifecycle-delegate profiles

scripts/ai/mcp-bridge-hybrid.py  — agent_intake, lifecycle_status, lifecycle_advance MCP tools
```
