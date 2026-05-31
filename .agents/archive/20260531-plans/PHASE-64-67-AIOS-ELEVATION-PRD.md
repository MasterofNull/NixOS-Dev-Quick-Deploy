# Phase 64–67: AIOS Elevation PRD
# NixOS AI Harness — Next-Cycle Architecture Uplift

**Version:** 1.0
**Date:** 2026-05-23
**Status:** APPROVED — Claude CTO, derived from MASTER-AI-HARNESS-ANALYSIS.md (Rev 5.0)
**Predecessor:** Phases 60–63 complete (bitemporal memory, CLM, nsjail, GraphRAG, RAGAS)
**aq-qa baseline:** 92/92 PASS · tier0: 17/17 PASS

---

## 1. Executive Summary

Phases 60–63 elevated the harness to a production-stable AI OS with:
temporal memory, RAG eval, execution sandboxing, and knowledge graph retrieval.

This PRD is derived from a 32-pass industry comparison (MASTER-AI-HARNESS-ANALYSIS.md v5.0)
covering Devin, Windsurf, OpenHands, AIOS Kernel, DayOS, vLLM, and Langfuse patterns.
It defines four next-cycle phases targeting the highest-ROI gaps vs. SOTA.

**North star:** Close the observability, governance, and sandbox tiers gap vs. enterprise
AI systems — while staying NixOS-first, local-inference-first, and anti-gaming.

---

## 2. Gap Analysis (from MASTER-AI-HARNESS-ANALYSIS.md Rev 5.0)

| ID | Source | Gap | Our State | Priority |
|----|--------|-----|-----------|----------|
| G1 | Langfuse / Arize Phoenix | Prompt versioning absent — traces lack `prompt_version_id` | TraceCollector has OTel spans but no prompt hash | P0 — no rebuild |
| G2 | MetaGPT / OpenHands | Event bus `sub_type` absent — ContinuousLearning cannot cluster violation types | POST /api/agent-events has `event_type` only | P0 — no rebuild |
| G3 | OpenLIT / Grafana | No Gantt-style trace timeline visualization | OTel spans stored, not rendered as timeline | P0 — dashboard only |
| G4 | vLLM metrics pattern | Tool execution heatmap absent — no bottleneck identification | tool_audit.jsonl exists, no aggregation endpoint | P0 — no rebuild |
| G5 | AIOS Kernel K-LRU | CLM has Hot→Warm→Cold tiers but no K-LRU eviction policy | CLM compaction triggered by pressure but no LRU tracking | P1 — needs rebuild |
| G6 | Gemini PRD refinement | No contradiction event — supersession is manual only | memory_superseder.py does manual supersede | P1 — needs rebuild |
| G7 | Gemini PRD refinement | Constraints array missing from lessons endpoint | GET /control/ai-coordinator/lessons returns lessons only | P1 — no rebuild |
| G8 | DayOS Computational Law | Safety rails use YAML pattern matching — no truth scoring | config/safety-rails.yaml + Colang-DSL, no math proof | P2 |
| G9 | Ollama KV cache q4_0 | KV cache not quantized — wastes RAM at 2M+ token contexts | llama.cpp default KV (fp16) | P1 — config only |
| G10 | E2B / Wasmtime | nsjail (L3) only — no Wasmtime (L2 WASM) sandbox tier | nsjail confirmed working post-rebuild | P2 |
| G11 | Devin ReAct pattern | No dynamic DAG re-planning on tool failure | workflow_checkpointer has DAG but no backtracking | P2 |
| G12 | Cursor Mission Control | No multi-agent task monitoring grid view | Dashboard has individual panels, no parallel-task grid | P2 |
| G13 | MCP JSON-RPC 2.0 | Internal tools use custom protocol bridges | MCP servers exist but non-standard internally | P3 |

---

## 3. Phase Definitions

### Phase 64 — AIOS Observability + Trace Intelligence
**Goal:** Close G1-G4. No nixos-rebuild required. Pure Python + dashboard JS.
**Baseline:** 92/92 aq-qa, all coordinator endpoints live.

| Slice | Task | Gate |
|-------|------|------|
| 64.1 | `prompt_version_id` + `prompt_hash` in TraceCollector span schema. Hash = SHA256[:8] of system_prompt at query time. Store in `traces` PG table. Expose on GET /api/traces response. | `prompt_hash` field present in /api/traces response; aq-qa 64.1 PASS |
| 64.2 | `sub_type: Optional[str]` on POST /api/agent-events. ContinuousLearning clusters by `(event_type, sub_type)`. Sub-types: `schema_violation`, `context_overflow`, `logic_deadlock`, `tool_timeout`, `safety_block`. | Event accepted with sub_type; CL groups by sub_type; aq-qa 64.2 PASS |
| 64.3 | GET `/api/insights/tools/heatmap` — aggregates tool_audit.jsonl by tool name: call_count, avg_latency_ms, error_rate, last_called. Dashboard panel: "Tool Execution Heatmap" in Intelligence tab. | Endpoint returns non-empty JSON; panel renders; aq-qa 64.3 PASS |
| 64.4 | Trace Gantt timeline panel: render /api/traces spans as horizontal bars on SVG canvas. X=time, Y=span_name, color=status (success/error/slow). In Intelligence tab. | Panel renders with live span data; aq-qa 64.4 PASS |
| 64.5 | aq-qa checks 64.1–64.4; tier0 gate; commit. | tier0 17/17; aq-qa 92+4=96/96 |

**Commit scope:** `trace_collector.py`, `continuous_learning.py`, new `insights_tools.py` route,
`dashboard.html`, `assets/dashboard.js`

---

### Phase 65 — Memory Hardening + Automated Governance
**Goal:** Close G5-G7, G9. Coordinator changes require nixos-rebuild.

| Slice | Task | Gate |
|-------|------|------|
| 65.1 | K-LRU eviction in CLM warm tier: track `last_access_time` per context block in Redis. When warm tier exceeds 80% capacity, evict K least-recently-used blocks to cold (AIDB episodic). `apply_klru_pressure(k=3)` method. | GET /context/lifecycle/status shows klru_evictions counter; aq-qa 65.1 PASS |
| 65.2 | Contradiction event: in `memory_broker.write()`, after successful store, check top-3 semantic neighbors. If similarity > 0.92 AND content contradicts existing promoted lesson (negation check), emit `POST /api/agent-events {event_type:"memory", sub_type:"contradiction_detected"}` and call `superseder.supersede(old_id)`. | Contradiction triggers auto-supersession; lesson transitions to superseded; aq-qa 65.2 PASS |
| 65.3 | Constraints array in GET /control/ai-coordinator/lessons: add `constraints` field pulling facts with `fact_type=constraint` from MemoryBroker. aq-session-start injects constraints into context. | Response has `constraints` array; aq-session-start displays them; aq-qa 65.3 PASS |
| 65.4 | KV cache quantization: add `--cache-type-k q8_0 --cache-type-v q8_0` to llama.cpp systemd service args in ai-stack.nix. Reduces KV RAM from fp16 to ~50% footprint — enables larger contexts on Renoir APU. | llama-server /health OK post-rebuild; MTP acceptance rate unchanged; aq-qa 65.4 PASS |
| 65.5 | aq-qa checks 65.1–65.4; tier0 gate; commit; nixos-rebuild. | aq-qa 96+4=100/100; tier0 17/17 |

---

### Phase 66 — Sandbox Elevation + AppArmor
**Goal:** Close G10, activate AppArmor (existing PRD). Requires nixos-rebuild.

| Slice | Task | Gate |
|-------|------|------|
| 66.1 | Wasmtime in nixpkgs: check availability, add to hybridPython or shell devShell. Create `scripts/testing/smoke-wasmtime.sh`. | `wasmtime --version` exits 0; aq-qa 66.1 PASS |
| 66.2 | Wasmtime sandbox executor in shell_tools.py: for WASM-compatible tools (jq, cat, grep), run via wasmtime .wasm bundle if available — L2 isolation below nsjail cost. `WASMTIME_TOOLS` set; fallback to nsjail/subprocess. | Tool runs inside wasmtime; returncode 0; aq-qa 66.2 PASS |
| 66.3 | AppArmor activation: resume PROJECT-APPARMOR-ACTIVATION-RELIABILITY-PRD.md — enable apparmor in NixOS, write profiles for ai-hybrid-coordinator + dashboard. | systemctl status apparmor = active; profiles loaded; aq-qa 66.3 PASS |
| 66.4 | aq-qa checks 66.1–66.3; tier0 gate; commit; nixos-rebuild. | aq-qa 100+3=103/103; tier0 17/17 |

---

### Phase 67 — Dashboard Intelligence Elevation
**Goal:** Close G3 (Gantt), G12 (Mission Control). No rebuild required.

| Slice | Task | Gate |
|-------|------|------|
| 67.1 | Gantt-style trace timeline: SVG rendering of /api/traces data. X-axis = relative ms from query start, Y-axis = span_name, color-coded by status. Embedded in "Query Traces" panel. | Spans render as bars; 0 JS errors; aq-qa 67.1 PASS |
| 67.2 | Agent success/failure gauge: real-time pie/donut from /api/traces — success vs error vs slow. New panel "Agent Task Outcomes" in Operations tab. | Gauge renders; aq-qa 67.2 PASS |
| 67.3 | Mission Control view: tabular grid of active coordinator sessions from /api/insights/orchestration/sessions. Columns: session_id, agent, status, elapsed, last_tool. Refresh every 10s. | Grid populates; auto-refresh works; aq-qa 67.3 PASS |
| 67.4 | aq-qa checks 67.1–67.3; tier0 gate; commit. | aq-qa 103+3=106/106; tier0 17/17 |

---

## 4. Execution Sequence

```
Phase 64 (no rebuild)    → commit dc8abc5d+next
Phase 65.1-65.3 (no rebuild) → commit
nixos-rebuild switch     → deploy CLM K-LRU + KV cache quantization
Phase 65.4-65.5 verify   → post-rebuild aq-qa
Phase 66 (needs rebuild) → apparmor + wasmtime
Phase 67 (no rebuild)    → dashboard UI elevation
```

## 5. Delegation Plan

| Phase | Slice | Owner | Notes |
|-------|-------|-------|-------|
| 64.1-64.4 | All | Claude | No rebuild, direct execution |
| 65.1-65.3 | All | Claude | Python changes, no rebuild |
| 65.4 | Nix config | Claude | ai-stack.nix KV cache param |
| 66.1-66.2 | Wasmtime | Claude + Codex review | Codex reviews sandbox contract |
| 66.3 | AppArmor | Claude + Gemini review | Gemini reviews security profiles |
| 67.1-67.3 | Dashboard | Claude | SVG + JS panel work |

## 6. aq-qa Target Trajectory

| After Phase | Target |
|-------------|--------|
| 64 complete | 96/96 |
| 65 complete | 100/100 |
| 66 complete | 103/103 |
| 67 complete | 106/106 |

## 7. Stored for Phase 68+ (Future Cycle)

- ReAct dynamic DAG backtracking (G11) — requires workflow_checkpointer redesign
- MCP JSON-RPC 2.0 full standardization (G13) — large migration, Phase 68
- CopilotKit AG-UI WebSocket agent→dashboard state patches (G12 extension) — Phase 68
- pgvectorscale StreamingDiskANN migration (T2-D from Phase 60 PRD) — Phase 69
- Post-quantum Ed25519→ML-DSA-65 Agent Cards — Phase 70
