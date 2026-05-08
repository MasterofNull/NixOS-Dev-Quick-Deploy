# System Reset PDR — Multi-Agent Harness Consolidation
**Date:** 2026-05-08  
**Authors:** Claude Sonnet 4.6 (architect/synthesizer) + Codex (code auditor)  
**Status:** DRAFT — awaiting joint acceptance  
**Scope:** Full architectural review of the NixOS-Dev-Quick-Deploy AI harness

---

## 1. Executive Summary

The harness has grown ad hoc through 28 development phases, accumulating significant architectural debt. Core services are well-designed but the system as a whole has evolved without architectural governance. This PDR identifies five problem classes, proposes a consolidation architecture, and defines a phased development plan that can be executed across multiple agent sessions.

**TL;DR for implementation teams:**
1. Fix VSCodium hanging immediately (synchronous MCP bridge — 1 session)
2. Consolidate hybrid-coordinator from 111 files to a bounded service (~3 sessions)
3. Prune dead/duplicate modules and stale tests (~2 sessions)
4. Establish data retention and storage policies (1 session)
5. Define and enforce a stable module contract going forward (ongoing)

---

## 2. System Inventory (Audited 2026-05-08)

| Component | Files | Size | LOC |
|---|---|---|---|
| hybrid-coordinator | 111 Python | 6.7MB | ~22K |
| aidb/server.py | 1 Python | — | 3,684 |
| ai-stack/ (outside mcp-servers) | 50+ dirs | 28MB total | ~50K |
| scripts/ai/ | 152 executables | 13MB | — |
| scripts/testing/ | 217 test files | — | ~42K |
| .agent/ docs | 122 markdown | 9MB | — |
| Total Python (ai-stack) | — | — | 170,410 |

**File count anomaly:** 45,014 total files — primary driver is `.forks/nixpkgs` (nixpkgs upstream subtree). This is expected but should be confirmed out-of-scope for the code cleanup.

---

## 3. Problem Statements

### P1 — VSCodium/Continue.dev Hanging (SEVERITY: CRITICAL — USER-FACING)

**Root cause (confirmed):**

`scripts/ai/mcp-bridge-hybrid.py` `main()` is a fully synchronous stdin-reading loop.  
The `_post()` helper uses `urllib.request.urlopen(timeout=30)` — a blocking call.  
When Continue.dev invokes any MCP tool:
1. Bridge calls `_post()` → blocks the process for up to 30s
2. No other MCP messages can be handled during the block
3. The `aq-hints` context provider calls `:8003/hints` on **every chat message** (same path)
4. If hybrid-coordinator must call Qwen3-35B (90–120s inference), the bridge timeout fires at 30s
5. Result: Continue hangs, VSCodium UI freezes

`asyncio` is imported but unused — the event loop is never started.

**Secondary cause:** `/hints` endpoint has no cached fast-path. Every call may trigger LLM.

---

### P2 — Monolithic hybrid-coordinator (SEVERITY: HIGH)

**Observation:** 111 Python files in a single flat directory — effectively an unstructured monolith.

**Duplicate/overlapping modules (confirmed by Codex audit):**
| Duplicate Set | Files |
|---|---|
| Garbage collection | `garbage_collection.py` + `garbage_collector.py` |
| Continuous learning | `continuous_learning.py` + `continuous_learning_daemon.py` + `real_time_learning_engine.py` |
| Harness SDK | `harness_sdk.py` + `harness_sdk.ts` + `harness_sdk.js` + `harness_sdk.d.ts` |
| Memory systems | `memory_manager.py` + `memory_context_handlers.py` + `agentic_memory_journal.py` |
| Orchestration | `orchestration_utils.py` + `orchestration_handlers.py` + `coordinator.py` + `ai_coordinator.py` |

**Import coupling (from http_server.py):** Imports from 25+ internal modules at startup. Any import failure kills the whole service.

**Consequence:** New developers (or agents) cannot reason about the system without reading all 111 files. Changes in one module have unpredictable side effects across unrelated features. Deployment risk is high.

---

### P3 — Dead and Duplicate ai-stack Modules (SEVERITY: MEDIUM)

The `ai-stack/` directory has 50+ subdirectories outside `mcp-servers/`. Many appear to be feature explorations that were never integrated into a running service:

**Likely dormant (not imported by any running service):**
- `federated-learning/` — no NixOS service module references it
- `meta-optimization/` — no service endpoint wires it
- `autonomous-orchestrator/` — separate from `local-orchestrator/` and `orchestration/`
- `real-time-learning/` — separate from `continuous_learning_daemon.py`
- `affective-engine/` — has a NixOS module but unclear if metrics are consumed
- `trading-agents/` — standalone feature, no cross-service dependency
- `world-model/` — has NixOS module but not wired to main query path

**Overlapping orchestration layers (4 separate concerns, no clear boundary):**
- `ai-stack/orchestration/` — `agent_hq.py` (754 lines)
- `ai-stack/agentic-patterns/` — `pipeline_orchestration.py` (945 lines)
- `ai-stack/local-orchestrator/` — separate from hybrid-coordinator
- `ai-stack/autonomous-orchestrator/` — separate from all above

No clear protocol separating which layer owns which lifecycle phase.

---

### P4 — Storage and Data Accumulation (SEVERITY: MEDIUM)

**Identified accumulation points:**
| Location | Description | Risk |
|---|---|---|
| `.aidb/temporal_facts.json` | 2.1MB, unbounded growth | Will eventually cause slow AIDB startup |
| `ai-stack/snapshots/*.jsonl` | Query gaps + imported docs | No rotation policy |
| 96 `__pycache__` dirs | Tracked in git | Repo pollution, confuses file counts |
| `docs/architecture/adk-discovery-log.jsonl` | Architecture trace log | Unbounded |
| `.agent/` (9MB) | 122 markdown files including old phase summaries | Stale docs consuming agent context |
| `/var/lib/nixos-ai-stack/` | Runtime state (Redis, Qdrant, PostgreSQL) | No documented retention policy |

**Root cause:** No data lifecycle policy was established when new storage was added. Each phase added new write paths without corresponding cleanup.

---

### P5 — Test and Script Proliferation (SEVERITY: LOW-MEDIUM)

**Testing:**
- 217 test files in `scripts/testing/` (~42K lines)
- Tests mixed with source in `ai-stack/mcp-servers/hybrid-coordinator/` (inline test_*.py)
- No clear distinction between: unit tests, integration tests, smoke tests, benchmarks
- Unknown fraction are stale (not run in recent phases)

**Scripts:**
- 152 executables in `scripts/ai/` (aq-* namespace)
- High overlap: `aq-runtime-diagnose`, `aq-runtime-act`, `aq-runtime-plan`, `aq-runtime-remediate`, `aq-system-act` all address runtime diagnosis
- `aq-collaborate`, `aq-delegate`, `harness-rpc.js` all provide delegation primitives

**Consequence:** High cognitive overhead for agents. Agents pick wrong tool → echoes and redundant calls.

---

## 4. Architecture Target State

### 4.1 hybrid-coordinator — Bounded Service Model

Split the 111-file monolith into **4 bounded domains** with explicit interfaces:

```
hybrid-coordinator/
├── core/                   # Route handling, HTTP server, config — must stay lean
│   ├── http_server.py      # aiohttp app + route registration only
│   ├── route_handler.py    # Primary routing logic
│   ├── llm_router.py       # LLM model selection
│   └── config.py           # Service config
│
├── workflow/               # Session lifecycle, UAG FSM, planning
│   ├── lifecycle_fsm.py
│   ├── intake_gateway.py
│   ├── workflow_session_handlers.py
│   ├── workflow_executor.py
│   ├── workflow_planning.py
│   └── safety_gate.py      # Phase 28 addition
│
├── knowledge/              # Search, hints, AIDB, context, memory
│   ├── hints_engine.py
│   ├── search_router.py
│   ├── memory_manager.py   # (consolidates 3 memory modules)
│   ├── semantic_cache.py
│   └── query_expansion.py
│
└── extensions/             # AGI features, learning, monitoring (optional-load)
    ├── continuous_learning.py  # (consolidates 3 learning modules)
    ├── affective_handlers.py
    ├── identity_handlers.py
    ├── model_optimization.py
    └── ...
```

**Migration rule:** The `extensions/` domain is optional-load — services in `core/` must not import from `extensions/`. This breaks the hard coupling that makes the service fragile.

### 4.2 MCP Bridge — Non-Blocking Fix

`mcp-bridge-hybrid.py` must use non-blocking HTTP:

```python
# Replace urllib blocking calls with run_in_executor pattern
import concurrent.futures
_executor = concurrent.futures.ThreadPoolExecutor(max_workers=4)

async def _post_async(url, payload, key):
    loop = asyncio.get_event_loop()
    return await loop.run_in_executor(_executor, _post_sync, url, payload, key)
```

Or simpler: replace the synchronous `main()` loop with an asyncio event loop that runs HTTP calls in a thread pool. This allows multiple concurrent MCP requests without blocking.

**Also required:**
- `/hints` fast-path: return cached hints without LLM when last update < 30s
- Reduce aq-hints context provider call frequency (debounce or session-scoped)
- MCP bridge timeout: 5s for hints/health, 30s for planning tools, 120s for LLM tools

### 4.3 ai-stack — Module Classification

Classify all 50+ subdirectories into three tiers:

| Tier | Criteria | Action |
|---|---|---|
| **Active Service** | Has running NixOS systemd unit OR is imported by hybrid-coordinator core | Keep, maintain |
| **Candidate Archive** | No active service, no imports in 3+ months, no phase reference | Move to `archive/` |
| **Experimental** | Valuable concept but not production-ready | Move to `ai-stack/experiments/`, no import from production code |

### 4.4 Data Lifecycle Policy

| Store | Retention | Enforcement |
|---|---|---|
| `temporal_facts.json` | 30 days rolling | cron trim script |
| `snapshots/*.jsonl` | 7 days | cron trim script |
| `__pycache__` | Not tracked | Add to `.gitignore` |
| Redis session state | TTL already set | Verify TTL in options.nix |
| AIDB documents | Project-scoped, no auto-delete | Manual audit per quarter |

### 4.5 Script/Test Canonicalization

**aq-* scripts:** Consolidate overlapping runtime diagnosis tools:
- `aq-runtime-diagnose + aq-runtime-plan + aq-runtime-act + aq-runtime-remediate` → single `aq-runtime` with subcommands

**Test files:** Establish three canonical test suites:
1. `scripts/testing/smoke/` — Fast checks only (< 5s), run on every pre-commit
2. `scripts/testing/integration/` — Real services, run post-deploy
3. `scripts/testing/benchmarks/` — Long-running, run manually

Move inline `test_*.py` files from hybrid-coordinator into appropriate suites.

---

## 5. Development Plan

### Phase A — VSCodium Fix (Priority: IMMEDIATE)
**Owner:** Implementer | **Estimate:** 1 session

**A.1 — Non-blocking MCP bridge**
- Refactor `mcp-bridge-hybrid.py` `main()` to async event loop
- Replace `_post`/`_get` with `run_in_executor` wrappers
- Add fallback responses: if hybrid-coordinator unreachable → return static hints cache

**A.2 — /hints endpoint fast-path**
- Add 30s response cache to `hints_engine.py`
- Return cached response without LLM if cache hit
- Add `X-Hints-Cached: true` header for observability

**A.3 — Continue config debounce**
- Add `debounceDelay: 500` to aq-hints context provider config
- Reduces context provider calls from every keystroke to 500ms idle

**Validation:** Open VSCodium, type in Continue chat, verify no hang. Run `aq-qa 0`.

---

### Phase B — hybrid-coordinator Domain Decomposition (Priority: HIGH)
**Owner:** Architect + Implementer | **Estimate:** 3 sessions

**B.1 — Audit and classify 111 files**
- Categorize each file: core | workflow | knowledge | extensions | dead
- Identify the 5 duplicate module sets — pick canonical, mark others for removal
- Output: `docs/architecture/hybrid-coordinator-module-map.md`

**B.2 — Remove confirmed duplicates**
- Merge `garbage_collection.py` + `garbage_collector.py` → single module
- Merge `continuous_learning.py` + `continuous_learning_daemon.py` + `real_time_learning_engine.py` → single module with daemon mode flag
- Merge 3 memory modules → single `memory_manager.py`
- Remove non-Python SDK files (harness_sdk.ts, .js, .d.ts) if unused by any live service

**B.3 — Create domain subdirectories + move files**
- Create `core/`, `workflow/`, `knowledge/`, `extensions/` under hybrid-coordinator
- Move files per classification from B.1
- Update all internal imports
- Validate: `python3 -m py_compile` all modules + `aq-qa 0`

---

### Phase C — Dead Module Pruning (Priority: MEDIUM)
**Owner:** Implementer | **Estimate:** 2 sessions

**C.1 — Confirm dead modules via import audit**
- For each `ai-stack/` subdirectory outside mcp-servers: check if any running NixOS service imports it
- Script: `grep -r "<dirname>" nix/modules/services/ --include="*.nix"`
- List confirmed dead dirs

**C.2 — Archive confirmed dead modules**
- Move to `archive/ai-stack-deprecated-$(date +%Y-%m)/`
- Update `.gitignore` to track archive separately
- Do NOT delete — preserve for reference

**C.3 — Gitignore __pycache__**
- Add `**/__pycache__/` to `.gitignore`
- Run `git rm -r --cached */__pycache__` to untrack existing

---

### Phase D — Data Lifecycle Policy (Priority: MEDIUM)
**Owner:** Implementer | **Estimate:** 1 session

**D.1 — Implement data retention cron scripts**
- `scripts/data/trim-temporal-facts.sh` — keep last 30 days
- `scripts/data/trim-snapshots.sh` — keep last 7 days of JSONL
- Add both to NixOS cron (systemd timer)

**D.2 — Verify Redis TTL policy**
- Check `nix/modules/core/options.nix` for session TTL settings
- Verify hybrid-coordinator sessions expire (current: Redis TTL handles it)
- Document retention policy in `docs/operations/DATA-RETENTION-POLICY.md`

---

### Phase E — Script/Test Consolidation (Priority: LOW)
**Owner:** Implementer | **Estimate:** 2 sessions

**E.1 — Audit test files**
- Identify which test files are run by `scripts/governance/tier0-validation-gate.sh`
- Mark stale tests (not referenced anywhere, older than 60 days)
- Move stale tests to `archive/tests-deprecated/`

**E.2 — Consolidate aq-runtime scripts**
- Create `scripts/ai/aq-runtime` with subcommands: `diagnose`, `plan`, `act`, `remediate`
- Keep existing scripts as thin wrappers that call the new canonical
- Update AGENTS.md reference table

---

## 6. Phase Dependencies and Sequencing

```
Phase A (VSCodium) — INDEPENDENT, do first
Phase B (hybrid-coordinator) — after A; B.1 before B.2 before B.3
Phase C (dead modules) — after B.1 classification
Phase D (data) — independent of B and C
Phase E (scripts) — after C
```

**Do not start Phase B.3 (file moves) until Phase B.1 (audit) is complete.**  
File moves without a complete import map will break the service.

---

## 7. What We Are NOT Doing

- No new features during consolidation phases A–D
- No Phase 28 (safety gating) implementation until after Phase A (VSCodium fix)
- No nixos-rebuild until Phase A is validated in current session
- No deletion of any code — archive only
- No changes to: options.nix port definitions, NixOS module structure, switchboard profiles

---

## 8. Acceptance Criteria

Per phase:
- [ ] `python3 -m py_compile` all modified modules — zero errors
- [ ] `aq-qa 0` — ≥ 40 passed / 0 failed
- [ ] `scripts/governance/tier0-validation-gate.sh --pre-commit` — 8/8
- [ ] VSCodium: no hang on MCP tool call (Phase A specific)
- [ ] hybrid-coordinator starts clean after domain split (Phase B specific)

Final:
- [ ] hybrid-coordinator flat file count ≤ 30 in root dir (domain dirs created)
- [ ] No duplicate module pairs remain
- [ ] `mcp-bridge-hybrid.py` has asyncio event loop for HTTP calls
- [ ] Data retention cron jobs deployed and tested
- [ ] `__pycache__` removed from git tracking

---

## 9. Risk Register

| Risk | Likelihood | Impact | Mitigation |
|---|---|---|---|
| Import path breaks during domain split | HIGH | HIGH | Run py_compile + aq-qa after each file move |
| Continue.dev cache invalidation after MCP bridge change | MEDIUM | MEDIUM | Test in VSCodium before committing |
| Archived "dead" module was actually imported | MEDIUM | HIGH | Confirm via grep before archive, not just assume |
| temporal_facts.json trim removes active data | LOW | MEDIUM | Trim to 30 days, not full delete |
| Phase 28 work conflicts with Phase B | LOW | MEDIUM | Block Phase 28 until B.3 complete |

---

## 10. Joint Agreement Checkpoint

This PDR was produced by:
- **Claude Sonnet 4.6** — architectural analysis, risk synthesis, problem framing
- **Codex** — code-level audit (confirmed: 111 HC files, 5 duplicate module sets, sync MCP bridge, 96 __pycache__ dirs)

**Next action:** Codex reviews this PDR and confirms or amends the development plan. Both agents commit to the phase sequence before implementation begins.

---

*PDR stored at: `docs/architecture/SYSTEM-RESET-PDR-2026-05.md`*  
*Plan tracker: `.agents/plans/system-reset-plan-2026-05.md` (created separately)*  
*Memory: stored in `/home/hyperd/.claude/projects/.../memory/`*
