# Architecture Revamp — All Slices Complete

**Agent:** Claude Sonnet 4.6 (Orchestrator)
**Date:** 2026-05-18
**Source contract:** `.agents/plans/ARCH-REVAMP-IMPL-CONTRACT.md`

---

## Slice Status — Final

### Nix/Switchboard Slices (N-*)

| Slice | Status | Notes |
|-------|--------|-------|
| N-1 | ✅ Done (prior) | `coordinator-internal` profile in `switchboard.nix:356`; `llm_client.py:464` injects header |
| N-2 | ✅ Done (prior) | `switchboard.py:1774-1782` forces `stream=True` for all local profiles except `coordinator-internal`, `embedding-local`, `local-tool-calling` |
| N-3 | ✅ Done (prior) | `SWB_HINTS_TIMEOUT_S` default 3.0; `_get_hints()` has 1 retry with 0.5s sleep; `X-AI-Hints-Skipped` header set on failure |
| N-4 | ✅ Done (prior) | Hints prepended to FIRST sys message (`sys_idxs[0]`) at `switchboard.py:1756` |
| N-5 | ✅ Done (prior) | `X-AI-Fallback: budget-exceeded` at `switchboard.py:1921` |
| N-6 | ✅ Done (prior) | `X-AI-Model-Alias` at `switchboard.py:1922` |
| N-7 | ✅ Done (prior) | `switchboard.py:1697-1698` returns HTTP 503 `{"error":"loop_detected"}` on 2nd consecutive loop trigger |

### Coordinator Python Slices (C-*)

| Slice | Status | Notes |
|-------|--------|-------|
| C-1 | ✅ Done (prior) | `llm_client.py:464` injects `X-AI-Profile: coordinator-internal` |
| C-2 | ✅ Done (prior) | `_probe_remote_fallback()` uses `status_code < 400`; 4xx treated as unhealthy |
| C-3 | ✅ Clean | No hardcoded `127.0.0.1` in `agent_executor.py` |
| C-4 | ✅ Done (commit `c885faa0`) | `analyze_prompt` in `local-orchestrator/router.py`: when QUERY pattern matches AND implementation keywords score > 0, defer to keyword scoring. "how can I implement X" → `IMPLEMENTATION`. 11-case behavioral suite passes. |
| C-5 | ✅ Done (prior) | `router.py` imports from `routing_contract.py`; `AgentBackend` enum is shim; `RouteDecision = RoutingDecision` alias |
| C-6 | ✅ Done (commit `d8df8ff6`) | `local-agents/task_router.py` deleted; `__init__.py` import block removed; `RoutingDecision` export preserved from canonical `routing_contract` |

### Module Audit Slices (G-*)

| Slice | Status | Finding |
|-------|--------|---------|
| G-1 | ✅ Audited | Only `garbage_collector.py` exists (no dead `garbage_collection.py`). Callers: `server.py:711` (GarbageCollector, run_gc_scheduler). Single canonical file. No action needed. |
| G-2 | ✅ Audited | `continuous_learning.py` → `ContinuousLearningPipeline` (batch/session learning daemon) and `real_time_learning_engine.py` → gap detection, hint quality, online learner. **Complementary, not overlapping.** Keep both. |
| G-3 | ✅ Approved (prior, `gemini-G3-review.md`) | Gemini approved C-5/C-6 adapter approach |
| G-4 | ✅ Audited | All live doc references use `ai-hybrid-coordinator` (correct systemd unit name). No rename needed. Archive docs untouched. |

### Docs Slices (Q-*)

| Slice | Status | Notes |
|-------|--------|-------|
| Q-1 | ✅ Done (prior) | `[compact-guidance]` contract documented in `46-SWITCHBOARD-PROFILES.md:120-135` |
| Q-2 | ✅ Done (prior) | Stale-hints trade-off documented in `REQUEST-ROUTING-FLOW.md:73` |
| Q-3 | ✅ Done (prior) | `forceProvider=null` auto-resolution documented in `REQUEST-ROUTING-FLOW.md:71` |
| Q-4 | ➡ Deferred | Phase B.2 file map (121 coordinator Python files → subdir) — low priority, no functional impact |

---

## Round 4 — G-1/G-2 Execution Decisions

Based on audit findings:
- **G-1**: `garbage_collector.py` — single canonical file, no dead duplicate, no deletion needed
- **G-2**: Keep both `continuous_learning` and `real_time_learning_engine` — serve distinct functions

No deletion/merge actions required for Round 4.

---

## Additional Fixes This Session

| Commit | Fix |
|--------|-----|
| `7b7d2dc5` | Dashboard: `graph.centerAt`/`graph.zoom` (2D API) → `graph.cameraPosition` (correct 3D API) |
| `185ed61c` | Cleanup: health monitor timeout 5→10s; collab screenshot tracked; root scratch files removed |
| `be65fdc7` | Gemini hardening: /tmp amplification, phantom profiles, duplicate QA runners, fake telemetry |

---

## System State at Close

- **aq-qa:** 64+ checks passing, 0 failed
- **tier0:** 14/14 gates passing
- **Services:** 13/13 healthy (coordinator, switchboard, aidb, llama.cpp, qdrant, etc.)
- **Dashboard:** No JS errors; 3D graph node-click working
- **No nixos-rebuild required** for today's changes (Python/JS only)

---

## Remaining Work (Q-4, future)

- Q-4: Phase B.2 file map for coordinator Python reorganization — deferred to dedicated phase
- C-5/C-6 full adapter layer in coordinator (if `routing_contract.RoutingDecision` needs to fully replace legacy coordinator internal routing decisions) — out of scope for current revamp
