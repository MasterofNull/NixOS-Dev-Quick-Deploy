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
