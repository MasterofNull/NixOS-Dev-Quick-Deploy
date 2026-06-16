---
doc_type: prd
id: phase184C-dashboard-observability-prd
title: "Phase 184C — Dashboard & Observability Unification: 12 New Panels, Cross-Cutting Metrics, Alert Rules"
status: draft
owner: architect
phase: "Phase 184C"
priority: P1-high
evidence_required: all 12 new panels render with live data; no '--' placeholders in targeted panels; alert fires when delegate success rate drops below 50%
---

# Phase 184C — Dashboard & Observability Unification

## 1. Problem Statement

The NixOS-Dev-Quick-Deploy AI harness operates six active subsystems (delegation, training pipeline, RAGAS quality evaluation, vector memory, autonomous improvement, workflow execution) that collectively produce measurable runtime signals. **None of these cross-cutting subsystems has full dashboard coverage today.** An operator looking at the dashboard cannot answer:

- Is the delegation pipeline healthy or silently broken?
- Is the finetuning dataset growing?
- Are RAGAS quality scores improving or regressing?
- Which of the 14 Qdrant collections have zero points and need seeding?
- How many agent memory entries exist and which type dominates?
- Have any PRSI improvement cycles executed in the last 24 hours?

### Quantified coverage gap

| Active subsystem | Total observable signals | Panels with live data today | Coverage |
|---|---|---|---|
| Delegation health | 6 (success rate, startup 500s, per-tool rate, feedback closure, adjusted rate, window breakdown) | 0 time-series panels | 0% |
| Training pipeline | 4 (dataset size, patterns learned, event type distribution, last ingest run) | 0 panels | 0% |
| RAGAS quality | 4 (answer_relevance, context_precision, faithfulness, per-collection) | 0 panels (scalar appears only in aq-report JSON) | 0% |
| Agent memory collections | 3 (episodic, procedural, semantic growth) | 0 panels | 0% |
| Domain Qdrant collections | 7 zero-point collections (trading, mlops, qa, osint, interaction-history, etc.) | point counts appear once in /ai/metrics but no growth trend | 10% |
| PRSI / autonomous improvement | 3 (cycle count, pass/fail, ROI) | 0 panels | 0% |
| Workflow execution (Phase 185A) | 2 (execution rate, parallel speedup) | 0 panels | 0% |

**Result:** 6 active subsystems, 4 fully dark (0% coverage), 2 partially lit. 22 of 26 observable signals are invisible to operators. Every dark subsystem can fail silently for 24+ hours without triggering any dashboard indicator (per MEMORY.md "Coverage gap → silent breakage" anti-pattern).

---

## 2. Current Dashboard Inventory

The dashboard backend is at `dashboard/backend/api/routes/` and the primary aggregation route is `GET /api/aistack/ai/metrics`. Panels are driven by JS fetches against these routes from the frontend SPA.

| Panel Name | Primary Route | Data Source | Status |
|---|---|---|---|
| Service health cards (aidb, hybrid, qdrant, llama, embeddings, switchboard, redis, postgres) | `/api/aistack/ai/metrics` | HTTP probes + asyncio.gather | Working |
| Qdrant total vectors | `/api/aistack/ai/metrics` → `database_metrics.qdrant.total_vectors` | `_fetch_qdrant_collection_points()` | Working |
| Qdrant collection point counts (single snapshot bar) | `/api/aistack/ai/metrics` → `database_metrics.qdrant.collections` | Qdrant REST /collections/{name} | Working but no trend |
| Delegation stats widget | `/api/aistack/stats/delegate` | Coordinator `/stats/delegate` proxy | Working (returns flat JSON) — NOT a time series |
| Learning / feedback pipeline stats | `/api/aistack/stats/learning` | `continuous_learning_stats.json` + finetune path | Working — dataset_size=331, patterns=0 shown as scalars only |
| PRSI gap count | `/api/aistack/ai/metrics` → `prsi.gap_count` | `_fetch_prsi_stats()` from PostgreSQL | Working — scalar only |
| Harness scorecard / eval trend | `/api/aistack/harness/scorecard`, `/api/aistack/eval-trend` | Coordinator + tool_audit.jsonl | Working |
| Per-tool task classification | `/api/aistack/task-classification/stats` | `/var/log/nixos-ai-stack/tool-audit.jsonl` | Working — table exists; no 24h filter by tool success/failure split |
| Routing decisions table | `/api/aistack/routing/decisions` | Coordinator `/traces/routing` proxy | Working |
| Orchestration sessions / swimlane | `/api/aistack/orchestration/events` | `agent-run-events.jsonl` | Working |
| Race run view | `/api/aistack/agent-runs/race` | `race-runs.jsonl` + `agent-run-events.jsonl` | Working |
| Circuit breakers | `/api/aistack/stats/circuit-breakers` | Coordinator `/health` | Working |
| Redis / Postgres probes | `/api/aistack/ai/metrics` → `infra_probes` | asyncio probes | Working |
| RAGAS metrics (aq-report snapshot) | `/api/aistack/ai/metrics` (nested in harness section indirectly) | `latest-aq-report.json` → `ragas_metrics` | **Stale** — scalars only, no trend, surfaced nowhere in frontend |
| Delegation 24h success rate | `/api/aistack/ai/metrics` → buried in harness.overview | Coordinator delegate stats | **Stale** — number exists in JSON but no dedicated panel, no time series |
| Startup 500 histogram | None | `delegate_24h_breakdown.infra_startup_500` in harness JSON | **Missing** — no route, no panel |
| Finetuning dataset growth | None | `continuous_learning_stats.json` `finetuning_dataset_size` | **Stale** — scalar only, no growth trend |
| Patterns learned gauge | None | `continuous_learning_stats.json` `total_patterns_learned` | **Missing** — no panel |
| Agent-run event type distribution | None | `agent-run-events.jsonl` | **Missing** |
| Agent memory collection growth | None | Qdrant episodic/procedural/semantic collections | **Missing** |
| PRSI cycle timeline | None | PostgreSQL `telemetry_events` WHERE event_type='harness_improvement_pass' | **Missing** |
| Workflow execution rate | None | Planned Phase 185A workflow events | **Missing (planned)** |

**Summary:** 12 working panels, 10 stale or missing. Zero trend/time-series panels for any AI subsystem metric.

---

## 3. Telemetry Source Inventory

| Source | Path / Endpoint | Format | Key Event Types / Fields | Approx Size | Sample Rate |
|---|---|---|---|---|---|
| `hybrid-events.jsonl` | `/var/lib/ai-stack/hybrid/telemetry/hybrid-events.jsonl` | JSONL (one JSON object per line) | `hybrid_search`, `agent_memory_recall`, `route_search`, `learning_feedback`, `context_augmented` | 53.4 MB, ~78,948 events | Continuous (every request) |
| `agent-run-events.jsonl` | `/var/lib/ai-stack/hybrid/telemetry/agent-run-events.jsonl` | JSONL | `agent_step_start`, `agent_tool_intent`, `agent_tool_result`, `prompt_load`, `spec_variant`, `model_call`, `validation`, `final_outcome`, `planning`, `system_prompt`, `token_usage`, `agent_complete`, `agent_stall`, `agent_failed` | 3.1 MB, 3,722 events | Per agent execution |
| `delegation-feedback.jsonl` | `/var/lib/ai-stack/hybrid/telemetry/delegation-feedback.jsonl` | JSONL | Keys: `failure_class`, `failure_classes`, `fallback_applied`, `final_profile`, `requested_profile`, `requester_role`, `http_status`, `improvement_actions` | 160.8 KB, 135 events | Per delegation attempt |
| `continuous_learning_stats.json` | `/var/lib/ai-stack/hybrid/telemetry/continuous_learning_stats.json` | JSON (single object, rewritten on update) | `finetuning_dataset_size`, `total_patterns_learned`, `learning_paused`, `optimization_proposals.total`, `deduplication.deduplication_rate`, `backpressure.file_sizes`, `batch_insights` | 654 B | Written by continuous learning daemon; refresh interval ~60s |
| `race-runs.jsonl` | `/var/lib/ai-stack/hybrid/telemetry/race-runs.jsonl` | JSONL | `agent_id`, `variant`, `experiment_id`, `status`, `winner` | 6.6 KB | Per race |
| `latest-aq-report.json` | `/var/lib/ai-stack/hybrid/telemetry/latest-aq-report.json` | JSON (single object, large) | `ragas_metrics.{answer_relevance_avg, context_precision_avg, faithfulness_avg, sample_count}`, `delegate_24h_breakdown.{total, ok, raw_rate, adjusted_rate, infra_startup_500, provider_error, timeout, other_failure}`, `effectiveness_scorecard`, `eval_trend` | 34.6 KB | Written after each `aq-report` run (manual / scheduled) |
| `optimization_proposals.jsonl` | `/var/lib/ai-stack/hybrid/telemetry/optimization_proposals.jsonl` | JSONL | `proposal_id`, `type`, `description`, `score`, `accepted` | 5.6 KB | Per learning cycle |
| Qdrant REST API | `http://127.0.0.1:6333/collections/{name}` | JSON REST | `result.points_count` per collection | N/A | On demand |
| Coordinator REST API | `http://127.0.0.1:8003/stats/delegate` | JSON REST (auth required) | `delegate_24h_breakdown`, `delegate_7d_breakdown`, `delegate_active_window_breakdown`, `healthy`, `delegate_24h_rate` | N/A | On demand |
| PostgreSQL `telemetry_events` | asyncpg DSN from `AIDB_DB_URL` | SQL table | `event_type='harness_improvement_pass'` metadata: `success`, `report`, `probes` | N/A | Per improvement pass |
| Tool audit log | `/var/log/nixos-ai-stack/tool-audit.jsonl` | JSONL | `tool_name`, `risk_tier`, `outcome` (`success`/`blocked`/`error`), `latency_ms`, `caller_hash` | Variable | Per tool call |
| Dashboard backend Prometheus | `GET /api/aistack/prometheus/metrics` | Prometheus text format | `redis_ping_ok`, `postgres_query_ok` gauges | N/A | On demand |
| Planned: workflow-events.jsonl (Phase 185A) | `/var/lib/ai-stack/hybrid/telemetry/workflow-events.jsonl` | JSONL | `workflow_id`, `step_count`, `parallel_steps`, `duration_ms`, `status` | TBD | Per workflow execution |
| Planned: prsi-cycles.jsonl (Phase 185B) | `/var/lib/ai-stack/hybrid/telemetry/prsi-cycles.jsonl` | JSONL | `cycle_id`, `hypothesis`, `result`, `roi_estimate`, `pass` | TBD | Per PRSI cycle |

**Current 54 MB hybrid-events.jsonl parsing constraint:** Full-file linear scans at each panel refresh are prohibited. All JSONL readers for this file must use checkpoint-based tail reading (last-known byte offset stored in memory or Redis) or read only the last N lines bounded by panel refresh rate. Panel refresh is set to 60s minimum for JSONL-backed panels.

---

## 4. Panel Specification

### Panel A — Delegate Success Rate (24h Rolling Time Series)

| Attribute | Value |
|---|---|
| **Panel name** | Delegate Success Rate — 24h Rolling |
| **Chart type** | Time series (line, dual-axis: raw rate + adjusted rate) |
| **Data source** | `GET /api/aistack/stats/delegate` → fields: `delegate_24h_breakdown.raw_rate`, `delegate_24h_breakdown.adjusted_rate`, `delegate_24h_breakdown.total`, `delegate_24h_breakdown.ok` |
| **Aggregation** | Latest scalar from coordinator; plotted as current-value point on a rolling 24h sparkline maintained in frontend state array (ring buffer, max 1440 points at 1-min refresh) |
| **Refresh rate** | 60 seconds |
| **Alert threshold** | `raw_rate < 0.50` for 5 consecutive readings → CRITICAL; `raw_rate < 0.70` for 10 readings → WARNING |
| **Backend route needed** | Existing: `GET /api/aistack/stats/delegate` already proxies coordinator. **Extend** response to include `window_ts` (ISO timestamp of window start) so frontend can anchor the time axis correctly. No new route needed. |
| **Notes** | Current reading: `raw_rate=0.045` (4.5%), `adjusted_rate=0.095` (startup-500s excluded). Plot both series. Dual-axis Y: left = rate 0–1.0, right = absolute ok/total counts. |

---

### Panel B — Coordinator Startup 500s Hourly Histogram

| Attribute | Value |
|---|---|
| **Panel name** | Coordinator Startup 500 Errors — Hourly |
| **Chart type** | Bar chart (histogram, one bar per hour, last 24 bars) |
| **Data source** | New route: `GET /api/aistack/stats/delegate/startup-500-histogram` → parse `delegation-feedback.jsonl`, group by `floor(timestamp / 3600)`, count events where `http_status == 500` or `failure_class == "provider_request_error"` with `http_status` 5xx |
| **Aggregation** | Count per 1-hour bucket, 24-bucket window |
| **Refresh rate** | 120 seconds |
| **Alert threshold** | Any hourly bucket >= 10 startup 500s → WARNING; >= 20 → CRITICAL |
| **Backend route needed** | **New:** `GET /api/aistack/stats/delegate/startup-500-histogram` in `aistack.py`. Parse tail of `delegation-feedback.jsonl` (max last 1000 lines), bucket by hour, return `{"buckets": [{"hour_start": "ISO", "count": N}, ...], "total_24h": N, "window_hours": 24}`. |
| **Notes** | Current 24h snapshot: 23 startup 500s from `delegate_24h_breakdown.infra_startup_500`. This is what Phase 184A must fix — the histogram makes the problem rate visible over time. |

---

### Panel C — Per-Tool Success Rate Table (Sortable, Last 24h)

| Attribute | Value |
|---|---|
| **Panel name** | Tool Success Rate — All Tools, Last 24h |
| **Chart type** | Sortable table (columns: tool_name, calls, ok, blocked, error, success_rate_pct, avg_latency_ms) |
| **Data source** | Existing: `GET /api/aistack/task-classification/stats` → `by_task_type` (call counts by tool). **Extend** to include outcome split per tool from `tool-audit.jsonl` (currently only totals by_outcome). |
| **Aggregation** | Count/rate per tool over full audit log tail (last 2000 lines = ~24h at typical volume) |
| **Refresh rate** | 120 seconds |
| **Alert threshold** | Any tool with >10 calls and success_rate_pct < 50 → WARNING row highlight |
| **Backend route needed** | **Extend existing** `GET /api/aistack/task-classification/stats`: add `per_tool_outcomes: {tool_name: {calls, ok, blocked, error, success_rate_pct, avg_latency_ms}}` computed by iterating `tool-audit.jsonl` tail and grouping by `(tool_name, outcome)`. No new route. |
| **Notes** | Current: `by_task_type` gives per-tool call counts but not per-tool outcome split. `by_outcome` gives total outcome counts only. The join is done in the route handler. |

---

### Panel D — Delegation Feedback Closure Rate Gauge

| Attribute | Value |
|---|---|
| **Panel name** | Delegation Feedback Closure Rate |
| **Chart type** | Gauge (0–100%) with threshold bands: red 0–30, yellow 30–70, green 70–100 |
| **Data source** | New route: `GET /api/aistack/stats/delegate/feedback-closure` → parse `delegation-feedback.jsonl` (all 135 events), compute: `closed = count(events where fallback_applied == true AND final_profile != requested_profile)`, `opened = total events`, `closure_rate = closed / opened` |
| **Aggregation** | Latest (static over full log; incremental if log grows) |
| **Refresh rate** | 300 seconds (log grows slowly) |
| **Alert threshold** | `closure_rate < 0.30` → WARNING (feedback loop is not converging) |
| **Backend route needed** | **New:** `GET /api/aistack/stats/delegate/feedback-closure`. Parse `delegation-feedback.jsonl`, count events by `failure_class`, compute closure metrics, return `{"total": 135, "fallback_applied": N, "closure_rate": F, "top_failure_classes": [...], "top_improvement_actions": [...]}`. |
| **Notes** | Current reading: 135 events, all with `failure_class: null` in the event-type field (events store structured data differently from typed events). The route must inspect `failure_class` and `fallback_applied` fields, not event_type. |

---

### Panel E — Finetuning Dataset Size Time Series (Daily Cadence)

| Attribute | Value |
|---|---|
| **Panel name** | Finetuning Dataset Size — Daily Growth |
| **Chart type** | Time series (step-line, one point per snapshot) |
| **Data source** | New route: `GET /api/aistack/stats/training/dataset-history` → read `continuous_learning_stats.json` for current value (`finetuning_dataset_size`); maintain a persistent ring-buffer JSON file at `/var/lib/ai-stack/hybrid/telemetry/dataset-size-history.jsonl` (one appended record per dashboard route call, with dedup: only append if value changed). |
| **Aggregation** | Current value from `continuous_learning_stats.json`; history from `dataset-size-history.jsonl` (last 90 points) |
| **Refresh rate** | 300 seconds |
| **Alert threshold** | Dataset size unchanged for 7 days → WARNING (training ingest stalled) |
| **Backend route needed** | **New:** `GET /api/aistack/stats/training/dataset-history`. Logic: (1) read `continuous_learning_stats.json` → `finetuning_dataset_size`; (2) append `{"ts": ISO, "size": N}` to history JSONL if size changed since last entry; (3) return `{"current": N, "history": [{ts, size}, ...], "growth_7d": delta, "paused": bool}`. |
| **Notes** | Current value: 331 records. Target after Phase 184B training events fix: measurable growth within 48h. Route must use `REPO_ROOT` env var for JSONL path to avoid EROFS (per MEMORY.md Nix store EROFS pattern). |

---

### Panel F — Patterns Learned Counter Gauge

| Attribute | Value |
|---|---|
| **Panel name** | Patterns Learned — Total & 24h |
| **Chart type** | Gauge (current total) + small sparkline (24h delta) with threshold markers at 10, 50, 200 |
| **Data source** | Existing: `GET /api/aistack/stats/learning` → `total_patterns_learned`, `finetuning_dataset_size`; new: append total to `dataset-size-history.jsonl` (reuse Panel E route) or dedicated `patterns-history.jsonl` |
| **Aggregation** | `total_patterns_learned` from `continuous_learning_stats.json` (latest); 24h delta computed from history JSONL |
| **Refresh rate** | 120 seconds |
| **Alert threshold** | `total_patterns_learned == 0` for >24h → WARNING (learning pipeline broken); `deduplication_rate > 0.90` → INFO (potential data quality issue) |
| **Backend route needed** | **Extend existing** `GET /api/aistack/stats/learning`: add `patterns_24h_delta` (difference between current and 24h-ago snapshot, read from history JSONL). No new route required if history JSONL approach used from Panel E. |
| **Notes** | Current: `total_patterns_learned=0`, `deduplication_rate=0.0`. Root cause under investigation in Phase 184B. Gauge at 0 with critical threshold marker is itself a valid signal to operators. |

---

### Panel G — Event Type Distribution Bar Chart (agent-run-events, Last 24h)

| Attribute | Value |
|---|---|
| **Panel name** | Agent Run Event Distribution — Last 24h |
| **Chart type** | Horizontal bar chart (event_type on Y-axis, count on X-axis), sorted descending |
| **Data source** | New route: `GET /api/aistack/stats/agent-run-events/distribution` → tail `agent-run-events.jsonl` (last 5000 lines), filter to events within last 24h by `timestamp` field, count by `event_type` |
| **Aggregation** | Count per event_type in 24h window |
| **Refresh rate** | 60 seconds |
| **Alert threshold** | `agent_stall / agent_step_start > 0.10` → WARNING (>10% of runs stall); `agent_failed > 0` → INFO |
| **Backend route needed** | **New:** `GET /api/aistack/stats/agent-run-events/distribution`. Read tail of `agent-run-events.jsonl` (last 5000 lines, bounded), parse timestamps, filter to 24h window, count by `event_type`, also compute derived ratios `stall_rate`, `completion_rate`. Return `{"distribution": {event_type: count, ...}, "stall_rate": F, "completion_rate": F, "total_events": N, "window_hours": 24}`. |
| **Notes** | Current counts (full log): `agent_step_start=433`, `agent_tool_intent=412`, `agent_tool_result=411`, `final_outcome=396`, `agent_complete=4`, `agent_stall=2`, `agent_failed=1`. The 24h window filter is critical — full-log counts are not useful for trending. |

---

### Panel H — RAGAS Quality Scores Multi-Line Time Series

| Attribute | Value |
|---|---|
| **Panel name** | RAGAS Quality Scores — Trend |
| **Chart type** | Multi-line time series (3 lines: answer_relevance, context_precision, faithfulness); Y-axis 0.0–1.0; threshold band at 0.7 (target) |
| **Data source** | New route: `GET /api/aistack/stats/ragas/history` → read `ragas_metrics` from `latest-aq-report.json` for current values; maintain `/var/lib/ai-stack/hybrid/telemetry/ragas-history.jsonl` with one record per aq-report run |
| **Aggregation** | Current snapshot from `latest-aq-report.json`; historical trend from `ragas-history.jsonl` (last 60 points) |
| **Refresh rate** | 300 seconds (aq-report runs at most every few hours) |
| **Alert threshold** | `faithfulness_avg < 0.60` → WARNING; `answer_relevance_avg < 0.50` → WARNING; any metric < 0.40` → CRITICAL |
| **Backend route needed** | **New:** `GET /api/aistack/stats/ragas/history`. Logic: (1) read `latest-aq-report.json` → `ragas_metrics`; (2) if `faithfulness_enabled=true` and `sample_count > 0`, append new record to `ragas-history.jsonl` (dedup by aq-report timestamp — check `generated_at` or file mtime); (3) return `{"current": {answer_relevance, context_precision, faithfulness, sample_count}, "history": [...], "target": 0.70, "below_target": [metric_names]}`. |
| **Notes** | Current: `answer_relevance=0.5017`, `context_precision=0.6008`, `faithfulness=0.6349`, `sample_count=100`. All three are below the 0.70 operational target. History file must be seeded with the current snapshot on first call. |

---

### Panel I — Qdrant Collection Point Counts Bar Chart (All 14 Collections)

| Attribute | Value |
|---|---|
| **Panel name** | Qdrant Collection Points — All Collections |
| **Chart type** | Horizontal bar chart (collection name on Y-axis, point count on X-axis), color-coded: green >100, yellow 1–100, red 0 |
| **Data source** | Existing: `GET /api/aistack/ai/metrics` → `database_metrics.qdrant.collections` (dict of name → count). All 14 collections already fetched via `_fetch_qdrant_collection_points()`. |
| **Aggregation** | Snapshot (latest REST call to Qdrant) |
| **Refresh rate** | 60 seconds |
| **Alert threshold** | Any collection with 0 points whose name is in `["error-solutions","skills-patterns","best-practices","codebase-context","knowledge"]` → WARNING (core RAG collections empty) |
| **Backend route needed** | **No new route.** Add `all_collections` field to `/api/aistack/ai/metrics` response (currently `database_metrics.qdrant.collections` only contains the dict, which is already correct). Frontend needs to render all 14 entries rather than the current top-3 `knowledge_collections` view. |
| **Notes** | Current live point counts: `codebase-context=25,681`, `knowledge=12,126`, `learning-feedback=9,787`, `skills-patterns=2,046`, `error-solutions=1,563`, `best-practices=278`, `agent-memory-semantic=99`, `agent-memory-procedural=9`, `agent-memory-episodic=6`, `interaction-history=1`. Zero-point collections: `trading-patterns`, `osint-intelligence`, `mlops-patterns`, `qa-patterns` — all 4 domain collections need seeding. |

---

### Panel J — Agent Memory Collection Growth Time Series

| Attribute | Value |
|---|---|
| **Panel name** | Agent Memory Growth — Episodic / Procedural / Semantic |
| **Chart type** | Multi-line time series (3 lines); Y-axis: point count; X-axis: time (last 7 days) |
| **Data source** | New route: `GET /api/aistack/stats/memory-growth` → read Qdrant point counts for `agent-memory-episodic`, `agent-memory-procedural`, `agent-memory-semantic`; maintain `/var/lib/ai-stack/hybrid/telemetry/memory-growth-history.jsonl` |
| **Aggregation** | Point count snapshot appended to history JSONL on each route call (bounded: only append if any value changed since last entry); return last 200 history points |
| **Refresh rate** | 120 seconds |
| **Alert threshold** | `episodic + procedural + semantic` unchanged for >24h → INFO (no agent runs storing memory); `episodic < 5` → INFO (very low episodic memory seeding) |
| **Backend route needed** | **New:** `GET /api/aistack/stats/memory-growth`. Reuse `_fetch_qdrant_collection_points(["agent-memory-episodic","agent-memory-procedural","agent-memory-semantic"])` (already available in aistack.py); append to `memory-growth-history.jsonl`; return `{"current": {episodic: 6, procedural: 9, semantic: 99}, "history": [...], "total": 114}`. |
| **Notes** | Current: episodic=6, procedural=9, semantic=99, total=114. Semantic leads by 11x — may indicate episodic and procedural write paths are underutilized. Trend line will reveal if memory is growing or static. |

---

### Panel K — PRSI Improvement Cycle Timeline (Planned: Phase 185B)

| Attribute | Value |
|---|---|
| **Panel name** | PRSI Improvement Cycles — Event Timeline |
| **Chart type** | Event marker timeline (vertical bars on time axis; hover shows hypothesis + pass/fail + ROI estimate) |
| **Data source** | Existing: `_fetch_improvement_pass_stats()` in aistack.py queries PostgreSQL `telemetry_events WHERE event_type='harness_improvement_pass'`. Currently returns `{total_runs, successful_runs, success_rate_pct, last_run_at}`. |
| **Aggregation** | Per-cycle events from PostgreSQL ordered by `created_at DESC LIMIT 50` |
| **Refresh rate** | 300 seconds |
| **Alert threshold** | `successful_runs / total_runs < 0.50` over last 7 days → WARNING (PRSI improvement pass failing >50% of attempts) |
| **Backend route needed** | **New (Phase 185B dependency):** `GET /api/aistack/stats/prsi/cycles` — extends `_fetch_improvement_pass_stats()` to return individual cycle rows: `[{cycle_ts, hypothesis_type, success, roi_estimate, probes_passed}]`. Backend SQL: `SELECT created_at, metadata FROM telemetry_events WHERE event_type='harness_improvement_pass' ORDER BY created_at DESC LIMIT 50`. |
| **Phase dependency** | Blocked on Phase 185B (PRSI cycle emission). Panel renders with empty state until Phase 185B ships. Empty-state message: "No PRSI cycles recorded — Phase 185B required." |

---

### Panel L — Workflow Execution Rate Time Series (Planned: Phase 185A)

| Attribute | Value |
|---|---|
| **Panel name** | Workflow Execution Rate — Runs/Hour |
| **Chart type** | Time series (bar + line overlay: runs/hour bars, parallel speedup % line) |
| **Data source** | Planned `workflow-events.jsonl` (Phase 185A) OR existing `agent-run-events.jsonl` → `event_type=spec_variant` events can proxy as workflow initiations |
| **Aggregation** | Count of workflow starts per 1-hour bucket, 24-bucket window; parallel_speedup = `parallel_steps / total_steps` from workflow event metadata |
| **Refresh rate** | 60 seconds |
| **Alert threshold** | Zero workflow executions in 24h → INFO (no agent experiments running) |
| **Backend route needed** | **New (Phase 185A dependency):** `GET /api/aistack/stats/workflows/execution-rate`. If `workflow-events.jsonl` does not exist, fall back to counting `spec_variant` events in `agent-run-events.jsonl` as a proxy metric. Return `{"hourly_buckets": [...], "total_24h": N, "parallel_speedup_avg": F, "data_source": "workflow-events|proxy-spec-variant"}`. |
| **Phase dependency** | Partial proxy available now using `agent-run-events.jsonl spec_variant` events (count=396 in current log). Full execution rate + parallel speedup requires Phase 185A workflow event emission. |

---

## 5. Backend Route Changes

All routes are in `dashboard/backend/api/routes/aistack.py`. No rebuild is required for dashboard backend changes — the dashboard service uses `WorkingDirectory=repo` with Python edits picked up on restart.

| Route | HTTP Method | Purpose | Input Params | Response Shape | Status |
|---|---|---|---|---|---|
| `/api/aistack/stats/delegate` | GET | Delegation aggregate | none | Extend: add `window_ts` to existing coordinator proxy response | Extend existing |
| `/api/aistack/stats/delegate/startup-500-histogram` | GET | Hourly 500 error buckets | `?hours=24` | `{buckets:[{hour_start,count}], total_24h, window_hours}` | **New** |
| `/api/aistack/stats/delegate/feedback-closure` | GET | Delegation feedback closure rate | none | `{total, fallback_applied, closure_rate, top_failure_classes:[{class,count}], top_improvement_actions:[str]}` | **New** |
| `/api/aistack/task-classification/stats` | GET | Per-tool stats | none | Extend: add `per_tool_outcomes:{tool:{calls,ok,blocked,error,success_rate_pct,avg_latency_ms}}` | Extend existing |
| `/api/aistack/stats/training/dataset-history` | GET | Finetuning dataset growth trend | `?limit=90` | `{current:N, history:[{ts,size}], growth_7d:N, paused:bool}` | **New** |
| `/api/aistack/stats/learning` | GET | Learning stats including patterns delta | none | Extend: add `patterns_24h_delta`, `patterns_history:[{ts,count}]` | Extend existing |
| `/api/aistack/stats/agent-run-events/distribution` | GET | Agent event type distribution | `?hours=24` | `{distribution:{event_type:count}, stall_rate:F, completion_rate:F, total_events:N, window_hours:24}` | **New** |
| `/api/aistack/stats/ragas/history` | GET | RAGAS quality score trend | `?limit=60` | `{current:{answer_relevance,context_precision,faithfulness,sample_count}, history:[{ts,ar,cp,f}], target:0.70, below_target:[str]}` | **New** |
| `/api/aistack/stats/memory-growth` | GET | Agent memory collection growth | `?limit=200` | `{current:{episodic,procedural,semantic}, history:[{ts,episodic,procedural,semantic}], total:N}` | **New** |
| `/api/aistack/stats/prsi/cycles` | GET | PRSI improvement cycle list | `?limit=50` | `{cycles:[{cycle_ts,success,roi_estimate,probes_passed}], total_runs, success_rate_pct, last_run_at}` | **New (Phase 185B)** |
| `/api/aistack/stats/workflows/execution-rate` | GET | Workflow execution rate | `?hours=24` | `{hourly_buckets:[{hour_start,count,parallel_speedup}], total_24h, data_source}` | **New (Phase 185A)** |

**History persistence pattern (applies to Panels E, H, J):** History JSONL files are appended to (not rewritten) on each route call, with deduplication by timestamp comparison against the last appended entry. Paths must use `os.getenv("REPO_ROOT")` fallback pattern to avoid Nix store EROFS. Read the last N lines only; never full-file scan.

---

## 6. Alert Rules

The dashboard backend already has alert infrastructure at `dashboard/backend/api/routes/health.py` (`get_alerts`, `acknowledge_alert`, `update_threshold`). All new alerts use the existing `AlertEngine`. Alert definitions belong in the alert configuration at `GET /api/health/alerts/configuration`.

| # | Alert Name | Metric | Condition | Window | Severity | Notification |
|---|---|---|---|---|---|---|
| 1 | `delegate-success-critical` | `delegate_24h_breakdown.raw_rate` from `/api/aistack/stats/delegate` | `raw_rate < 0.50` for 5 consecutive readings | Rolling 24h, checked every 60s | CRITICAL | Dashboard alert banner + alert log entry; auto-creates attention-snapshot.json entry |
| 2 | `delegate-success-warning` | `delegate_24h_breakdown.raw_rate` | `raw_rate < 0.70` for 10 consecutive readings | Rolling 24h, checked every 60s | WARNING | Dashboard WARNING badge on delegation panel |
| 3 | `coordinator-startup-500-spike` | `infra_startup_500` count per hour from startup-500-histogram route | Hourly bucket count >= 10 | 1h bucket | WARNING; >= 20 → CRITICAL | Dashboard alert banner; write to `attention-snapshot.json` |
| 4 | `ragas-quality-degraded` | `faithfulness_avg` from `/api/aistack/stats/ragas/history` | `faithfulness_avg < 0.60` | Any aq-report snapshot, checked on refresh | WARNING | Dashboard RAGAS panel border turns orange; alert log entry |
| 5 | `ragas-quality-critical` | Min of (`answer_relevance_avg`, `context_precision_avg`, `faithfulness_avg`) | Any metric < 0.40 | Any aq-report snapshot | CRITICAL | Dashboard red banner: "RAGAS quality critical — RAG retrieval degraded" |
| 6 | `training-stall` | `finetuning_dataset_size` change from `/api/aistack/stats/training/dataset-history` | Dataset size unchanged for 168 consecutive readings (7 days at 300s refresh = 2016 intervals, but 168 intervals at 60min each is more practical — 7d ÷ 300s = 2016 checks) | 7 days | WARNING | Dashboard INFO banner: "Training ingest stalled — dataset_size=331 for 7d" |
| 7 | `rag-collection-empty` | Point count per collection from `/api/aistack/ai/metrics` → `database_metrics.qdrant.collections` | Any core collection (`error-solutions`, `skills-patterns`, `best-practices`, `codebase-context`, `knowledge`) with `count == 0` | On refresh (60s) | WARNING | Alert row in dashboard alert table: "Collection {name} is empty — seeding required" |
| 8 | `agent-stall-rate-high` | `stall_rate` from `/api/aistack/stats/agent-run-events/distribution` | `stall_rate > 0.10` (>10% of agent runs stall) | Last 24h | WARNING | Dashboard agent-run panel badge: "Stall rate: {pct}%" |
| 9 | `memory-growth-frozen` | Total agent memory points (episodic + procedural + semantic) | Total unchanged for >24h AND at least one agent run occurred in the same 24h window | 24h | INFO | Dashboard memory panel: "Memory store not growing — check store_agent_memory call path" |
| 10 | `prsi-pass-rate-low` | `success_rate_pct` from `/api/aistack/stats/prsi/cycles` | `success_rate_pct < 50` over last 7 days | 7 days | WARNING | Dashboard PRSI panel: "Improvement pass failing — {N}/{total} cycles passed" |

---

## 7. Implementation Plan

### Phase A — Backend Routes (no rebuild required)

All changes are in `dashboard/backend/api/routes/aistack.py`. The dashboard Python service picks up edits on restart (`systemctl restart ai-dashboard`), no NixOS rebuild needed.

**A1 — Extend existing routes** (low-risk, backward-compatible additive changes):
- `GET /api/aistack/stats/delegate` — add `window_ts` field to proxy response
- `GET /api/aistack/task-classification/stats` — add `per_tool_outcomes` by iterating tool-audit log with per-tool outcome grouping
- `GET /api/aistack/stats/learning` — add `patterns_24h_delta` using history JSONL written by new Panel E route

**A2 — New routes, no external dependencies**:
- `GET /api/aistack/stats/delegate/startup-500-histogram` — parse `delegation-feedback.jsonl` tail
- `GET /api/aistack/stats/delegate/feedback-closure` — parse `delegation-feedback.jsonl` full (135 events, fast)
- `GET /api/aistack/stats/agent-run-events/distribution` — parse `agent-run-events.jsonl` tail (5000 lines max)
- `GET /api/aistack/stats/memory-growth` — call Qdrant REST for 3 collections, append to history JSONL

**A3 — New routes with history persistence**:
- `GET /api/aistack/stats/training/dataset-history` — reads `continuous_learning_stats.json`, appends to `dataset-size-history.jsonl`
- `GET /api/aistack/stats/ragas/history` — reads `latest-aq-report.json`, appends to `ragas-history.jsonl`

**A4 — New routes, PostgreSQL dependency**:
- `GET /api/aistack/stats/prsi/cycles` — extends existing `_fetch_improvement_pass_stats()` SQL query (no new DB table needed)

**A5 — New routes, Phase-gated**:
- `GET /api/aistack/stats/workflows/execution-rate` — Phase 185A dependency; proxy mode using `spec_variant` events available immediately as placeholder

### Phase B — Frontend Panels (no rebuild required)

All frontend changes are to the dashboard SPA JS files. The dashboard service serves static files from `WorkingDirectory=repo`.

**B1 — Panels using extended existing routes** (routing data already available):
- Panel C (per-tool table) — add `per_tool_outcomes` columns to existing task-classification panel
- Panel I (Qdrant all collections) — extend existing bar chart to render all 14 entries from `database_metrics.qdrant.collections`
- Panel F (patterns learned gauge) — read `total_patterns_learned` from existing `/api/aistack/stats/learning` response

**B2 — Panels requiring new routes from Phase A2/A3**:
- Panel A (delegate success rate time series) — frontend ring buffer, 1440-point rolling window
- Panel B (startup-500 histogram) — new route from A2
- Panel D (feedback closure gauge) — new route from A2
- Panel E (dataset size time series) — new route from A3
- Panel G (agent event distribution bar) — new route from A2
- Panel H (RAGAS quality multi-line) — new route from A3
- Panel J (memory growth time series) — new route from A2/A3

**B3 — Phase-gated panels** (render empty state with explanatory message):
- Panel K (PRSI cycle timeline) — Phase 185B dependency
- Panel L (workflow execution rate) — Phase 185A dependency (proxy mode renders immediately with `spec_variant` event count)

### Phase C — Alert Rules (no rebuild required)

- Add alert definitions to existing `AlertEngine` configuration at `dashboard/backend/api/routes/health.py`
- Alert rules 1–10 are threshold-based on values returned by routes from Phase A
- Wire alert evaluation to the 60s/120s/300s refresh cadence of each source route

### No-Rebuild vs Rebuild Distinction

| Change | Rebuild required? | Reason |
|---|---|---|
| Dashboard backend route additions/extensions | No | `ai-dashboard` service: `WorkingDirectory=repo`, Python edits picked up on `systemctl restart ai-dashboard` |
| Frontend JS/HTML panel additions | No | Same `WorkingDirectory=repo` pattern; static files served directly |
| Alert threshold additions to health.py | No | Same |
| New coordinator route (Phase A4 PRSI cycles route requires coordinator endpoint) | **Yes** — only if coordinator endpoint changes needed; existing `_fetch_improvement_pass_stats` SQL runs directly from dashboard, not via coordinator proxy | Dashboard connects to PostgreSQL directly via asyncpg — no coordinator rebuild needed |
| Any AppArmor rule additions for new file paths | **Yes** — NixOS rebuild | New JSONL paths under `/var/lib/ai-stack/hybrid/telemetry/` must be added to coordinator AppArmor profile if coordinator writes them |

---

## 8. Monitoring of the Monitoring

A stale dashboard panel is worse than no panel — it displays outdated data without signaling staleness.

### Staleness Detection Protocol

Each new route MUST include a `data_age_seconds` field computed as `time.time() - file_mtime` for JSONL/JSON source files or `time.time() - last_qdrant_call_ts` for REST-backed panels.

Frontend panels MUST display a yellow "STALE" badge when `data_age_seconds > 2 * refresh_rate_seconds`.

### Dashboard Self-Health Check (`aq-qa` integration)

Add the following checks to the `aq-qa` health suite:

| Check ID | Description | Pass Condition |
|---|---|---|
| `0.11.01` | Delegate success rate panel responds | `GET /api/aistack/stats/delegate` returns `delegate_24h_rate` field (not null) within 5s |
| `0.11.02` | Startup-500 histogram route responds | `GET /api/aistack/stats/delegate/startup-500-histogram` returns `total_24h >= 0` within 5s |
| `0.11.03` | RAGAS history route responds | `GET /api/aistack/stats/ragas/history` returns `current.sample_count > 0` within 5s |
| `0.11.04` | Dataset history route responds | `GET /api/aistack/stats/training/dataset-history` returns `current > 0` within 5s |
| `0.11.05` | Memory growth route responds | `GET /api/aistack/stats/memory-growth` returns `total > 0` within 5s |
| `0.11.06` | Agent event distribution responds | `GET /api/aistack/stats/agent-run-events/distribution` returns `total_events >= 0` within 5s |
| `0.11.07` | All Qdrant collections visible | `GET /api/aistack/ai/metrics` → `database_metrics.qdrant.collections` has exactly 14 keys |
| `0.11.08` | No '--' in any targeted panel field | Spot-check: `delegate_24h_rate`, `finetuning_dataset_size`, `faithfulness_avg` are numeric, not string '--' |

### Dashboard Health Panel

The existing `GET /api/health/aggregate` route should include a `dashboard_self_health` section that reports the pass/fail status of the above 8 checks. This creates a "meta-panel" — the dashboard can show its own health in a corner widget.

---

## 9. Validation Plan

For each panel, validation must confirm the panel renders live data (not mock or stale fallback) before the phase is considered complete.

### Panel-by-Panel Validation Procedure

**For all panels:**
1. `systemctl restart ai-dashboard` — ensure latest code loaded
2. Open dashboard at `http://127.0.0.1:8889` in Chromium
3. For each new panel: verify no `--` placeholder appears in targeted fields

**Panel A (Delegate Success Rate):**
- `curl -s http://127.0.0.1:8889/api/aistack/stats/delegate | jq '.delegate_24h_rate'` → must return `0.045` (or current live value), not null
- Observe time series in frontend accumulates a new point every 60s over a 5-minute watch period

**Panel B (Startup-500 Histogram):**
- `curl -s http://127.0.0.1:8889/api/aistack/stats/delegate/startup-500-histogram | jq '.total_24h'` → must return integer (current: 23)
- Bar chart renders 24 bars; non-zero bars appear at hours corresponding to coordinator restart times

**Panel C (Per-Tool Table):**
- `curl -s http://127.0.0.1:8889/api/aistack/task-classification/stats | jq '.per_tool_outcomes | keys | length'` → must return >0
- Table sorts by success_rate_pct ascending; tool-audit log must exist at `/var/log/nixos-ai-stack/tool-audit.jsonl`

**Panel D (Feedback Closure Gauge):**
- `curl -s http://127.0.0.1:8889/api/aistack/stats/delegate/feedback-closure | jq '.total'` → must return 135
- Gauge renders a numeric closure_rate, not null

**Panel E (Dataset Size History):**
- `curl -s http://127.0.0.1:8889/api/aistack/stats/training/dataset-history | jq '.current'` → must return 331
- After 2 refresh cycles (10 min), `history` array length increases by 1 (if value changed) or remains stable with correct dedup

**Panel F (Patterns Learned Gauge):**
- `curl -s http://127.0.0.1:8889/api/aistack/stats/learning | jq '.total_patterns_learned'` → must return 0 (current); gauge shows 0 with threshold markers visible
- After Phase 184B fix: value must increase above 0 within 24h of deployment

**Panel G (Event Distribution):**
- `curl -s http://127.0.0.1:8889/api/aistack/stats/agent-run-events/distribution | jq '.distribution'` → must have `agent_step_start` key with non-zero count
- `stall_rate` must be a float, not null

**Panel H (RAGAS Quality):**
- `curl -s http://127.0.0.1:8889/api/aistack/stats/ragas/history | jq '.current'` → must return `{answer_relevance: 0.5017, context_precision: 0.6008, faithfulness: 0.6349, sample_count: 100}` (or updated values)
- History JSONL file must exist at `/var/lib/ai-stack/hybrid/telemetry/ragas-history.jsonl` after first route call

**Panel I (Qdrant All Collections):**
- `curl -s http://127.0.0.1:8889/api/aistack/ai/metrics | jq '.database_metrics.qdrant.collections | length'` → must return 14
- Frontend bar chart shows all 14 bars; 4 red bars for zero-point domain collections

**Panel J (Memory Growth):**
- `curl -s http://127.0.0.1:8889/api/aistack/stats/memory-growth | jq '.current'` → must return `{episodic: 6, procedural: 9, semantic: 99}`
- `total` must equal 114

**Panel K (PRSI Cycle Timeline) — Phase 185B:**
- Before Phase 185B: endpoint returns `{cycles: [], total_runs: N, message: "Phase 185B required for cycle detail"}`
- After Phase 185B: `cycles` array has entries with `cycle_ts`, `success`, `roi_estimate`

**Panel L (Workflow Execution Rate) — Phase 185A proxy:**
- Proxy mode: `curl -s http://127.0.0.1:8889/api/aistack/stats/workflows/execution-rate | jq '.data_source'` → `"proxy-spec-variant"`
- `total_24h` shows count of `spec_variant` events in last 24h from `agent-run-events.jsonl`

### Alert Validation

- Temporarily set `delegate_24h_rate` threshold to 0.99 in alert config → alert fires within 60s
- `GET /api/health/alerts` returns the alert with correct severity and metric reference
- Reset threshold to 0.50 after test

---

## 10. Dependencies

### Dependency Ordering

```
Phase 184A (delegation fix)
  └── feeds Panel A and Panel B with meaningful data (low rate will rise)
      └── Alert rule 1/2/3 become useful post-fix

Phase 184B (training events fix)
  └── feeds Panel F (patterns learned rises from 0)
      └── feeds Panel E (dataset growth becomes visible)
          └── Alert rule 6 (stall detection becomes meaningful)

Phase 184C (this PRD — dashboard backend)
  └── Panels A-J can ship immediately (A3, A4, A5 gated below)
  └── Phase A1 + A2 panels: no dependency, ship first
  └── Phase A3 panels (H RAGAS history, E dataset history): no external dependency
  └── Phase A4 panels (K PRSI): existing SQL path available now — ship with empty state

Phase 185A (workflow execution events)
  └── Panel L full mode (parallel speedup metric)
  └── Panel L proxy mode ships with Phase 184C

Phase 185B (PRSI cycle emission)
  └── Panel K full mode (cycle detail with roi_estimate, probes_passed)
  └── Panel K empty-state ships with Phase 184C
```

### Panel-Level Dependency Matrix

| Panel | Ready to ship in 184C? | Blocking dependency |
|---|---|---|
| A (Delegate Success Rate) | Yes | None — data exists now |
| B (Startup-500 Histogram) | Yes | None — data exists in delegation-feedback.jsonl |
| C (Per-Tool Table extension) | Yes | None — tool-audit.jsonl exists |
| D (Feedback Closure Gauge) | Yes | None — delegation-feedback.jsonl has 135 events |
| E (Dataset Size History) | Yes | None — continuous_learning_stats.json exists |
| F (Patterns Learned Gauge) | Yes (shows 0, which is meaningful) | None for display; Phase 184B for non-zero value |
| G (Event Distribution) | Yes | None — agent-run-events.jsonl exists |
| H (RAGAS Quality Multi-line) | Yes | None — latest-aq-report.json has ragas_metrics |
| I (Qdrant All Collections bar) | Yes | None — already in ai/metrics response |
| J (Memory Growth Time Series) | Yes | None — Qdrant REST available |
| K (PRSI Cycle Timeline) | Partial (empty state) | Phase 185B for cycle detail |
| L (Workflow Execution Rate) | Partial (proxy mode) | Phase 185A for full parallel speedup |

---

## 11. Risks

### R1 — JSONL Parsing at 54 MB Scale (`hybrid-events.jsonl`)

**Risk:** Panels G and any future panels reading `hybrid-events.jsonl` at full scale will take >2s per parse at typical Python I/O rates, blocking async handlers.

**Mitigation:** Panels G uses `agent-run-events.jsonl` (3.1 MB), not `hybrid-events.jsonl`. No Phase 184C panel requires full-file parsing of the 54 MB file. The constraint is: `hybrid-events.jsonl` MUST NOT be tailed in any new dashboard route without a byte-offset checkpoint. If a future panel requires it, implement tail-via-mmap or Redis-cached checkpoint (offset stored in Redis key `dashboard:hybrid_events_offset`).

**Current file growth rate:** `hybrid-events.jsonl` emits ~78,948 events over its lifetime at ~0.68 KB/event average. At 45,012 `hybrid_search` events (the dominant type), this is the coordinator's primary activity log. New routes must use `/var/lib/ai-stack/hybrid/telemetry/continuous_learning_stats.json` (654 B, rewritten periodically) or smaller specialized files as their primary source.

### R2 — Dashboard Backend Performance Impact of New Routes

**Risk:** Adding 8 new routes, each firing 1–3 I/O operations (JSONL read + optional Qdrant REST call), could increase dashboard backend latency if multiple panels refresh simultaneously.

**Mitigation:** Each new route implements a per-route in-memory cache with TTL equal to its refresh interval. Use the existing `_AI_METRICS_CACHE` pattern from `get_ai_metrics()`. Routes reading JSONL files use `asyncio.to_thread()` to avoid blocking the event loop (per MEMORY.md "Async blocking CRITICAL" pattern). History JSONL appends are fire-and-forget via `asyncio.create_task()`.

### R3 — History JSONL Files Not Initialized on First Run

**Risk:** Frontend requests RAGAS or dataset history on first deploy; history JSONL is empty or missing; panel shows no trend.

**Mitigation:** Routes seed history JSONL on first call with a single entry (current snapshot). Frontend gracefully handles `history.length == 1` — renders a single point, not an error.

### R4 — Coordinator Auth for `/stats/delegate` Proxy

**Risk:** `GET /api/aistack/stats/delegate` proxies to coordinator at `:8003/stats/delegate`. Coordinator returned `{"error": "unauthorized", "mode": "api-key"}` on direct unauthenticated call. Dashboard backend uses `_hybrid_headers()` which includes the API key from `_load_hybrid_api_key()`. If the key is unavailable (secret file missing), all delegate panels show fallback `null`.

**Mitigation:** Add a startup check in the dashboard backend: log WARNING if `_load_hybrid_api_key()` returns None. Panel A should explicitly display "Auth unavailable — check HYBRID_API_KEY_FILE env var" rather than silent null. This is an existing risk for the current delegate panel; Phase 184C makes it explicit.

### R5 — PostgreSQL asyncpg Dependency for PRSI Cycles Route

**Risk:** Panel K (`/api/aistack/stats/prsi/cycles`) requires `asyncpg`. The existing `_ASYNCPG_AVAILABLE` guard means the route silently returns `{available: False}` if asyncpg is not installed or the DSN is misconfigured.

**Mitigation:** Route returns explicit `{available: False, reason: "asyncpg_not_installed|dsn_error", cycles: []}`. Frontend Panel K renders "PRSI history unavailable" rather than a broken chart. This is acceptable because Panel K is Phase 185B gated anyway.

### R6 — AppArmor Profile for New Telemetry Paths

**Risk:** History JSONL files written by the dashboard backend (running as a non-hyperd service user) under `/var/lib/ai-stack/hybrid/telemetry/` may need new AppArmor `rwk` rules for the `ai-dashboard` service profile.

**Mitigation:** Check existing AppArmor profile for `ai-dashboard.service` before implementing history writes. If `/var/lib/ai-stack/hybrid/telemetry/**` is already covered with `rw`, no rebuild needed. If not, add the rule in the same PR as the route and trigger a NixOS rebuild before testing. Confirm with `journalctl -u apparmor.service` post-rebuild (per MEMORY.md "AppArmor c mode = parse failure" pattern — use `rwk` not `rwkc`).

### R7 — Frontend Ring Buffer Memory Leak (Panel A)

**Risk:** Panel A time series maintains a 1440-point ring buffer in JavaScript. If the page is left open for >24h with no memory management, this could cause memory growth in long-running dashboard sessions.

**Mitigation:** Implement ring buffer with `Array.prototype.splice(0, excess)` to maintain fixed maximum length. Consider server-side history JSONL (same pattern as Panels E, H, J) as the canonical store, with frontend only rendering the last N points. This avoids frontend state management complexity.
