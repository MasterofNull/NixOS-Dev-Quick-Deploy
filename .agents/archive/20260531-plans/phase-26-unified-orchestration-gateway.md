# Phase 26 — Unified Agent Orchestration Gateway

## Objective
Replace the scattered multi-entry-point agent workflow with a single, subscription-agnostic
intake gateway that drives every user prompt through a deterministic 8-phase lifecycle:

```
INTAKE → DISCOVER → PRD → PLAN → ASSIGN → DELEGATE → VALIDATE → COMMIT
```

Any client (Continue, Codex ext, Claude ext, raw API, future tools) hits a single endpoint.
No client identities or model IDs are hardcoded — all resolved dynamically from env/registry.

---

## Motivation

### Current Problems
1. Continue, Codex extension, and Claude extension each call the stack differently — no
   uniform lifecycle, no consistent discovery or planning before execution.
2. Agent delegation is ad-hoc: no PRD phase, no structured planning before code changes.
3. Domain routing is manual — the orchestrator must know which team to call.
4. Model IDs appear in multiple places; dropping a subscription breaks the wiring.

### Goal State
- One HTTP entry: `POST /agent/intake`
- One lifecycle FSM drives all work from first prompt to final commit
- Dynamic agent registry reads capabilities from env vars, never hardcoded
- Domain classifier routes to the right team automatically after the PLAN phase

---

## New Modules

### `intake_gateway.py` — Universal Agent Gateway (UAG)
Routes: `POST /agent/intake`, `GET /agent/lifecycle/{id}`, `POST /agent/lifecycle/{id}/advance`

Responsibilities:
- Normalize caller identity from headers (X-AI-Profile, X-Caller-Id, User-Agent)
- Detect prompt complexity (simple/standard/complex)
- Create LifecycleSession via lifecycle_fsm
- Return session_id, current_phase, next_action, and hints
- Simple tasks skip DISCOVER+PRD and enter at PLAN

### `lifecycle_fsm.py` — 8-Phase Lifecycle FSM
Session persistence: `DATA_DIR/lifecycle/<session_id>.jsonl`

Phases:
1. **INTAKE** — normalize input, detect complexity + domain hint
2. **DISCOVER** — codebase scan, health check, existing plans/PRD query
3. **PRD** — generate or locate existing PRD; scope the work
4. **PLAN** — phased execution plan with tool assignments per phase
5. **ASSIGN** — call agent_capability_registry to match agents to plan phases
6. **DELEGATE** — call domain_router to route slices; fire sub-agent tasks
7. **VALIDATE** — aq-qa smoke, syntax checks, test runner gates
8. **COMMIT** — guided commit with tier0-validation-gate

Terminal states: DONE, ABORTED

### `agent_capability_registry.py` — Dynamic Agent Discovery
Sources (no hardcoded IDs):
- `SWITCHBOARD_REMOTE_ALIAS_*` env vars → remote agents
- Local inventory: profiles from switchboard (`:8085`)
- CLI bridge availability: `CLI_BRIDGE_URL` + probe
- MCP bridge presence: `mcp-bridge-hybrid.py` TOOLS list

Capability profiles per agent:
- `architect` — architecture, policy, tradeoff analysis
- `implementer` — code patches, test scaffolding
- `reviewer` — deterministic acceptance gate
- Domain specialists: nixos, python, security, trading, design

### `domain_router.py` — Domain Classifier + Team Router
Domains → team routing:
- `nixos` → architect:remote-reasoning + implementer:local-agent
- `python` → implementer:codex-cli|qwen-local + reviewer:self
- `security` → architect:remote-reasoning + auditor:local-agent
- `trading` → tradingagents team via `/trading/*`
- `design` → impeccable team via `/agent/intake?domain=design`
- `infra` → implementer:local-agent + reviewer:self
- `general` → default local-agent profile

---

## Updated Configs

### `config/workflow-blueprints.json`
New blueprints:
- `lifecycle-aware-intake` — full 8-phase lifecycle workflow for standard tasks
- `domain-delegated-task` — post-PRD blueprint for domain-specific team execution
- `simple-task-direct` — skip DISCOVER+PRD for trivial changes

### `config/agent-routing-policy.json`
New profiles:
- `agent-intake` — allow all lifecycle tools
- `lifecycle-delegate` — allow delegate+validate but deny model-reload

### `scripts/ai/mcp-bridge-hybrid.py`
New MCP tools (visible to all MCP clients: Continue, Codex ext, Claude ext):
- `agent_intake` — submit prompt to UAG, returns session_id + phase
- `lifecycle_status` — query lifecycle session state + phase history
- `lifecycle_advance` — manually advance a session phase

---

## Wire-in (http_server.py)

```python
import intake_gateway           # Phase 26: UAG + lifecycle FSM
import agent_capability_registry  # Phase 26: dynamic agent registry
import domain_router            # Phase 26: domain classifier + team routing
```

In `run_http_mode()` after context_summary_handlers:
```python
intake_gateway.init(
    lifecycle_dir=Path(os.environ.get("DATA_DIR", "~/.local/share/nixos-ai-stack/hybrid")) / "lifecycle",
    agent_registry=agent_capability_registry,
    domain_router_mod=domain_router,
    hints_url=os.environ.get("HYBRID_COORDINATOR_URL", "http://127.0.0.1:8003"),
    error_payload_fn=_error_payload,
)
intake_gateway.register_routes(http_app)  # Phase 26: UAG routes
```

---

## Validation Gates (Before Commit)

```bash
python3 -m py_compile ai-stack/mcp-servers/hybrid-coordinator/intake_gateway.py
python3 -m py_compile ai-stack/mcp-servers/hybrid-coordinator/lifecycle_fsm.py
python3 -m py_compile ai-stack/mcp-servers/hybrid-coordinator/agent_capability_registry.py
python3 -m py_compile ai-stack/mcp-servers/hybrid-coordinator/domain_router.py
aq-qa 0   # must stay 0 failures
scripts/governance/tier0-validation-gate.sh --pre-commit
```

---

## Task Checklist

- [x] P26-001 Phase plan written
- [x] P26-002 `lifecycle_fsm.py` — 8-state FSM + session persistence
- [x] P26-003 `agent_capability_registry.py` — dynamic agent discovery
- [x] P26-004 `domain_router.py` — domain classifier + team routing
- [x] P26-005 `intake_gateway.py` — UAG HTTP handlers
- [x] P26-006 Wire into `http_server.py`
- [x] P26-007 Add MCP tools to `mcp-bridge-hybrid.py`
- [x] P26-008 Update `config/workflow-blueprints.json`
- [x] P26-009 Update `config/agent-routing-policy.json`
- [x] P26-010 Update `docs/agent-guides/40-HYBRID-WORKFLOW.md`
- [x] P26-011 Validation + commit (tier0: 8/8 gates PASS, aq-qa: 39/0)

---

## Key Files (Quick Reference)
```
ai-stack/mcp-servers/hybrid-coordinator/intake_gateway.py         NEW
ai-stack/mcp-servers/hybrid-coordinator/lifecycle_fsm.py          NEW
ai-stack/mcp-servers/hybrid-coordinator/agent_capability_registry.py NEW
ai-stack/mcp-servers/hybrid-coordinator/domain_router.py          NEW
ai-stack/mcp-servers/hybrid-coordinator/http_server.py            EDIT: import + init + routes
scripts/ai/mcp-bridge-hybrid.py                                    EDIT: add 3 tools
config/workflow-blueprints.json                                    EDIT: 3 new blueprints
config/agent-routing-policy.json                                   EDIT: 2 new profiles
docs/agent-guides/40-HYBRID-WORKFLOW.md                           EDIT: lifecycle docs
```
