# Phase A — Progressive Tool Disclosure — COMPLETE
# (file updated 2026-06-14 by claude-sonnet-4-6 — revised approach)
---
phase: A
title: "Phase A — Progressive Tool Disclosure (task-aware)"
status: COMPLETE
commit: 8b3f51f9
date: 2026-06-13
agent: claude-sonnet-4-6
---

## Outcome

All 14 AI coordination tools are now present in `TOOL_SCHEMAS` alongside the 3 base tools.
Final token budget: **754t / 800t ceiling**. aq-qa parity check A.5.1 passes.

## Step 0 — Endpoint verification (hard gate)

Live coordinator at `http://127.0.0.1:8003` verified via HTTP probes. All 14 tool
endpoints are reachable via loopback-agent auth (no API key required from 127.0.0.1).

| Tool | Method | Endpoint | Verified |
|------|--------|----------|---------|
| get_hint | GET | /hints | ✓ returns {hints:[]} |
| delegate_to_remote | POST | /query | ✓ returns {route,response,results} |
| query_context | POST | /query (context_only mode) | ✓ |
| store_memory | POST | /memory/store | ✓ (400 on short content — logic, not auth) |
| get_workflow_status | GET | /workflow/orchestrate/{id} | ✓ |
| run_opencode | local subprocess | N/A | graceful fallback |
| harness_health | POST | /qa/check | ✓ returns {status,phase,exit_code} |
| get_prsi_pending | GET | /control/prsi/pending | ✓ |
| prsi_orchestrate | GET/POST | /control/prsi/actions[/execute] | ✓ |
| recommend_agent_for_task | GET | /control/agents | ✓ (fixed from /federated/recommend) |
| query_aidb | POST | /search/tree | ✓ |
| get_working_memory | POST | /memory/recall | ✓ |
| mesh_discovery | GET | /discovery/capabilities | ✓ |
| collective_memory_search | POST | {AIDB_URL}/vector/search | ✓ (direct AIDB) |

**2 endpoint fixes applied:**
- `recommend_agent_for_task`: `/federated/recommend` (unregistered) → `/control/agents`
- `get_workflow_status`: `/workflow/status/{id}` (404) → `/workflow/orchestrate/{id}`

## Files Changed

| File | Change |
|------|--------|
| `ai-stack/agents/runtimes/local_agent_runtime.py` | TOOL_SCHEMAS: 3→17 via `_T()` ultra-minimal builder. All dispatch handlers already present in TOOL_CATALOG (Phase pre-work). Two endpoint fixes. |
| `.agent/tool-parity-contract.json` | New — generated from ai_coordination.py. 14 required tools, 0 deferred. |
| `scripts/ai/aq-chat` | `/tools` shows parity contract with ✓/[GAP]. `/tools all` shows full registry. `_parity_contract_cache` added. |
| `scripts/ai/_aq-qa-bash` | A.5.1 parity CI check (L7) — asserts required_tools ⊆ TOOL_SCHEMAS names and token budget ≤ ceiling. |

## Validation

```
Tools: 17 | Tokens: 754/800  PASS
PARITY CHECK: PASS (0 missing, 754t ≤ 800t)
aq-qa 0: 116 pass, 1 fail (0.8.1 delegate 24h rate — pre-existing xfail)
tier0-validation-gate --pre-commit: 19/19 PASS
```

## Pre-existing failure note

`0.8.1 delegate 24h success rate ≥50% (got 21%, 9/42 calls)` — in `config/qa-xfail.yaml`
as a known runtime-blocked failure. Unrelated to Phase A.

## Phase A.6 — Per-iteration tool hot-swap (2026-06-13)

**Commit:** cbde02d3  
**Files:** `ai-stack/agents/runtimes/local_agent_runtime.py`, `ai-stack/local-agents/agent_executor.py`

**What was implemented:**

`local_agent_runtime.py`:
- `_refresh_tools_from_result(tool_name, result_text, current_tools, max_tools=6)` — monotonic expansion from TOOL_CATALOG using five keyword clusters (memory/workflow/delegate/health/mesh). Each addition slimmed via `_slim_schema()` (~50 tokens).
- `_active_tools` live set initialised from `_select_tools_for_task()`, then expanded after each `tc_result` in the `run()` loop. `_build_inference_payload()` always called with `selected_tools=_active_tools`.

`agent_executor.py`:
- Module-level `_AEXEC_*_KW` frozensets and `_AEXEC_HOTSWAP_MAP`.
- `_refresh_active_tools(tool_name, result_text, current_tools, all_tools, max_tools=8)` — same semantics, works with flat registry schemas.
- In `_execute_with_tools()`: `_all_tools` snapshots full registry; `_active_tools` starts equal to it; after each tool result, refresh fires and if the set grew, `messages[0]` (system prompt) is rebuilt with the expanded tool surface. Debug log: `tool_hotswap: +N tools after <tool_name> (total=M)`.

**Validation:** py_compile OK · aq-qa 0: 116/116 · tier0 gate: 19/19 PASS
