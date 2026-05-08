# System Reset — Multi-Agent Harness Consolidation
**Created:** 2026-05-08  
**PDR:** `docs/architecture/SYSTEM-RESET-PDR-2026-05.md`  
**Status:** ACTIVE

## Phase Tracker

| Phase | Name | Priority | Status | Sessions |
|---|---|---|---|---|
| A | VSCodium / MCP Bridge Fix | IMMEDIATE | ✅ DONE (92d7d510) | 1 |
| B.1 | hybrid-coordinator audit + module map | HIGH | ✅ DONE (4e909111) | 1 |
| B.2 | Resolve confirmed duplicates | HIGH | ✅ DONE (f80e59ec) | 1 |
| B.3 | Domain subdirectory split | HIGH | ⬜ NOT STARTED | ~1 |
| C.1 | Dead module import audit | MEDIUM | ✅ DONE (2026-05-08) | 0.5 |
| C.2 | Archive confirmed dead modules | MEDIUM | 🔄 PARTIAL (federated-learning: 62a86e63) | ~0.5 |
| C.3 | Gitignore __pycache__ | MEDIUM | ✅ NO-OP (already gitignored) | 0 |
| D.1 | Data retention scripts | MEDIUM | ✅ DONE (41f82a55) | 0.5 |
| D.2 | NixOS systemd timer | MEDIUM | ✅ DONE (pending commit) | 0.5 |
| E | Script/test consolidation | LOW | ⬜ NOT STARTED | ~2 |

## Phase A Detail — VSCodium Fix

**Problem:** mcp-bridge-hybrid.py uses blocking urllib.request in a synchronous stdin loop.  
Any MCP tool call blocks for up to 30s → Continue.dev / VSCodium hangs.

**Files to change:**
- `scripts/ai/mcp-bridge-hybrid.py` — convert to async event loop + run_in_executor
- `ai-stack/mcp-servers/hybrid-coordinator/hints_engine.py` — add 30s response cache
- `/home/hyperd/.continue/config.json` — add debounceDelay to aq-hints provider

**Acceptance:** VSCodium does not hang when typing in Continue chat. `aq-qa 0` ≥ 40 passes.

## Phase B Detail — hybrid-coordinator Decomposition

**Problem:** 111 Python files in one flat directory, 5 duplicate module sets, 22K LOC monolith.

**Duplicate sets to resolve:**
1. `garbage_collection.py` + `garbage_collector.py` → keep `garbage_collection.py`
2. `continuous_learning.py` + `continuous_learning_daemon.py` + `real_time_learning_engine.py` → merge into `continuous_learning.py` with daemon mode
3. `memory_manager.py` + `memory_context_handlers.py` + `agentic_memory_journal.py` → consolidate
4. `harness_sdk.ts` + `harness_sdk.js` + `harness_sdk.d.ts` — verify if any live service uses them; remove if not

**Target structure:**
```
hybrid-coordinator/
├── core/        (route_handler, http_server, llm_router, config)
├── workflow/    (lifecycle_fsm, intake_gateway, safety_gate, workflow_*)
├── knowledge/   (hints_engine, search_router, memory_manager, semantic_cache)
└── extensions/  (AGI features, learning, monitoring — optional-load)
```

**Constraint:** core/ must NOT import from extensions/. This enforces the boundary.

## Phase C Detail — Dead Module Pruning

**Candidate directories (not confirmed dead — must grep before archive):**
- `ai-stack/federated-learning/`
- `ai-stack/meta-optimization/`
- `ai-stack/autonomous-orchestrator/`
- `ai-stack/real-time-learning/`
- `ai-stack/trading-agents/` (standalone, not cross-service)
- `ai-stack/world-model/` (has NixOS module — check if metrics consumed)
- `ai-stack/affective-engine/` (has NixOS module — check service health)

**Check command:**
```bash
grep -r "<dirname>" nix/modules/services/ --include="*.nix" | grep -v '#'
```

## Phase D Detail — Data Retention

**Write these scripts:**
- `scripts/data/trim-temporal-facts.sh` — keep last 30 days in `.aidb/temporal_facts.json`
- `scripts/data/trim-snapshots.sh` — keep last 7 days in `ai-stack/snapshots/*.jsonl`

**NixOS timer (in `nix/modules/services/data-retention.nix`):**
```nix
systemd.timers.data-retention = {
  wantedBy = [ "timers.target" ];
  timerConfig.OnCalendar = "daily";
};
```

## Invariants (Do Not Break)

1. Never hardcode ports — always read from options.nix or env vars
2. No bare pip install — pure Python stdlib + existing deps
3. Phase 28 safety gating blocked until Phase B.3 complete
4. No nixos-rebuild until Phase A validated
5. Archive first, delete never

## Session Handoff Protocol

At the start of each session working on this plan:
1. Read this file to understand current phase status
2. Read `docs/architecture/SYSTEM-RESET-PDR-2026-05.md` for full context
3. Check git log for what was committed since last session
4. Update phase status in this file before starting work
5. Commit this file with each phase completion

## Remaining C.2 Archive Candidates (with blockers)

- `ai-stack/autonomous-orchestrator/` — BLOCKER: scripts/ai/autonomous-coordinator*.sh references security_policy.json inside it. Update those scripts first.
- `ai-stack/agentic-patterns/` — BLOCKER: dashboard/backend/api/services/ai_insights.py constructs path strings into it. Update ai_insights.py to not require those paths.

## Evidence Log

| Date | Phase | Action | Commit |
|---|---|---|---|
| 2026-05-08 | A | VSCodium MCP bridge fix + hints cache | 92d7d510 |
| 2026-05-08 | D.1 | Data retention scripts + fix temporal_facts | 41f82a55 |
| 2026-05-08 | C.2 | Archive federated-learning | 62a86e63 |
| 2026-05-08 | B.2 | Archive garbage_collection.py; fix ops_handlers stale import | f80e59ec |
| 2026-05-08 | B.1 | hybrid-coordinator module map | 4e909111 |
| 2026-05-08 | — | Phase 27 staged work committed | f988b361 |
| 2026-05-08 | — | PDR written, plan created | c24213a3 |
