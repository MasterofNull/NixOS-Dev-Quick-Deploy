# Phase 68–70: AIOS Continuity + Protocol Standardization PRD
**Status:** ACTIVE — 2026-05-23
**Authored by:** Claude (orchestrator) · Gemini proxy (VP Eng) · Codex proxy (Staff Eng)
**Supersedes:** Phase 64-67 PRD (complete as of 2026-05-23)
**Source material:** MASTER-AI-HARNESS-ANALYSIS.md v5.0 (32-pass Gemini SOTA comparison), Phase 64-67 stored items

---

## 1. Context

All Phase 64-67 features are shipped. Post-rebuild state:
- **aq-qa**: 100/100 PASS · 3 skipped (expected)
- **Dashboard**: Intelligence 48 panels (20+29), Operations 28 panels (14+14)
- **Active**: prompt_hash DDL ✓, K-LRU CLM ✓, contradiction events ✓, KV cache q8_0 ✓, AppArmor complain ✓
- **Model**: llama-cpp running with `--cache-type-k q8_0 --cache-type-v q8_0` (Phase 66.1)

This PRD addresses the next three cycles targeting SOTA gaps from the MASTER report.

---

## 2. Gap Inventory (from MASTER-AI-HARNESS-ANALYSIS.md §7)

| ID | Gap | SOTA Reference | Priority | Rebuild? |
|----|-----|---------------|----------|----------|
| G11 | ReAct DAG backtracking — workflow re-planning on error | Cursor agentic shell | P1 | Yes |
| G12 | AG-UI WebSocket agent→dashboard state push | CopilotKit | P2 | No |
| G13 | MCP JSON-RPC 2.0 migration | Anthropic MCP spec | P1 | Yes |
| G14 | Temporal Knowledge Graph (fact provenance chain) | Zep/Graphiti | P2 | No |
| G15 | Distributed consensus (reputation-weighted voting) | AIOS Kernel | P3 | Yes |
| G16 | Post-quantum Agent Cards (ML-DSA-65) | NIST FIPS 204 | P3 | Yes |

---

## 3. Phase 68 — Protocol Compliance + ReAct DAG

**Goal:** Close G11 (ReAct backtracking) + start G13 (MCP JSON-RPC 2.0) foundational work.
**Rebuild required:** Phase 68.1-68.3 (coordinator); 68.4-68.5 (dashboard, no rebuild)

### Slices

| ID | Slice | Acceptance Criteria |
|----|-------|---------------------|
| 68.1 | **Workflow checkpoint error recovery**: `workflow_checkpointer.py` — on step failure, inspect error type (retryable vs fatal); retryable steps re-enqueue to DLQ with backoff; fatal steps trigger re-planning via `backtrack_to(parent_node_id)` + `_prune_descendant_nodes()`. Max backtrack depth = 3 (configurable). | `POST /workflow/run` with failing step returns `{"backtrack_applied": true, "new_plan": [...]}` on retry; aq-qa 68.1 PASS |
| 68.2 | **MCP JSON-RPC 2.0 adapter**: `mcp/jsonrpc_adapter.py` — thin shim that wraps existing tool handlers in JSON-RPC 2.0 envelope (`jsonrpc: "2.0"`, `id`, `method`, `params`, `result`/`error`). Mount at `POST /mcp/v2`. Parallel to existing tool routes (no breaking changes). | `POST /mcp/v2 {"jsonrpc":"2.0","id":1,"method":"tools/call","params":{"name":"aq_hints","arguments":{}}}` returns valid JSON-RPC 2.0 response; aq-qa 68.2 PASS |
| 68.3 | **MCP tool manifest endpoint**: `GET /mcp/v2/tools` returns JSON-RPC 2.0 compliant tool list (name, description, inputSchema per MCP spec 2025-11-05). | Response validates against MCP tools/list schema; aq-qa 68.3 PASS |
| 68.4 | **Dashboard: Workflow Replay panel** (Operations): `loadWorkflowReplay()` — fetches `/aistack/orchestration/sessions?limit=20`, shows sessions with `backtrack_count > 0` highlighted; expandable step trace. | Panel renders; backtrack count shown; aq-qa 68.4 PASS |
| 68.5 | **Dashboard: MCP Protocol Status** (Intelligence): `loadMCPStatus()` — fetches `/mcp/v2/tools`, shows tool count + JSON-RPC 2.0 compliance badge. | Panel renders; aq-qa 68.5 PASS |

**aq-qa trajectory:** 100 → 105/105

---

## 4. Phase 69 — AG-UI WebSocket + Temporal Graph

**Goal:** Close G12 (agent→dashboard push) + G14 (temporal knowledge graph foundation).
**Rebuild required:** Phase 69.3 only (coordinator temporal graph routes)

### Slices

| ID | Slice | Acceptance Criteria |
|----|-------|---------------------|
| 69.1 | **AG-UI WebSocket endpoint**: `GET /ws/agent-state` — WebSocket endpoint in dashboard backend. On connect, subscribes to coordinator SSE `/api/agent-events`. Converts events to AG-UI delta patches `{type:"state_delta", path:"...", value:...}`. Dashboard JS client auto-reconnects on drop. | `ws://localhost:8889/ws/agent-state` accepts connection; events flow within 500ms; aq-qa 69.1 PASS |
| 69.2 | **Dashboard: Live Event Feed** (Intelligence): `loadLiveEvents()` — WebSocket client connecting to `/ws/agent-state`. Renders last 20 events in real-time without polling. Badge shows "live" or "reconnecting". | Events update live; no polling; aq-qa 69.2 PASS |
| 69.3 | **Temporal fact chain**: `knowledge/temporal_graph.py` — `TemporalGraph` stores (subject, predicate, object, valid_from, valid_to) tuples in Postgres `fact_chain` table. `add_fact()` supersedes conflicting facts with valid_to=now. `query_at(timestamp)` returns facts valid at that point. `GET /knowledge/graph/fact-chain?subject=...` endpoint. | `query_at(T-1h)` returns pre-supersession state; aq-qa 69.3 PASS |
| 69.4 | **Dashboard: Fact Chain Timeline** (Intelligence): `loadFactChainTimeline()` — SVG timeline of fact supersession events from `/knowledge/graph/fact-chain`. Color: green=active, grey=superseded. | Timeline renders; aq-qa 69.4 PASS |

**aq-qa trajectory:** 105 → 109/109

---

## 5. Phase 70 — Distributed Consensus + Hardening

**Goal:** G15 (reputation-weighted consensus for high-risk changes) + post-rebuild harness soak.

### Slices

| ID | Slice | Acceptance Criteria |
|----|-------|---------------------|
| 70.1 | **Reputation-weighted vote**: `workflow/consensus_engine.py` — `WeightedVote` replaces simple majority. Agent reputation scores from lessons registry (lesson_count, error_rate); tie-break = orchestrator veto. `POST /workflow/consensus/vote` accepts `{session_id, agent_id, vote, confidence}`. | Weighted consensus returns correct winner; aq-qa 70.1 PASS |
| 70.2 | **AppArmor enforce mode**: after 1-week soak with clean audit logs (`journalctl -b --grep apparmor`), switch ai-hybrid-coordinator + command-center-dashboard-api to `state = "enforce"`. | `aa-status` shows profiles in enforce mode; aq-qa 70.2 PASS |
| 70.3 | **Harness full soak validation**: run `aq-qa 0` + `maeah-acceptance-tests.sh` + `smoke-wasmtime.sh` in `nix develop .#full` to confirm all Phase 64-70 features stable under load. | All gates PASS; aq-qa ≥ 109/109 |

**aq-qa trajectory:** 109 → 112/112

---

## 6. Team Collaboration

### Role assignments (Phase 68)

| Role | Agent | Assignment |
|------|-------|-----------|
| Orchestrator / implementer | Claude | 68.1-68.5 implementation |
| VP Eng / Security | Gemini | Review 68.2 (JSON-RPC auth surface), 68.1 (backtrack depth limit) |
| Staff Eng | Codex | Review 68.1 (workflow_checkpointer contract), 68.2 (MCP spec compliance) |
| Local agent | Qwen3-35B | Bounded: test JSON-RPC 2.0 payload shapes against spec (1 file, no PRD changes) |

**Proxy policy**: Gemini async → Claude fills VP Eng role and marks review proxy. Codex offline → Claude fills Staff Eng role and marks review proxy.

### Collaboration briefs
- Phase 68 brief: `.agent/collaboration/PHASE-68-TEAM-BRIEF.md`
- Gemini review: `.agent/collaboration/GEMINI-PHASE-68-REVIEW.md`
- Codex review: `.agent/collaboration/CODEX-PHASE-68-REVIEW.md`

---

## 7. Delivery Order

```
Phase 68.1 (rebuild) → 68.2-68.3 (rebuild) → 68.4-68.5 (dashboard, no rebuild)
Phase 69.1-69.2 (dashboard, no rebuild) → 69.3 (rebuild) → 69.4 (dashboard)
Phase 70.1 (rebuild) → 70.2 (enforce mode, rebuild) → 70.3 (soak)
```

**Priority override**: 68.4-68.5 (dashboard) can proceed NOW without waiting for 68.1-68.3 rebuild.

---

## 8. Pending Rebuild Items (from Phase 64-66)

These need the NEXT nixos-rebuild to deploy:
- `trace_collector.py`: prompt_hash in SELECT (fixed 2026-05-23, not yet rebuilt)
- `workflow_checkpointer.py`: Phase 68.1 backtracking (pending implementation)
- `mcp/jsonrpc_adapter.py`: Phase 68.2 (pending implementation)

---

## 9. aq-qa Milestone Targets

| Milestone | Count |
|-----------|-------|
| Phase 68 complete | 105/105 |
| Phase 69 complete | 109/109 |
| Phase 70 complete | 112/112 |
