---
doc_type: prd
id: phase-115-system-intelligence-hub-prd
title: "Phase 115 — System Intelligence Hub: Live Codebase State for Humans and Agents"
status: active
owner: claude
phase: "Phase 115"
priority: high
evidence_required: aq-system-state artifact generates cleanly; dashboard nav panel loads without N/A; agent MCP tool returns structured data
---

# Phase 115 — System Intelligence Hub

## Problem

As this codebase grows through LLM-generated work, both human developers and AI agents spend
significant time re-deriving system state at the start of every session. The current tooling
(`aq-report`, `MEMORY.md`, `HANDOFF.md`, `aq-session-start`) partially addresses this, but
each source is siloed:

- `aq-report` reports performance metrics only — not code structure or service wiring
- `MEMORY.md` has agent context but degrades on a 150-line budget
- `HANDOFF.md` captures task state but not system topology
- Dashboard shows live metrics but not structural/historical state
- AIDB has semantic knowledge but requires query overhead
- Git log has history but no synthesis

The result: agents run 10-15 discovery commands every session to answer questions like "what
services depend on Redis?", "which modules have open errors?", "what changed since the last
rebuild?" This is token-expensive and error-prone (stale assumptions, hallucinated file paths).

The problem compounds when multiple agents collaborate: each agent re-derives the same state
independently, with no shared synthesis layer.

## Goals

1. **Eliminate session-start re-discovery overhead** for agents and humans.
2. **Provide a single authoritative system state document** that is always fresh.
3. **Enable natural-language querying** of system state by agents via an MCP tool.
4. **Surface structural visualizations** on the dashboard: service topology, error patterns,
   data storage, code health, validation history.
5. **Support multi-agent coordination** by making system state legible across agent boundaries.

## Non-Goals

- No new data collection infrastructure — reads from existing sources only.
- No replacement of `aq-report`, `aq-qa`, `MEMORY.md`, or `HANDOFF.md`.
- No Rust or full-stack rewrite.
- No generated artifact that becomes a canonical source of truth (it reflects sources; sources govern).
- No hallucinated or inferred data — if a source is unavailable, the field is marked `no_data`.

## Architecture Overview

```
Existing Sources                 Synthesis Layer              Consumers
─────────────────                ────────────────             ─────────
Service systemd                 ┌──────────────────┐         Agents:
Git metadata          ────────► │ aq-system-state  │ ──────► session-start
Coordinator telemetry          │  (timer: 15min)  │         aq-hints
Validation registry  ────────► │                  │         delegate context
AIDB collections               └──────────────────┘
Attention queue                         │
Coordinator logs                        ▼              Humans:
aq-report artifact           latest-system-state.json  dashboard nav
RESUME.json/HANDOFF.md       latest-system-state.md    HANDOFF briefing
```

## Layers

### Layer 1 — `aq-system-state` Artifact (Core)

**What:** A new CLI command `aq-system-state` that synthesizes all available sources into a
structured JSON artifact (`/var/lib/ai-stack/hybrid/telemetry/latest-system-state.json`) and a
human-readable Markdown summary (`latest-system-state.md`).

**Sources synthesized:**

| Domain | Source | Output fields |
|--------|--------|---------------|
| Git | `git log`, `git status`, `git branch` | recent_commits (last 10), uncommitted_changes, active_branch, diverged_slices |
| Services | `systemctl` state for all `ai-*` units | name, status, active_since, last_error, pid, Nix store hash |
| Code structure | `find` + module index | module_map (file → size/modified/error_count), churn_hotspots (changed 3+ times in 7d) |
| Validation | validation-check-registry.json + last focused-CI JSON | check_id, status, last_run, failure_count, command |
| Errors | Coordinator logs (last 1h, ERROR/WARN level) | error_type, count, first_seen, last_seen, service |
| Attention | ATTENTION.json + ATTENTION_ARCHIVE.jsonl (24h) | pending_count, recent_auto_ok, recent_human_gate |
| Data topology | Qdrant /collections, PG tables, Redis INFO | collection_name, point_count, disk_mb; pg_table, row_count; redis_memory_mb, key_count |
| Agent state | RESUME.json, HANDOFF.md (first 50 lines), PENDING.json | current_objective, phase, open_tasks, recent_handoff |
| Performance | latest-aq-report.json (freshness ≤ 7d) | scorecard summary, delegation_rate, useful_ratio, top_errors |

**Output artifact schema (abbreviated):**
```json
{
  "generated_at": "ISO timestamp",
  "freshness_seconds": 300,
  "git": { "branch": "main", "recent_commits": [...], "uncommitted_files": [] },
  "services": [ { "name": "ai-hybrid-coordinator", "status": "active", "uptime_s": 28800 } ],
  "code_health": { "module_count": 142, "churn_hotspots": [...], "open_error_files": [...] },
  "validation": { "total_checks": 63, "passing": 62, "failing": 0, "last_run_at": "..." },
  "errors": [ { "service": "coordinator", "type": "backend_500", "count": 3, "last_seen": "..." } ],
  "attention": { "pending_human_gate": 0, "recent_auto_ok": 5 },
  "data_topology": {
    "qdrant": [ { "name": "error-solutions", "points": 22 } ],
    "postgres": [ { "table": "tool_audit", "rows": 8900 } ],
    "redis": { "memory_mb": 1.2, "keys": 340 }
  },
  "agent_state": { "objective": "...", "phase": "...", "open_tasks": [...] },
  "performance_summary": { "scorecard_status": "fail", "completion_reliability": 0.647 }
}
```

**Refresh:** `ai-system-state.timer` — runs `aq-system-state` every 15 minutes via systemd timer.
Timer writes to the fixed artifact path. Dashboard and agents read from the artifact.

**CLI output modes:**
- `aq-system-state` — writes artifact + prints summary to stdout
- `aq-system-state --fmt json` — prints JSON only
- `aq-system-state --diff` — shows delta from previous run (changed fields only)
- `aq-system-state --domain git|services|errors|data` — focused domain output

### Layer 2 — Dashboard "System Navigator" Panel

**What:** A new "System Navigator" lens on the dashboard with 4 visualization cards:

**Card 1: Service Topology (dependency DAG)**
- SVG/canvas DAG of all `ai-*` services with `after=`/`wants=` edges
- Node color = service health (green/yellow/red)
- Click → opens systemd journal tail in modal
- Data source: `latest-system-state.json`.services + Nix module static analysis

**Card 2: Error Pattern Heatmap**
- Grid: services (rows) × time buckets (columns, 1h each, 24h window)
- Cell = error count (gradient: 0 = transparent, high = red)
- Hover → shows top error types for that cell
- Data source: coordinator logs + attention archive

**Card 3: Data Storage Gauge**
- Horizontal bars: Qdrant (N collections, X MB), PostgreSQL (N tables, X MB), Redis (X MB)
- Sub-bars per collection with point count + last-write timestamp
- Flags stale collections (no writes in 7d)
- Data source: `latest-system-state.json`.data_topology

**Card 4: Code Health Treemap**
- Treemap: files sized by churn_count × error_count (last 7d)
- Color: red = high churn + errors, green = stable + clean
- Labels: module path (truncated), last modified
- Click → opens file in VS Code (via `vscode://` URI)
- Data source: `latest-system-state.json`.code_health

**Dashboard integration:**
- New lens tab: "System" (between "Overview" and "Agent Observability")
- `loadSystemNavigator()` function in dashboard.js
- `setInterval(loadSystemNavigator, 900_000)` (15min, matches artifact refresh)
- `aq-qa` check: `system-navigator-card` verifies the API endpoint returns valid data

### Layer 3 — Agent-Queryable MCP Tool

**What:** A `context_system_state` MCP tool registered in the coordinator that agents can call
instead of running 10+ discovery commands.

**Tool schema:**
```python
@tool("context_system_state")
async def context_system_state(
    domain: str = "all",   # all | git | services | errors | data | agent_state | validation
    query: str = "",        # optional natural-language filter
    max_age_s: int = 900,   # reject artifact if older than this
) -> dict
```

**Behavior:**
1. Read `latest-system-state.json` (from artifact path)
2. If artifact is missing or stale (> max_age_s), trigger a fresh `aq-system-state` run
3. Filter to requested domain
4. If `query` is provided, embed it and return semantically-relevant subsets
5. Return structured dict with a `summary` field (human-readable, ≤ 200 tokens)

**Why this reduces session overhead:**
- Agents call `context_system_state(domain="errors")` once instead of parsing 5+ log files
- Returns structured data usable for decision-making without further processing
- `summary` field can be injected directly into agent context
- Stale data triggers automatic refresh so agents never act on old state

**AIDB integration:**
- Every artifact generation also upserts a condensed summary into AIDB collection `system-state`
- Enables semantic queries: "which services were broken last week?" → time-windowed AIDB search

### Acceptance Criteria

| Slice | Criterion | Validation |
|-------|-----------|------------|
| 115.1 | `aq-system-state --fmt json` runs without error and produces all top-level keys | focused CI check |
| 115.2 | Artifact refreshes every 15min; `systemctl status ai-system-state.timer` active | aq-qa check |
| 115.3 | `latest-system-state.json` < 1 second stale after manual `aq-system-state` run | integration check |
| 115.4 | Dashboard "System" lens loads without N/A in any card | aq-qa browser check |
| 115.5 | Service topology DAG renders all `ai-*` services with correct health colors | visual check |
| 115.6 | Error heatmap shows ≥ 1 cell with data from last 24h coordinator logs | integration check |
| 115.7 | `context_system_state(domain="services")` returns all active services | coordinator test |
| 115.8 | Tool handles stale/missing artifact gracefully (triggers refresh, no exception) | unit test |
| 115.9 | AIDB `system-state` collection shows ≥ 1 point after first run | aq-qa check |
| 115.10 | `aq-session-start` reads artifact summary and injects into session context | integration check |

## Slices

### Slice 115.1 — `aq-system-state` CLI + artifact schema
- **File**: `scripts/ai/aq-system-state` (new)
- **Nix**: service entry in `mcp-servers.nix` for `ai-system-state.timer`
- **Dependencies**: jq, curl (already in env); systemctl (already available)
- **Estimated effort**: 2-3 hours

### Slice 115.2 — Systemd timer for artifact refresh
- **File**: `nix/modules/services/system-state.nix` (new)
- **Timer**: `OnCalendar=*:0/15` (every 15 minutes)
- **Writes**: `/var/lib/ai-stack/hybrid/telemetry/latest-system-state.json`
- **Estimated effort**: 30min

### Slice 115.3 — Dashboard System Navigator panel
- **Files**: `assets/dashboard.js`, `dashboard.html`
- **New lens**: `setLens('system')` with 4 visualization cards
- **Data API**: reads from `latest-system-state.json` via new dashboard route `/api/aistack/system-state`
- **Estimated effort**: 3-4 hours

### Slice 115.4 — `context_system_state` MCP tool in coordinator
- **File**: `ai-stack/mcp-servers/hybrid-coordinator/extensions/system_state_tool.py` (new)
- **Registration**: in `router.py` tool registry
- **AIDB upsert**: writes summary to `system-state` Qdrant collection
- **Estimated effort**: 2-3 hours

### Slice 115.5 — `aq-session-start` integration
- **File**: `scripts/ai/aq-session-start` (edit)
- **Change**: Read `latest-system-state.json` at session start; inject `agent_state` + `errors` + `validation` sections into session context
- **Estimated effort**: 1 hour

## Decision Rules

- Source data governs: the artifact is a cache, not a source of truth.
- If any source is unavailable, the field is `null` with `_source_status: "unavailable"`.
- Freshness is always shown; agents must check `freshness_seconds` before trusting stale data.
- Visualizations are informational only — never block deployments or gates.
- The artifact is NOT a new canonical spec format — it supplements existing docs.
- Start with Slice 115.1 before any visualization work.

## Team Perspectives

### Architecture
The artifact-first approach is correct. Build the synthesis layer before the visualization layer —
visualization without reliable data is worse than no visualization. The 15-minute refresh is
appropriate; shorter intervals waste I/O, longer intervals let state drift too far.

Key risk: the code health treemap requires static analysis that may be slow on large repos.
Mitigation: use `git log --name-only` (O(N) on changed files) rather than full AST analysis.

### QA
Every new card needs an `aq-qa` check before merge. The system navigator is visible infrastructure —
it must pass the same governance gate as any other service. Add `system-navigator-card` and
`context-system-state-tool` to the validation registry.

### Local Agent
The `context_system_state` tool is the highest-value slice for local agent performance.
Current Qwen3-35B sessions spend ~500 tokens on re-deriving what services are running.
The tool provides this in a single structured response. Implement Slice 115.4 early.
