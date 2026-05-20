# PRD: Configuration Centralization & Routing Standardization

**Status:** DRAFT  
**Authors:** Claude Sonnet 4.6 (architect), Gemini (co-auditor)  
**Date:** 2026-05-20  
**Priority:** P1 — Performance + Correctness  
**Tracking:** `.agents/plans/config-centralization/`

---

## 1. Problem Statement

The NixOS-Dev-Quick-Deploy AI harness has accumulated three independent configuration schemas, no canonical env var contract, hardcoded token budgets, and routing logic scattered across six files. This causes:

- **Wasted tokens**: conflicting max_tokens caps (dashboard uses 1500, coordinator uses 8000 for the same local-agent lane); no enforcement across layers
- **Variable overwrite bugs**: `HYBRID_API_KEY` (dashboard/scripts) silently ignored when coordinator expects `HYBRID_API_KEY_FILE`; `LLAMA_URL` (shell/dashboard) and `LLAMA_CPP_BASE_URL` (coordinator) diverge when ports change
- **System misconfiguration**: 299 hardcoded port references across active Python/shell files; a port change in `options.nix` only propagates via NixOS rebuild, but runtime scripts still use stale defaults
- **Developer friction**: new scripts invent new variable names because no contract document exists

---

## 2. Root-Cause Analysis

### 2.1 Three Independent Config Schemas (Not Talking to Each Other)

| Layer | SSOT File | URL key for llama-cpp | API key for coordinator |
|---|---|---|---|
| **Coordinator** | `shared/stack_settings.py` → `HybridSettings` | `LLAMA_CPP_BASE_URL` | `HYBRID_API_KEY_FILE` |
| **Switchboard** | `switchboard.py` (inline) | `REMOTE_LLM_URL` | `HYBRID_COORDINATOR_API_KEY` |
| **Dashboard** | `dashboard/backend/api/config/service_endpoints.py` | `LLAMA_URL` | `HYBRID_API_KEY` / `HYBRID_URL` |
| **Shell scripts** | `config/service-endpoints.sh`, `config/variables.sh` | `LLAMA_URL` + `LLAMA_CPP_URL` | `HYBRID_API_KEY` |
| **Tests** | `scripts/testing/_mock_config.py` | `LLAMA_CPP_BASE_URL` | _(hardcoded)_ |

Three different names for the same llama-cpp URL. Two different names for the coordinator API key. No layer automatically inherits from another.

### 2.2 Switchboard Token Budgets: All Hardcoded Python Literals

`ai-stack/switchboard/switchboard.py` defines 13 profiles (default, continue-local, local-agent, remote-*, local-tool-calling, embedding-local, embedded-assist, coordinator-internal) with `maxInputTokens`, `maxOutputTokens`, `maxMessages` as inline Python integers. Only 2 of 26 budget fields are env-configurable (`SWB_CONTINUE_LOCAL_MAX_INPUT_TOKENS`, `SWB_CONTINUE_LOCAL_MAX_MESSAGES`). The mechanism to externalize them via `SWB_PROFILE_CATALOG_JSON_FILE` exists but has never been used.

**Effect**: When ctxSize changed from 16384 to 8192 (mlock removal), `advertisedContextWindow` updated (via `LLAMA_CTX_SIZE` env), but budgets like `maxInputTokens=8000` for local-agent remain uncapped — the model receives prompts it cannot process in the reduced context.

### 2.3 Routing Authority Spread Across Six Files

```
Request arrives
  ↓
switchboard.py:forceProvider()      ← "which backend CLASS" (static profile config)
  ↓
http_server.py:handle_query()       ← "route_search or orchestrate?"
  ↓
ai_coordinator_handlers.py:         ← "auto_prefer_local heuristic" (timeout ≤10s → local)
  prefer_local + auto_prefer_local
  ↓
openai_a2a_handlers.py:             ← "prefer_local from query param or payload"
  _coordinator_prefer_local()
  ↓
mcp_handlers.py:                    ← "prefer_local from MCP tool argument"
  prefer_local arg
  ↓
route_handler.py / search_router.py ← actual dispatch
```

The heuristic `auto_prefer_local = not requested_profile and not tools_present and timeout_s <= 10.0` in `ai_coordinator_handlers.py:721` is undocumented, unconfigured, and causes requests that *should* go local to go remote when tool-calling is present.

### 2.4 Config Directory: 50+ Files, No Lifecycle Policy

`config/` contains 50+ JSON/YAML files with overlapping scope:
- `config/agent-routing-policy.json` and `config/intent-routing-map.json` and `config/capability-lifecycle-registry.json` — all affect routing
- `config/ai-slo-thresholds.json` and `config/ai-stack-hardware-profiles.json` — both affect performance budgets
- No file has a `version`, `owner`, or `last_validated` field that gates CI

### 2.5 Hardcoded Ports in Active Code

299 occurrences of `127.0.0.1:<port>` in non-nix files. `nix/modules/core/options.nix` is the declared SSOT, but `dashboard/backend/api/main.py` and `dashboard/backend/api/routes/topology.py` still hardcode `8080`, `8003`, etc. directly — meaning a port change in NixOS does not propagate to these files without a code edit.

---

## 3. Goals

1. **One env var contract** — single file listing every variable name, its type, default, and which layer owns it; all new code MUST reference this file
2. **Externalized switchboard profiles** — token budgets in `config/switchboard-profiles.yaml`, loaded at startup, hot-reloadable
3. **Documented routing authority** — one policy config file governs local-vs-remote decisions; heuristics are configurable, not hardcoded
4. **Port/URL propagation fixed** — Python/shell code reads from their respective SSOT files only; no raw port literals in active code
5. **Config directory governed** — every file has a schema, version, and CI validation; orphaned files removed

---

## 4. Non-Goals

- Rewriting the coordinator or switchboard from scratch
- Changing any API contract or endpoint path
- Touching `nix/` Nix expressions (port defaults stay in `options.nix`)
- Affecting Codex's Phase 59.1 RAG work (this is parallel infrastructure)

---

## 5. Solution Design

### 5.1 Canonical Env Var Contract (Phase A)

Create `config/env-contract.yaml` — machine-readable, human-auditable:

```yaml
version: "1.0"
variables:
  # Service URLs — canonical names, all layers MUST use these
  - name: LLAMA_CPP_BASE_URL
    type: url
    default: "http://127.0.0.1:8080"
    layers: [coordinator, dashboard, shell, tests]
    aliases_deprecated: [LLAMA_URL, LLAMA_CPP_URL, LLAMA_CPP_INFERENCE_URL]
    owner: nix/modules/core/options.nix

  - name: EMBEDDING_SERVICE_URL
    type: url
    default: "http://127.0.0.1:8081"
    layers: [coordinator, dashboard, shell]
    aliases_deprecated: [EMBEDDINGS_URL, LLAMA_EMBED_URL]
    owner: nix/modules/core/options.nix

  - name: HYBRID_COORDINATOR_URL
    type: url
    default: "http://127.0.0.1:8003"
    layers: [dashboard, shell, tests, edgeai]
    aliases_deprecated: [HYBRID_URL, HYBRID_BASE_URL]
    owner: nix/modules/core/options.nix

  - name: SWITCHBOARD_URL
    type: url
    default: "http://127.0.0.1:8085"
    layers: [dashboard, shell, continue, tests]
    aliases_deprecated: []
    owner: nix/modules/core/options.nix

  # API Keys — always file-based in production
  - name: HYBRID_API_KEY_FILE
    type: path
    default: "/run/secrets/hybrid_coordinator_api_key"
    layers: [coordinator, dashboard, shell, edgeai]
    aliases_deprecated: [HYBRID_API_KEY, HYBRID_KEY, HYBRID_COORDINATOR_API_KEY]
    note: "Runtime reads key from file. HYBRID_API_KEY accepted as direct value fallback."

  # Token budgets (runtime overrides for switchboard profiles)
  - name: SWB_PROFILE_CATALOG_YAML_FILE
    type: path
    default: "config/switchboard-profiles.yaml"
    layers: [switchboard]
    note: "Loaded at switchboard startup. Overrides inline Python defaults."

  # Routing
  - name: AI_ROUTING_POLICY_FILE
    type: path
    default: "config/routing-policy.yaml"
    layers: [coordinator]
    note: "Controls auto_prefer_local thresholds and heuristic parameters."
```

**Enforcement**: `scripts/governance/tier0-validation-gate.sh` adds a gate that checks new Python/shell files don't introduce env var names not in the contract.

### 5.2 Externalized Switchboard Profiles (Phase B)

Create `config/switchboard-profiles.yaml` with all 13 profiles. Modify switchboard to load it via `SWB_PROFILE_CATALOG_YAML_FILE` at startup (falling back to inline defaults for backward compatibility).

```yaml
version: "1.0"
profiles:
  default:
    forceProvider: null
    maxInputTokens: 1500
    maxMessages: 12
    maxOutputTokens: 768

  local-agent:
    forceProvider: local
    maxInputTokens: 8000   # hard cap: must be < LLAMA_CTX_SIZE - system_prompt_overhead
    maxMessages: 16
    maxOutputTokens: 4096

  # ... all 13 profiles
```

**Key constraint**: `maxInputTokens` for local profiles MUST satisfy `maxInputTokens + maxOutputTokens + ~500 (system) ≤ LLAMA_CTX_SIZE`. The switchboard startup validates this against the advertised `LLAMA_CTX_SIZE` env var and logs a warning if violated.

### 5.3 Routing Policy Config (Phase C)

Create `config/routing-policy.yaml`:

```yaml
version: "1.0"
local_preference:
  # When no profile is specified, auto-route to local if ALL conditions met:
  auto_prefer_local_when:
    - no_explicit_profile: true
    - no_tool_calls_in_request: true          # was hardcoded: not tools_present
    - timeout_seconds_lte: 30                  # was hardcoded: <= 10
    - slot_available: true
  fallback_when_local_unavailable: remote_default

  # Intent → preferred backend
  intent_routing:
    systems_software: local-tool-calling
    security_analysis: local-tool-calling
    embedded_hardware: local-tool-calling
    scientific_research: local-agent
    gis_systems: local-agent
    default: default

  # Slot-busy retry policy
  slot_busy:
    max_retries: 3
    retry_after_seconds: 30
```

Coordinator's `ai_coordinator_handlers.py` reads this file at init; `_ai_coordinator_route_by_complexity()` becomes data-driven.

### 5.4 URL Alias Shims (Phase D)

In `dashboard/backend/api/config/service_endpoints.py` and `config/service-endpoints.sh`, add backward-compatible alias shims:

```python
# BACKWARD COMPAT — deprecated aliases; will be removed in Phase D+30d
LLAMA_URL = os.getenv("LLAMA_CPP_BASE_URL", os.getenv("LLAMA_URL", f"http://..."))
HYBRID_URL = os.getenv("HYBRID_COORDINATOR_URL", os.getenv("HYBRID_URL", f"http://..."))
```

```bash
# In config/service-endpoints.sh
LLAMA_CPP_BASE_URL="${LLAMA_CPP_BASE_URL:-${LLAMA_URL:-http://127.0.0.1:8080}}"
export LLAMA_CPP_BASE_URL
# Keep LLAMA_URL for 30-day deprecation window
LLAMA_URL="$LLAMA_CPP_BASE_URL"; export LLAMA_URL
```

### 5.5 Config Directory Governance (Phase E)

Add required header to every `config/*.json` and `config/*.yaml`:
```json
{
  "_meta": { "version": "1.0", "owner": "phase-XX", "last_validated": "2026-05-20" },
  ...
}
```

Tier0 gate validates: schema presence, no orphaned files (files not referenced by any service), no duplicate keys across files covering the same domain.

---

## 6. Acceptance Criteria

| Gate | Pass condition |
|------|---------------|
| AC-1 | `config/env-contract.yaml` exists; tier0 gate validates no new unlisted env vars in Python/shell changes |
| AC-2 | `config/switchboard-profiles.yaml` loaded by switchboard; `SWB_PROFILE_CATALOG_YAML_FILE` propagated via NixOS env |
| AC-3 | `config/routing-policy.yaml` loaded by coordinator; `auto_prefer_local_when.timeout_seconds_lte` configurable without code change |
| AC-4 | Zero occurrences of raw `127.0.0.1:(8080|8003|8085|8002|8889)` in `dashboard/backend/` Python files |
| AC-5 | `LLAMA_URL`, `HYBRID_URL`, `HYBRID_API_KEY` still work as aliases (backward compat for 30 days) |
| AC-6 | aq-qa 0: 0 failed after all phases |
| AC-7 | Switchboard startup validates `maxInputTokens + maxOutputTokens ≤ LLAMA_CTX_SIZE` and logs warning if violated |

---

## 7. Risk & Mitigations

| Risk | Mitigation |
|------|-----------|
| Alias shims break on unexpected env var combinations | Test matrix: verify each alias resolves correctly in unit tests |
| Switchboard profile YAML parse fails → coordinator unreachable | Fallback to inline defaults on load error; log warning at startup |
| Routing policy YAML change causes regression | aq-qa 0.7.1/0.7.2 smoke tests catch routing breakage; gate on these before deploy |
| Coordinator key file vs direct-value split | HYBRID_API_KEY_FILE takes precedence; HYBRID_API_KEY used as direct-value fallback; documented in contract |

---

## 8. Out of Scope / Future

- Removing the deprecated aliases (Phase D+30 days, after no remaining references)
- Config hot-reload for coordinator (routing policy can be SIGHUP'd; other config requires restart)
- GraphQL/JSON schema for full config validation (post Phase E)

---

## Appendix G — Gemini Co-Audit Supplementary Findings (2026-05-20)

Two additional issues found by Gemini's concurrent audit not captured in §2:

### G.1 EMBEDDINGS_PORT Discrepancy

`nix/modules/core/options.nix` defines the embed port twice:
- Line 1277: `default = 8081` (llama-cpp-embed, correct)
- Line 3182: `default = 8001` (a secondary embed option, likely stale from a previous service refactor)

`config/service-endpoints.sh` uses `8081` (correct). The `8001` default at line 3182 is a latent bug — any code that reads that specific option path would misconfigure the embed URL. **Add to Phase A audit**: trace what Nix option is at `options.nix:3182` and remove or correct it.

### G.2 `prefer_local` Default Conflict Between Endpoint Handlers

| File | Default | Rationale |
|------|---------|-----------|
| `http_server.py:905` | `True` | `/query` endpoint is local-first (retrieval) |
| `ai_coordinator_handlers.py:719` | `False` | `/orchestrate` endpoint prefers remote (Phase 14.2: "remote free-tier ~10x faster") |

This is architecturally intentional (two different endpoints with different policies) but not documented in any config file. A caller hitting `/query` without `prefer_local` gets local; a caller hitting `/orchestrate` without `prefer_local` gets remote. **Add to Phase C**: document this asymmetry explicitly in `config/routing-policy.yaml` and add a comment block at both handler sites referencing the policy file.

---

## §9 — Rewrite Target R1: aq-qa → Python Test Framework

### Current State (Why It Cannot Stand)

`scripts/ai/aq-qa` is 2,090 lines of bash with **72 embedded Python blocks** (`python3 -c`, `python3 -`, heredoc `<<'PY'`). It cannot be:
- Parallelized (sequential bash, no async)
- Partially run without understanding global state (`PASS`, `FAIL`, `SKIP` counters, `RESULTS` array)
- Debugged with standard tooling (mixing bash `set -euo pipefail` with Python subprocess exit codes)
- Extended safely (every new check must fit the bash control flow)
- Imported or composed (it's a script, not a module)

72 embedded Python blocks means 72 context switches where the reader must mentally re-enter Python scope, understand a different error model, and re-exit. This is not a test suite. It is accumulated scripting debt.

### Proposed Architecture: `scripts/testing/harness_qa/`

```
scripts/testing/harness_qa/
├── __main__.py          # entry point: python3 -m harness_qa [phase] [--json] [--level N]
├── runner.py            # CheckRunner: collects results, formats output, exit code
├── checks/
│   ├── phase0_smoke.py  # systemd, ports, inference ping, editor, routing, RAG
│   ├── phase1_infra.py  # JSON/YAML/TOML/JS syntax, roadmap, repo structure
│   ├── phase2_coordinator.py  # coordinator API surface, auth, routing
│   ├── phase3_knowledge.py    # memory, hints, RAG, AIDB vector search
│   ├── phase4_safety.py       # safety gate, runtime policy, trust roots
│   ├── phase5_agent.py        # lifecycle, DAG executor, fleet control
│   └── phase_maeah.py         # MAEAH acceptance gates (bonus + normative)
├── base.py              # Check dataclass, CheckResult, @check decorator
└── external.py          # curl/ss/git wrappers — isolated, mockable
```

**Base interface:**
```python
@dataclass
class CheckResult:
    id: str            # "0.7.3"
    description: str
    status: Literal["pass", "fail", "skip"]
    reason: str = ""
    layer: int = 4
    duration_ms: float = 0.0

def check(id: str, desc: str, layer: int = 4):
    """Decorator. Function returns bool or raises CheckSkip/CheckFail."""
```

**Output**: structured JSON (same schema as current), human-readable color terminal (same visual as current). Exit code = number of failures (capped at 100).

**Migration path**: `scripts/ai/aq-qa` becomes a thin wrapper that calls `python3 -m harness_qa "$@"` — zero disruption to `tier0-validation-gate.sh` or any existing caller.

### Acceptance Criteria (R1)

| Gate | Condition |
|------|-----------|
| R1-AC1 | All 65 current checks present and passing in Python framework |
| R1-AC2 | `aq-qa 0` produces identical output format (pass/fail counts, check IDs) |
| R1-AC3 | `python3 -m harness_qa 0 --json` produces valid JSON |
| R1-AC4 | Each check module independently importable and unit-testable |
| R1-AC5 | New checks can be added with one decorated function, zero bash |

---

## §10 — Rewrite Target R2: Coordinator HTTP Dispatch Reconception

### Current State (Why It Cannot Stand)

`http_server.py` (2,735 lines) is the integration nexus of the coordinator. It:
- Imports from 25+ coordinator modules at module load time
- Registers 27 routes, all from imported handlers (0 defined locally)
- Owns auth middleware, rate limiter, health aggregation, metrics emission, and startup sequencing
- Is imported directly by `server.py` (`import http_server`) creating tight coupling
- Has accumulated every phase's wiring since Phase 1 — there is no removal, only addition

The coordinator's total surface is **56,000+ lines** across 30+ Python files. This is not the problem — a large, complex system can have many files. The problem is that **all 56,000 lines treat `http_server.py` as their shared integration surface**. There is no service boundary enforcement. Any module can import any other module. The domain split (core/workflow/knowledge/extensions) is cosmetic — flat shim files still re-export everything.

At the current growth rate (Phase 59 + Phase 60 + ...), this reaches unmaintainable territory within 6 months.

### Proposed Architecture: Thin Router + Injected Domain Services

```
ai-stack/mcp-servers/hybrid-coordinator/
├── server.py                    # entry point only: parses args, calls router.start()
├── router.py                    # ~200 lines: aiohttp app, route registration, middleware
├── middleware/
│   ├── auth.py                  # API key + loopback auth — one place, one policy
│   ├── rate_limiter.py          # rate limiting (already partially extracted)
│   └── observability.py        # OTel span injection, request logging
├── services/                   # Domain services — each is a self-contained class
│   ├── query_service.py        # /query, /api/query — retrieval + synthesis
│   ├── orchestration_service.py # /v1/orchestrate, /v1/responses, A2A
│   ├── memory_service.py       # /memory/*, /api/memory/*
│   ├── knowledge_service.py    # /hints/*, /api/logic/*, topology
│   ├── workflow_service.py     # /workflow/*, DAG, checkpoints
│   ├── model_service.py        # /api/models/*, model lifecycle
│   ├── ops_service.py          # /control/*, /admin/*, /eval/*, /api/health/*
│   └── agent_service.py        # /agent/*, /runtime/*, /control/fleet/*
├── core/                       # (keep as-is — domain objects are fine)
├── knowledge/                  # (keep, but hints_engine.py decomposed — see §11)
├── extensions/                 # (keep, handler functions become service methods)
└── shared/                     # (keep as-is)
```

**Service injection contract** (in `router.py`):
```python
class CoordinatorRouter:
    def __init__(self, services: ServiceContainer):
        self.app = web.Application(middlewares=[auth_mw, rate_mw, otel_mw])
        services.query.register_routes(self.app.router)
        services.orchestration.register_routes(self.app.router)
        # ... each service owns its own routes
```

**Key principles:**
1. `router.py` never contains business logic — only wiring
2. Each service has `register_routes(router)` — owns its URL namespace
3. Services communicate through injected interfaces, not direct imports
4. Auth is one middleware, not scattered inline checks across 10 handlers
5. The flat shim files (`*.py` that re-export from subdirs) are removed — imports go direct to the canonical location

**Migration strategy**: Strangler Fig pattern — new `router.py` registers BOTH old `http_server.py` handlers AND new service handlers during transition. Old handlers are migrated service-by-service. `http_server.py` shrinks as services are extracted. At completion, `http_server.py` is deleted.

### Acceptance Criteria (R2)

| Gate | Condition |
|------|-----------|
| R2-AC1 | All 27 existing routes present and tested in new service structure |
| R2-AC2 | `http_server.py` reduced to ≤100 lines (compatibility shim only) during transition |
| R2-AC3 | Auth middleware consolidated to `middleware/auth.py` — grep for inline auth checks = 0 |
| R2-AC4 | Each domain service independently unit-testable without starting the full server |
| R2-AC5 | `router.py` ≤200 lines, zero business logic |
| R2-AC6 | aq-qa phase 0: 0 failed after migration |
| R2-AC7 | No circular imports — `python3 -c "import router"` completes in <2s |

---

## §11 — Rewrite Target R3: hints_engine.py Decomposition

### Current State

`hints_engine.py` is 3,458 lines — larger than `http_server.py` itself. It contains **six distinct concerns** bundled in one file (Gemini independent audit, 2026-05-20):

| Concern | Should Be | Est. Lines |
|---------|-----------|-----------|
| `Hint` dataclass + text utilities (tokenize, compress, estimate) | `knowledge/models.py` | ~120 |
| `TokenBudgetContext` — context-aware token budget calculation | `knowledge/token_manager.py` | ~450 |
| Static workflow rule matching (CLAUDE.md-derived keyword rules) | `knowledge/static_rules.py` | ~350 |
| Gap detection — synthetic gap identification, curated stale gap, file type detection | `knowledge/gap_analyzer.py` | ~550 |
| Qdrant/Redis/PostgreSQL query logic interleaved with scoring | _(absorbed into hints_engine.py orchestrator)_ | — |
| `HintsEngine` class — retrieval orchestration, ranking, progressive disclosure | `knowledge/hints_engine.py` | ~900 |

### Proposed Decomposition

```
ai-stack/mcp-servers/hybrid-coordinator/knowledge/
├── models.py        # Hint dataclass, TokenBudgetContext data types
├── token_manager.py # Token estimation, calculate_context_aware_budget, _budget_rationale
├── static_rules.py  # Hardcoded keyword/rule matching (CLAUDE.md-derived rules, no I/O)
├── gap_analyzer.py  # _is_synthetic_gap, _normalize_gap_text, gap fingerprinting
└── hints_engine.py  # HintsEngine orchestrator + DB/vector queries (~900 lines)
```

Each file has one job. `hints_engine.py` becomes the orchestrator that imports from its four focused siblings. External services (Qdrant, Redis, PostgreSQL) remain in `hints_engine.py` — splitting storage from retrieval would produce an anemic data layer with circular dependencies.

### Acceptance Criteria (R3)

| Gate | Condition |
|------|-----------|
| R3-AC1 | `hints_engine.py` ≤900 lines |
| R3-AC2 | `models.py` ≤200 lines; `token_manager.py` ≤500 lines; `static_rules.py` ≤400 lines; `gap_analyzer.py` ≤600 lines |
| R3-AC3 | Each new module independently importable (`python3 -m py_compile`) |
| R3-AC4 | `aq-qa 0` hint-related checks (0.9.x) pass unchanged |
| R3-AC5 | `TokenBudgetContext` accessible via `from knowledge.models import TokenBudgetContext` |
| R3-AC6 | `static_rules.py` has zero imports from `hints_engine.py` (no circular deps) |

---

## §12 — Revised Non-Goals

The following are still non-goals:
- Changing any external API contract, endpoint path, or auth mechanism
- Rewriting domain objects (MemoryBroker, RAGAugmentor, WorkflowCheckpointer, IntentClassifier)
- Changing the NixOS declarative infrastructure
- Rewriting the switchboard profile concept (Phase B is sufficient)
- Rewriting the data layer (PostgreSQL, Qdrant, Redis)

The following are now **GOALS** (updated from §4):
- Rewriting `aq-qa` as a Python framework (R1)
- Reconceiving the coordinator HTTP dispatch layer as a thin router with injected services (R2)
- Decomposing `hints_engine.py` into focused single-responsibility modules (R3)
