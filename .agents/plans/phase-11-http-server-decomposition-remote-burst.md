# Phase 11 — http_server.py Decomposition + Remote Cloud Burst

Status: `in progress — phases 11.2 and 11.3 complete`
Created: 2026-04-26
Owner: Claude (orchestrator) / Qwen (implementation slices)
Predecessor: Phase 10 (complete — pending nixos-rebuild deployment)

## Deployment Gate

Phase 8+9+10 commits are still awaiting `sudo nixos-rebuild switch --flake .#nixos`.
Run that **first** before starting Phase 11 implementation to ensure the baseline is
the deployed state, not a stale service build.

---

## Objective

Two independent improvements identified from the strategic re-evaluation (2026-04-26):

1. **http_server.py God Object** — 13,446 lines (vs target <1000). Phase 6 applied
   the same decomposition to server.py (3611 → 779 lines). Phase 11 applies it here.
2. **Remote Cloud Burst** — 100% local routing (7d). Hybrid coordinator is not hybrid.
   Define and implement the automatic remote routing trigger when local is saturated
   or query complexity exceeds local model capability.

---

## Evidence

| Signal                          | Value               | Target                            |
| ------------------------------- | ------------------- | --------------------------------- |
| http_server.py line count       | 11,404              | ≤1,000 (routing+wiring only)      |
| Remote routing share (7d)       | 0%                  | ≥10% for complex/overflow queries |
| ai_coordinator_delegate success | 23.5% (pre-rebuild) | ≥90% (post-rebuild)               |
| route_search P95                | 59,496ms            | ≤15,000ms (post-rebuild cap)      |
| Local queue_depth               | 0 (idle)            | burst trigger when >0 sustained   |

---

## Scope Lock

In scope:
- Phase 11.1: Audit http_server.py — map handler groups to extraction targets
- Phase 11.2: Extract delegation handler group into `delegation_handlers.py`
- Phase 11.3: Extract workflow handler group into `workflow_session_handlers.py`
- Phase 11.4: Extract OpenAI-compat + A2A handler groups into `openai_a2a_handlers.py`
- Phase 11.5: Extract learning/feedback/alert/cache groups into `ops_handlers.py`
- Phase 11.6: Cloud burst trigger — define routing rules in `routing-config.json` and
  wire activation in `route_handler.py` (no new service units)
- Phase 11.7: Validation — contract tests pass, http_server.py < 2000 lines, remote
  routing activates for at least one synthetic test query

Out of scope:
- Model upgrades (separate concern — see registry.json for Qwen3 candidates)
- New NixOS service units
- Changes to Qdrant schema or AIDB
- SSE streaming or parallel retrieval (already in Phase 8 commits awaiting rebuild)

---

## Phase 11.1 — Handler Group Audit

**Goal**: Map all 168 functions/classes in http_server.py to extraction targets.

**Existing extracted modules** (already in `ai-stack/mcp-servers/hybrid-coordinator/`):
- `route_handler.py`, `search_router.py`, `memory_manager.py`, `hints_engine.py`
- `workflow_executor.py`, `yaml_workflow_handlers.py`, `harness_eval.py`
- `capability_discovery.py`, `metrics.py`, `semantic_cache.py`
- `web_research.py`, `browser_research.py`, `research_workflows.py`
- `llm_router.py`, `llm_client.py`, `progressive_disclosure.py`

**Identified extraction targets** (groups still in http_server.py):

| Target Module                    | Handler Group                                                                                                                                                                                                                               | Approx Lines |
| -------------------------------- | ------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- | ------------ |
| `delegation_handlers.py`         | `_build_delegation_fallback_chain`, `_select_next_available_delegation_target`, `_assess_delegated_response_quality`, `_optimize_delegated_messages`, `_delegated_quality_status_snapshot`, and all delegate-path helpers (~lines 938–1705) | ~800         |
| `workflow_session_handlers.py`   | `handle_workflow_*`, `handle_workflow_session_*`, workflow sessions CRUD, blueprint loading (~lines 1847–3000)                                                                                                                              | ~1200        |
| `openai_a2a_handlers.py`         | `handle_openai_*`, `handle_well_known_*`, `_proxy_openai_request_via_coordinator` (~lines 674–900)                                                                                                                                          | ~300         |
| `ops_handlers.py`                | `handle_learning_*`, `handle_feedback*`, `handle_alert*`, `handle_cache_*`, `handle_model_*` (~lines 3000–5000)                                                                                                                             | ~2000        |
| `real_time_learning_handlers.py` | `_apply_real_time_learning`, `_apply_meta_learning`, `_capability_gap_*`, `_real_time_learning_*`, `_meta_learning_*` (~lines 1353–1705)                                                                                                    | ~400         |

**Success metric**: A documented map exists in this file's table above with line ranges
confirmed by grep. No code changes in this slice.

---

## Phase 11.2 — Extract Delegation Handlers

Status: `complete`
Commit: `fc370db7`

**Problem**: The `ai_coordinator_delegate` pathway (~800 lines), its fallback chain
builder, quality assessment, and message optimization logic all live in http_server.py.
This is the most business-critical path (currently 23.5% success pre-rebuild) and the
hardest to reason about in 13K lines of context.

**Fix strategy**:
- Create `delegation_handlers.py` with the delegation path extracted
- Export: `build_delegation_fallback_chain`, `select_next_available_delegation_target`,
  `assess_delegated_response_quality`, `optimize_delegated_messages`,
  `delegated_quality_status_snapshot`
- http_server.py imports and delegates to these functions
- No behavior changes — pure extraction

**Files**:
- `ai-stack/mcp-servers/hybrid-coordinator/delegation_handlers.py` (new)
- `ai-stack/mcp-servers/hybrid-coordinator/http_server.py` (import + remove extracted code)

**Validation**:
```bash
python3 -m py_compile ai-stack/mcp-servers/hybrid-coordinator/delegation_handlers.py
python3 -m py_compile ai-stack/mcp-servers/hybrid-coordinator/http_server.py
python3 -m pytest ai-stack/mcp-servers/hybrid-coordinator/tests/integration/test_mcp_contracts.py -v
scripts/testing/validate-ai-slo-runtime.sh
```

---

## Phase 11.3 — Extract Workflow Session Handlers

Status: `complete`
Commit: `ab363479`

**Problem**: Workflow session management (~1200 lines) — session start, session list,
blueprint loading, workflow plan/run/start/orchestrate — is mixed into http_server.py
despite `workflow_executor.py` and `yaml_workflow_handlers.py` already existing.

**Fix strategy**:
- Create `workflow_session_handlers.py`
- Move `handle_workflow_*`, `handle_workflow_session_*`, session CRUD helpers
- Wire via `app.router.add_*` calls that remain in http_server.py

**Validation**:
```bash
python3 -m py_compile ai-stack/mcp-servers/hybrid-coordinator/workflow_session_handlers.py
# Smoke: workflow plan + run/start endpoints still respond
curl -s -X POST localhost:8003/workflow/plan -H "Content-Type: application/json" \
  -d '{"objective":"test"}' | python3 -m json.tool | grep -q "plan"
```

Observed result:
- `http_server.py` reduced from roughly `12,780` lines after Phase 11.2 to `11,404`
- Workflow routes now register through `workflow_session_handlers.register_routes(http_app)`
- Roadmap/smoke checks updated to validate the extracted module instead of grepping `http_server.py`

---

## Execution Ledger

| Date       | Slice | Result | Evidence |
| ---------- | ----- | ------ | -------- |
| 2026-04-26 | 11.2  | complete | `fc370db7` extracted delegation helpers into `delegation_handlers.py` |
| 2026-04-26 | 11.3  | complete | `ab363479` extracted workflow session handlers into `workflow_session_handlers.py`; `scripts/governance/tier0-validation-gate.sh --pre-commit` passed |

---

## Phase 11.4 — Extract OpenAI-Compat + A2A Handlers

**Problem**: OpenAI-compatible endpoint handlers (`/v1/chat/completions`, `/v1/models`,
`/v1/completions`) and A2A agent card handlers (`/.well-known/agent.json`) are ~300
lines scattered through http_server.py.

**Fix strategy**:
- Create `openai_a2a_handlers.py`
- Move `handle_openai_*`, `handle_well_known_*`, `_proxy_openai_request_via_coordinator`

**Validation**:
```bash
python3 -m py_compile ai-stack/mcp-servers/hybrid-coordinator/openai_a2a_handlers.py
curl -s localhost:8003/v1/models | python3 -m json.tool | grep -q "data"
curl -s localhost:8003/.well-known/agent.json | python3 -m json.tool | grep -q "name"
```

---

## Phase 11.5 — Extract Ops Handlers (Learning/Feedback/Alert/Cache)

**Problem**: Learning, feedback, alert management, and cache handlers are operational
concerns that have nothing to do with the core query/delegation path but take up ~2000
lines in http_server.py.

**Fix strategy**:
- Create `ops_handlers.py`
- Move `handle_learning_*`, `handle_feedback*`, `handle_alert*`, `handle_cache_*`,
  `handle_model_*`, `handle_reload_model`, `handle_qa_check`

**Validation**:
```bash
python3 -m py_compile ai-stack/mcp-servers/hybrid-coordinator/ops_handlers.py
curl -s localhost:8003/learning/stats | python3 -m json.tool | grep -q "total"
curl -s localhost:8003/cache/stats | python3 -m json.tool | grep -q "hit_rate"
```

---

## Phase 11.6 — Cloud Burst Remote Routing Trigger

**Problem**: 100% local routing defeats the "hybrid" architecture. Remote routing is
wired but no activation rules trigger it. The coordinator's confidence threshold is 0.35
(very permissive — almost all queries stay local even with poor context quality).

**Design**: Two trigger conditions for remote burst:

1. **Quality trigger** (context_quality < threshold AND query complexity = complex):
   Route to remote when local model is unlikely to produce a useful response.
   - Config: `remote_burst_quality_threshold: 0.4` in `routing-config.json`
   - Only applies when `query_complexity = complex` (detected by `_detect_task_type`)

2. **Queue saturation trigger** (llama.cpp queue_depth > 0 for >10s):
   Route to remote when local inference queue is backed up.
   - Config: `remote_burst_queue_depth_trigger: 1` in `routing-config.json`
   - Prevents starvation during heavy local load

**Fix strategy**:
- Add `remote_burst_quality_threshold` and `remote_burst_queue_depth_trigger` keys
  to `routing-config.json`
- In `route_handler.py` or `llm_router.py`, check these conditions in
  `select_llm_backend()` before falling back to `prefer_local=true`
- Wire to the existing remote profile selector (`_coordinator_requested_profile`)
- No new service units — pure config + routing logic change

**Files**:
- `~/.local/share/nixos-ai-stack/routing-config.json` (add new keys)
- `ai-stack/mcp-servers/hybrid-coordinator/llm_router.py` (burst trigger logic)
- `nix/modules/roles/ai-stack.nix` (env var: `AI_REMOTE_BURST_QUALITY_THRESHOLD`)

**Important**: Do NOT activate until post-rebuild delegation success ≥50%.
Remote burst routes to `ai_coordinator_delegate` path. If delegation is still at 23.5%,
burst traffic will fail. Gate: `aq-qa 0.8.x` must pass first.

**Validation** (post-rebuild only):
```bash
# Set low threshold to force a test query to remote
python3 -c "
import json; p = '~/.local/share/nixos-ai-stack/routing-config.json'
import os; c = json.load(open(os.path.expanduser(p)))
c['remote_burst_quality_threshold'] = 0.95  # force all complex queries remote
json.dump(c, open(os.path.expanduser(p), 'w'))
"
# Wait 65s for TTL reload, send complex query, verify backend=remote in logs
curl -s -X POST localhost:8003/query -H "Content-Type: application/json" \
  -d '{"query":"design a distributed multi-agent system architecture","generate_response":true}' \
  | python3 -m json.tool | grep -q "remote"
# Restore original threshold after test
```

---

## Phase 11.7 — Validation Gate

**Success criteria (all must pass)**:
1. `python3 -m py_compile` passes for all new + modified modules
2. `wc -l ai-stack/mcp-servers/hybrid-coordinator/http_server.py` → < 2000 lines
3. `pytest tests/integration/test_mcp_contracts.py -v` → all pass
4. `scripts/testing/validate-ai-slo-runtime.sh` → PASS
5. `aq-qa 0` → 39+ passed, 0 failed
6. Remote routing: at least 1 synthetic complex query routes to remote backend
   (verified via `aq-report --since=1h` routing split)

---

## Execution Order

```
Phase 11.1 (audit — no code changes) → immediate
Phase 11.2 (delegation extraction) → most critical, do first
Phase 11.3 (workflow sessions) → independent, parallelizable with 11.2
Phase 11.4 (openai/a2a) → small, fast
Phase 11.5 (ops handlers) → largest slice, do last
Phase 11.6 (cloud burst) → BLOCKED on nixos-rebuild + delegation ≥50%
Phase 11.7 (validation gate) → run after each slice
```

---

## Notes

- Do NOT skip the nixos-rebuild gate before Phase 11.6. Remote burst on a broken
  delegate path will degrade user-facing quality.
- Each extraction slice should be a separate commit: `refactor(hybrid): extract X`
- Use `aq-delegate --auto-approve qwen "..."` for implementation slices 11.2–11.5
- The target for http_server.py after all slices: < 1000 lines (routing + startup only)
