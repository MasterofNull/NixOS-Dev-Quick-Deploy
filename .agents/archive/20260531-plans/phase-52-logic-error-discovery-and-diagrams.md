# Phase 52 — Logic Error Discovery + System Org Diagrams

**ID:** PHASE-52
**Status:** ACTIVE
**Goal:** Reduce friction in finding logic errors by (1) wiring AIDB vector search to
surface structurally similar code patterns and (2) adding HTML system + data-flow
diagrams to the dashboard so architecture and dependency relationships are visually
navigable.

---

## Problem Statement

Logic errors like the rate-limiter loopback omission are hard to catch without:
- Awareness of _all_ places a similar pattern should appear (rate-limit bypass,
  auth bypass, path exemption) — AIDB vector search can surface these
- A diagram showing which services talk to which, so "this path has no loopback
  bypass" is obvious at a glance — system topology diagram provides this

---

## Slices

### 52.1 — Logic Pattern Indexing in AIDB  `[implementer]`
Index structured "pattern annotations" into AIDB so semantic search finds
cross-cutting logic concerns (bypass lists, auth checks, rate limits, exemptions).

**Deliverables:**
- `scripts/ai/aq-index-logic-patterns` — scans the Python codebase, extracts:
  - Rate-limit exemption blocks
  - Auth bypass / loopback bypass lists
  - Port binding constants
  - Error-handler catch patterns
  Injects each as a doc into AIDB project `logic-patterns` with metadata
  (file, line, pattern_type, description)
- Idempotent: re-run overwrites docs by path+pattern_type key
- aq-qa check `0.9.18`: logic-patterns project exists in AIDB with >= 10 docs

### 52.2 — Logic Error Search Workflow  `[implementer]`
Given a description of an error class, retrieve the top-N semantically related
logic pattern docs from AIDB and return annotated file:line references.

**Deliverables:**
- `POST /api/logic/search` (dashboard route) — body: `{query, top_k}`
  → calls AIDB `/vector/search` on project `logic-patterns`
  → returns ranked results with file, line, pattern_type, similarity
- `aqd logic search "<description>"` subcommand (wrapper around the route)
- aq-qa check `0.9.19`: route registered + aqd subcommand present

### 52.3 — System Topology API  `[implementer]`
A coordinator endpoint that returns the live service topology as structured JSON:
services, ports, dependencies, health status, data-flow edges.

**Deliverables:**
- `GET /api/topology` in dashboard (reads `nix/modules/core/options.nix` ports +
  live `/health` status from coordinator)
- Response shape:
  ```json
  {
    "nodes": [{"id": "llama-cpp", "port": 8080, "status": "up", "role": "inference"}],
    "edges": [{"from": "hybrid-coordinator", "to": "llama-cpp", "label": "query"}],
    "generated_at": "ISO-8601"
  }
  ```
- aq-qa check `0.9.20`: `/api/topology` returns valid nodes + edges

### 52.4 — HTML System Org Diagram (Dashboard Panel)  `[implementer]`
Add a "System Map" panel to `dashboard/backend/static/dashboard.html` that
renders the topology as an interactive SVG graph.

**Deliverables:**
- New `<section id="system-map">` panel in dashboard.html
- Uses D3 force graph (loaded from CDN, no new build step):
  - Nodes: services with color-coded health (green/red/grey)
  - Edges: data-flow relationships
  - Click node → opens `?service=<id>` panel details
- `loadSystemMap()` JS function fetches `/api/topology` then renders
- Auto-refreshes every 60 s alongside other panels
- aq-qa check `0.9.21`: `loadSystemMap` function present in dashboard.html

### 52.5 — HTML Logic Flow Diagram (per-service)  `[implementer]`
A second diagram showing agent execution flow and request routing logic
(switchboard → coordinator → backends).

**Deliverables:**
- `GET /api/topology/flow` endpoint — returns Mermaid-compatible flowchart JSON
  describing the request routing graph (switchboard profiles → coordinator modes
  → backends)
- Renders inline in dashboard as a `<pre class="mermaid">` block loaded via
  `mermaid.initialize()` from CDN
- aq-qa check `0.9.22`: `/api/topology/flow` returns non-empty `flowchart` key

---

## Validation Criteria

| Check | Gate |
|-------|------|
| 0.9.18 | AIDB logic-patterns project has >= 10 docs |
| 0.9.19 | `/api/logic/search` route + `aqd logic search` subcommand present |
| 0.9.20 | `/api/topology` returns valid nodes + edges |
| 0.9.21 | `loadSystemMap` in dashboard.html |
| 0.9.22 | `/api/topology/flow` returns `flowchart` key |

aq-qa total after Phase 52: **62 checks**

---

## Execution Order

52.1 → 52.3 → 52.2 (depends on AIDB) → 52.4 (depends on topology API) → 52.5

52.1 and 52.3 are independent and can run in parallel.

---

## Rollback

- Remove `logic-patterns` AIDB project docs: `DELETE /documents?project=logic-patterns`
- Remove `/api/logic/search` and `/api/topology*` routes from dashboard
- Remove `loadSystemMap` and mermaid block from dashboard.html
- Revert `aqd` version and subcommand entries
