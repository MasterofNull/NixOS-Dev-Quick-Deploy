# Config Centralization, Routing Standardization & Targeted Rewrites — Master Plan

**PRD:** `.agent/PROJECT-CONFIG-CENTRALIZATION-PRD.md`
**Status:** ✓ COMPLETE — all phases A–E + R1–R3 + R2.1–R2.9 shipped (2026-05-21)
**Next cycle:** `.agents/plans/PHASE-60-ECOSYSTEM-INTEGRATION-PRD.md` (Phase 60–63)
**Date:** 2026-05-20 (redrawn with rewrite phases after Gemini + Claude joint audit)

---

## Phase 60–63 Execution Sequence (Next Cycle)

**PRD:** `.agents/plans/PHASE-60-ECOSYSTEM-INTEGRATION-PRD.md` (v0.2, all amendments complete)
**Status:** READY — 4/5 sign-off items complete; implementation can begin on Phase 60.1

```
Wave 1 (no rebuild needed):
  60.1-60.2: AIDB bitemporal schema migration + MemoryBroker event_time kwarg
  60.3: memory_superseder valid_until (replaces delete)
  62.4: config/safety-rails.yaml + evidence_safety_handlers rails (AM-G2 early ship)

Wave 2 (rebuild required after 60.1-60.3 + 62.4):
  60.5-60.6: RAGAS eval metrics (embed 100%, Qwen async 10%)
  60.7: aq-qa checks 6.0.1-6.0.5

Wave 3 (Phase 61 — rebuild required):
  61.1-61.3: ContextLifecycleManager (Hot/Warm/Cold, Redis 256MB cap, MLFQ_PRIORITY_LOW)
  61.4-61.5: CLM API routes + MLFQ pressure integration
  63.4-63.5: NixOS impermanence module (batch with Phase 61 rebuild)

Wave 4 (Phase 62 — rebuild required):
  62.1-62.3: nsjail sandbox (NOT Wasmtime — absent from nixpkgs 25.11)
  62.5: aq-qa checks 6.2.1-6.2.3

Wave 5 (Phase 63 — rebuild required):
  63.1-63.3: GraphRAG entity extraction + knowledge graph search + rag_augmentor graph path
  63.6: aq-qa checks 6.3.1-6.3.4
```

**Key amendments to remember (from PRD Sections 10-12):**
- AM-G1/C1: RAGAS faithfulness is async 10% sample; `RAGAS_FAITHFULNESS_ENABLED=false` default
- AM-G2: Safety rails to Phase 60 (not waiting for 62)
- AM-G5/C3: nsjail replaces Wasmtime; Wasmtime not in nixpkgs 25.11
- AM-Q1: Redis Hot-tier cap = 256 MB (not 512 MB — OOM risk at 27 GB budget)
- AM-Q2: Faithfulness scoring ALWAYS needs feature flag on Renoir APU
- AM-C2: CLM uses `config/clm-compaction-prompt.yaml`, not ablation profiles
- AM-C5: `eval_results` needs `metrics JSONB` column; `memory_broker` dedup must pass newer event_time

---

---

## Overview

This plan integrates two concerns:
1. **Config centralization (A–E)** — env var standardization, externalized switchboard profiles, routing policy config, URL alias cleanup, directory governance
2. **Targeted rewrites (R1–R3)** — aq-qa Python framework, coordinator HTTP dispatch thin router, hints_engine decomposition

These are not independent: R1 must deliver a working Python QA harness before R2 migration is safe; config phases A–D must complete before R2 can reference canonical env vars in the new service layer.

---

## Execution Sequence

```
Wave 1 (parallel, no restart needed):
  R1: aq-qa Python framework
  A:  Env var contract YAML

Wave 2 (parallel, after A completes; B+C need nixos-rebuild):
  B:  Externalized switchboard profiles    (nixos-rebuild)
  C:  Routing policy config               (nixos-rebuild)
  D:  URL/key alias standardization       (no restart)
  R3: hints_engine decomposition          (nixos-rebuild to deploy)

Wave 3 (after B+C+D complete):
  E:  Config directory governance         (no restart, CI only)

Wave 4 (after R1 + E + R3 complete — largest scope):
  R2: Coordinator HTTP dispatch rewrite   (nixos-rebuild + Strangler Fig migration)
```

Batch B+C nixos-rebuild into one rebuild cycle. R3 can share the same rebuild.

---

## Phase R1 — aq-qa Python Framework

**Goal:** Replace 2,090-line bash/72-embedded-Python script with a proper Python test framework.
**Depends on:** nothing
**Rebuild required:** No (bash wrapper calls `python3 scripts/testing/harness_qa/main.py`)

| Slice | Task | Owner | Gate |
|-------|------|-------|------|
| R1.1 | Create `scripts/testing/harness_qa/` package skeleton: `main.py`, `core/` (CheckResult, base classes), `checks/` (system.py, network.py, db.py, ai_stack.py), `phases/` (phase groups 0, 1, 2, 3, 4, 5, 54–59), `reporters/` (console, json, summary) | Codex | `python3 -m py_compile scripts/testing/harness_qa/main.py` |
| R1.2 | Migrate all phase 0 checks (67 checks) to Python — each check is a `@check(phase=0, id="X.Y.Z")` decorated function returning `CheckResult` | Codex | `python3 scripts/testing/harness_qa/main.py --phase 0` passes all 67 checks |
| R1.3 | Migrate all non-phase-0 phase checks (phases 1–59) | Codex | `python3 scripts/testing/harness_qa/main.py --all` matches legacy output |
| R1.4 | Replace `scripts/ai/aq-qa` with a thin bash wrapper: `exec python3 "$REPO_ROOT/scripts/testing/harness_qa/main.py" "$@"` | Claude | `aq-qa 0` output identical to pre-migration |
| R1.5 | Add JSON reporter: `aq-qa --format=json` outputs structured results consumable by dashboard | Codex | `aq-qa 0 --format=json \| python3 -m json.tool` exits 0 |

**Commit scope:** `scripts/testing/harness_qa/`, updated `scripts/ai/aq-qa`
**Notes:**
- Keep bash wrapper for backward compat — all existing callers (`Makefile`, `tier0`, `dashboard`, `maeah-acceptance-tests.sh`) continue to work unchanged
- `CheckResult` dataclass: `id`, `phase`, `status` (pass/fail/skip), `message`, `duration_ms`
- Async execution for HTTP checks (use `asyncio.gather` for all `_http_health` equivalents)
- Phase groups map 1:1 to existing `run_phase_N()` functions

---

## Phase A — Env Var Contract

**Goal:** One authoritative YAML document; tier0 gate enforces it going forward.
**Depends on:** nothing (parallel with R1)
**Rebuild required:** No

| Slice | Task | Owner | Gate |
|-------|------|-------|------|
| A.1 | Create `config/env-contract.yaml`: all variable names, canonical names, deprecated aliases, defaults, which service consumes each, layer (NixOS/shell/Python) | Claude/Codex | `python3 -c "import yaml; yaml.safe_load(open('config/env-contract.yaml'))"` |
| A.2 | Add tier0 gate: new `.py`/`.sh` files must not introduce env var names absent from contract | Claude | `scripts/governance/tier0-validation-gate.sh --pre-commit` |
| A.3 | Update `AGENTS.md` — reference `config/env-contract.yaml` as the env var authority | Claude | manual review |

**Commit scope:** `config/env-contract.yaml`, `scripts/governance/tier0-validation-gate.sh`, `AGENTS.md`
**Key content for A.1:**

| Canonical Name | Deprecated Aliases | Service | Layer |
|---|---|---|---|
| `LLAMA_CPP_BASE_URL` | `LLAMA_URL`, `LLAMA_CPP_URL` | coordinator, dashboard, shell | all |
| `HYBRID_COORDINATOR_API_KEY` | `HYBRID_API_KEY`, `AI_STACK_API_KEY` | dashboard, shell | env |
| `HYBRID_COORDINATOR_URL` | `COORDINATOR_URL` | switchboard, dashboard | env |
| `EMBED_BASE_URL` | `EMBED_URL`, `LLAMA_EMBED_URL` | coordinator | env |

---

## Phase B — Externalized Switchboard Profiles

**Goal:** Token budgets in YAML, loaded at startup, validated against ctxSize.
**Depends on:** A (so YAML references canonical env var names)
**Rebuild required:** Yes (NixOS env var propagation)

| Slice | Task | Owner | Gate |
|-------|------|-------|------|
| B.1 | Create `config/switchboard-profiles.yaml` — transcribe all 13 profiles from `switchboard.py` current inline literals; add `ctxSize_min` metadata per profile | Claude/Codex | `python3 -c "import yaml; yaml.safe_load(open('config/switchboard-profiles.yaml'))"` |
| B.2 | Modify `ai-stack/switchboard/switchboard.py`: `_load_profile_catalog()` to accept YAML via `SWB_PROFILE_CATALOG_YAML_FILE` (JSON path is the model to follow; add YAML branch) | Codex | `python3 -m py_compile ai-stack/switchboard/switchboard.py` |
| B.3 | Add startup validation: warn (not crash) if `maxInputTokens + maxOutputTokens > LLAMA_CTX_SIZE - 600` | Codex | `aq-qa 0.5.4` (continue-local profile smoke) |
| B.4 | Wire `SWB_PROFILE_CATALOG_YAML_FILE = config/switchboard-profiles.yaml` in `nix/modules/roles/ai-stack.nix` | Claude | nixos-rebuild switch → `aq-qa 0.5` green |

**Commit scope:** `config/switchboard-profiles.yaml`, `ai-stack/switchboard/switchboard.py`, `nix/modules/roles/ai-stack.nix`

---

## Phase C — Routing Policy Config

**Goal:** `auto_prefer_local` heuristic configurable, not hardcoded.
**Depends on:** A
**Rebuild required:** Yes (coordinator service)

| Slice | Task | Owner | Gate |
|-------|------|-------|------|
| C.1 | Create `config/routing-policy.yaml` — `auto_prefer_local_when`, `intent_routing`, `slot_busy`, `timeout_thresholds` | Claude/Codex | `python3 -c "import yaml; yaml.safe_load(open('config/routing-policy.yaml'))"` |
| C.2 | Modify `extensions/ai_coordinator_handlers.py`: load policy from `AI_ROUTING_POLICY_FILE` at init; replace hardcoded `timeout_s <= 10.0` with configured value; document `prefer_local` default per endpoint | Codex | `python3 -m py_compile` + `aq-qa 0.7.1` smoke |
| C.3 | Wire `AI_ROUTING_POLICY_FILE = config/routing-policy.yaml` in coordinator NixOS service env | Claude | nixos-rebuild switch |

**Commit scope:** `config/routing-policy.yaml`, `ai_coordinator_handlers.py`, `nix/modules/roles/ai-stack.nix`
**Note:** C can share the same nixos-rebuild as B.

---

## Phase D — URL/Key Alias Standardization

**Goal:** Canonical names everywhere; deprecated aliases as backward-compat shims.
**Depends on:** A
**Rebuild required:** No (alias shims cover runtime)

| Slice | Task | Owner | Gate |
|-------|------|-------|------|
| D.1 | `dashboard/backend/api/config/service_endpoints.py`: rename `LLAMA_URL` → `LLAMA_CPP_BASE_URL`; add alias shim for backward compat | Codex | `python3 -m py_compile` + grep confirms 0 raw `LLAMA_URL` reads in new code |
| D.2 | `config/service-endpoints.sh`: rename to canonical; alias shim exports old name for 30-day sunset | Claude | `bash -n` |
| D.3 | `ai-stack/switchboard/switchboard.py`: use `HYBRID_COORDINATOR_URL` canonical (not inline assumption) | Codex | switchboard health smoke |
| D.4 | `dashboard/backend/api/routes/topology.py` + `api/main.py`: remove hardcoded `127.0.0.1:8080` etc., import from `service_endpoints` | Codex | `grep -r "127\.0\.0\.1:[0-9]" dashboard/backend/ \| wc -l` → 0 |
| D.5 | `scripts/ai/aq-qa`, `scripts/ai/edgeai`: use contract variable names | Claude | `aq-qa 0` green |

**Commit scope:** dashboard config, shell configs, topology route
**Note:** D.5 is superseded by R1 — aq-qa is being rewritten. Skip D.5 and validate canonical names during R1 migration.

---

## Phase R3 — hints_engine Decomposition

**Goal:** 3,458-line monolith → 5 focused files, each with a single responsibility.
**Depends on:** nothing (standalone; can run in parallel with B/C/D)
**Rebuild required:** Yes (coordinator reads from nix store)

| Slice | Task | Owner | Gate |
|-------|------|-------|------|
| R3.1 | Create `knowledge/models.py` — extract `Hint` dataclass, `TokenBudgetContext` data type, shared type aliases | Codex | `python3 -m py_compile knowledge/models.py` |
| R3.2 | Create `knowledge/token_manager.py` — extract token estimation, `calculate_context_aware_budget`, `_budget_rationale` | Codex | `python3 -m py_compile` + `from knowledge.token_manager import TokenBudgetContext` in test |
| R3.3 | Create `knowledge/static_rules.py` — extract all CLAUDE.md-derived keyword rules, static routing rule matching (no I/O, no external service calls) | Codex | `python3 -m py_compile`; `grep -c "import hints_engine" knowledge/static_rules.py` = 0 |
| R3.4 | Create `knowledge/gap_analyzer.py` — extract `_is_synthetic_gap`, `_normalize_gap_text`, gap fingerprinting, curated stale gap detection | Codex | `python3 -m py_compile` |
| R3.5 | Update `knowledge/hints_engine.py` — replace extracted code with imports from the 4 new modules; verify ≤900 lines | Codex | `wc -l knowledge/hints_engine.py` ≤900; `python3 -m py_compile` |
| R3.6 | Verify no circular imports: `python3 -c "from knowledge import hints_engine"` | Claude | exit 0 in <2s |
| R3.7 | nixos-rebuild to deploy | User (terminal) | `aq-qa 0` hint checks pass |

**Commit scope:** all 5 `knowledge/*.py` files
**Note:** Commit R3.1–R3.6 in a single atomic commit after all py_compile gates pass. Nixos-rebuild (R3.7) batched with B+C rebuild.

---

## Phase E — Config Directory Governance

**Goal:** Every `config/` file is versioned, owned, and validated in CI.
**Depends on:** B, C, D (all config files present)
**Rebuild required:** No

| Slice | Task | Owner | Gate |
|-------|------|-------|------|
| E.1 | Add `_meta` header (version, owner, last_updated) to all `config/*.json` and `config/*.yaml` that lack one | Codex | tier0 JSON/YAML gate |
| E.2 | Add `scripts/governance/config-directory-lint.sh` — checks for `_meta`, detects duplicate env var declarations across domain-overlapping files | Claude | tier0 gate |
| E.3 | Remove or archive orphaned config files (not referenced by any service) | Codex | grep audit |

**Commit scope:** all `config/` files (meta headers only), new lint script

---

## Phase R2 — Coordinator HTTP Dispatch Rewrite (Strangler Fig)

**Goal:** Replace 2,735-line `http_server.py` god-object with a thin `router.py` (~200 lines) + 4–8 domain service classes.
**Depends on:** R1 (Python QA harness to validate migration safely), E (canonical env vars in new services), R3 (hints_engine importable cleanly)
**Rebuild required:** Yes (each migration batch)

### Domain Services (from Gemini audit)

| Service | File | Endpoints |
|---------|------|-----------|
| `StatusService` | `core/status_service.py` | `/status`, `/api/hardware/state`, `/stats/delegate` |
| `MemoryService` | `memory/memory_service.py` | `/api/memory/facts`, `/memory/journal`, `/memory/supersede` |
| `QueryService` | `query/query_service.py` | `/query`, `/api/query`, `/augment_query` |
| `OrchestrationService` | `workflow/orchestration_service.py` | `/v1/orchestrate`, `/search/tree`, `/workflow/graph/run` |
| `InsightsService` | `telemetry/insights_service.py` | `/api/traces`, `/eval/run`, `/api/logic/search` |
| `ControlService` | `control/control_service.py` | `/admin/v1/*`, `/control/budget/*`, `/control/fleet/*` |
| `AgentService` | `agent/agent_service.py` | `/agent/lifecycle/*`, `/runtime/*`, `/a2a/*` |

### Migration Slices (Strangler Fig)

| Slice | Task | Owner | Gate |
|-------|------|-------|------|
| R2.1 | Create `router.py` skeleton — aiohttp Application, middleware pipeline (auth, rate, otel), empty routing table; `http_server.py` still handles all requests | Codex | `python3 -m py_compile router.py`; existing aq-qa 0 unchanged |
| R2.2 | Extract `StatusService` + wire into `router.py`; old handlers remain in `http_server.py` as fallback | Codex | `/status`, `/api/hardware/state` smoke; R1 phase 0 green |
| R2.3 | Extract `MemoryService` | Codex | memory-related aq-qa checks pass |
| R2.4 | Extract `QueryService` | Codex | aq-qa 0.7.x green; latency ≤pre-migration baseline |
| R2.5 | Extract `OrchestrationService` | Codex | aq-qa orchestration checks green |
| R2.6 | Extract `InsightsService`, `ControlService`, `AgentService` | Codex | aq-qa 0: 0 failed |
| R2.7 | Auth middleware consolidated into `middleware/auth.py`; inline auth checks removed | Claude | `grep -r "_is_loopback_agent_request\|X-API-Key" http_server.py \| wc -l` = 0 |
| R2.8 | `http_server.py` reduced to ≤100-line compatibility shim (imports from `router.py`) | Codex | `wc -l http_server.py` ≤100 |
| R2.9 | nixos-rebuild; full aq-qa 0 pass; remove compatibility shim | User (terminal) | `aq-qa 0` 0 failed, `wc -l http_server.py` → file deleted |

**Commit scope:** `router.py`, `core/`, `memory/`, `query/`, `workflow/`, `telemetry/`, `control/`, `agent/` service dirs; updated `http_server.py` at each slice
**Note:** Each R2.x slice is an independent commit with its own nixos-rebuild. Do NOT batch R2 slices — rollback must be possible per service.

---

## Execution Calendar (suggested pacing)

| When | Phases | Rebuild |
|------|--------|---------|
| Day 1 | R1.1–R1.2 (phase 0 migration) + A.1 | No |
| Day 2 | R1.3–R1.5 (remaining phases) + A.2–A.3 | No |
| Day 3 | B.1–B.3 + C.1–C.2 + D.1–D.4 + R3.1–R3.4 | No (code prep) |
| Day 4 | B.4 + C.3 + R3.5–R3.6 → single nixos-rebuild | **Yes (batch)** |
| Day 5 | E.1–E.3 | No |
| Day 6+ | R2.1–R2.2 → nixos-rebuild | **Yes (R2 start)** |
| +rolling | R2.3–R2.9 (one service per day) → nixos-rebuild per slice | **Yes (each slice)** |

---

## Handoff Notes for Codex

**First task when resuming:**
```bash
aq-session-start --task "config-centralization R1.1: create scripts/testing/harness_qa/ skeleton"
```

**Execution order:**
1. R1.1 first — Python QA skeleton (no service changes, safest start)
2. A.1 — env-contract.yaml in parallel (pure data file)
3. After R1 + A complete: B, C, D, R3 all parallelizable
4. Gate every slice: `bash -n` / `py_compile` / `aq-qa 0` before commit
5. Never change any API surface, endpoint path, or NixOS option name
6. Never batch B+C into one commit — keep separate for rollback hygiene
7. R2 only begins after R1 delivers a working Python harness (R2 migration is too risky without it)

**Critical invariant:** Every nixos-rebuild must be followed by `aq-qa 0` before the next phase begins.
