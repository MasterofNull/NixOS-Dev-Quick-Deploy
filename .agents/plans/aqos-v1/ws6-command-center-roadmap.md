# WS6 — Command Center Rebuild Roadmap (god-tier prompt 9)

**Date**: 2026-07-09 · **Author**: claude-fable-5 · **Status**: foundation shipped; views are delegatable slices
**Gate honored**: no SPA work began before WS5 trace data existed (it now does — `/api/trace/{id}` live).

## Why this is a roadmap, not a rewrite-in-one-slice

The existing dashboard is an 8,040-line vanilla-JS monolith that WORKS. A full
React/Svelte rewrite of 9 views is weeks of work and pure risk if done at once.
Strangler: build the OpenAPI-first FOUNDATION + fix the enabling gaps now, then
add views one slice at a time on the generated client, retiring monolith
sections as each view reaches parity.

## Foundation shipped this slice

1. **OpenAPI-first is already true** — FastAPI publishes `/openapi.json` +
   Swagger UI at `/docs` (both verified live). No work needed; the contract exists.
2. **Generated typed client** — `scripts/ai/gen-api-client.py` turns the live
   spec into `scripts/ai/lib/aq_dashboard_client.py` (318 typed methods). Views,
   CLI tools, and tests now call typed methods instead of hand-rolling urllib
   against string paths; regen on API change so the client never drifts. A
   `--check` mode gates drift in CI.
3. **Trace endpoint fixed** — `/api/trace/{id}` returned ModuleNotFoundError
   (stdlib `trace` collision + missing repo-root path + unregistered dataclass
   module). Now robust (`_load_trace_module`), validated against the exact
   dashboard import context. This unblocks the Runs view.

## The 9 views + CLI-twin parity (every mutating view has an `aq` twin)

| View | Backend (exists?) | CLI twin | Status |
|------|-------------------|----------|--------|
| **Runs** (trace waterfall) | ✅ `/api/trace/{id}` | `aq-event trace <id>` ✅ | endpoint live; view = next slice |
| **Fleet** (agents/leases/live runs) | ⚠ partial (`/api/scheduler/queue` ✅, agent list via delegation registry) | `aq-delegation-registry list` ✅ | needs a leases surface (WS9) |
| **Approvals** (HITL: repairs/intakes/deferrals) | ✅ `/api/approvals/pending` | `aq-review-repairs` ✅ | badge live; full queue view = slice |
| **Evals** (scorecards/regressions) | ✅ `/api/loop/status` + `pass_rate_alert` | `aq-local-training-loop`, `aq-model-eval` ✅ | alarm live; trend view = slice |
| **Cost** (budgets/burn) | ⚠ cascade ledger + token usage exist unaggregated | `aq-cascade summary` ✅ | needs a cost-rollup endpoint |
| **Memory** (browse/search/lineage) | ⚠ AIDB endpoints exist | `aq-memory`, `query_aidb` ✅ | lineage is WS7 |
| **Models** (registry/promotion) | ⚠ model-coordinator + model_budget | `model_budget.py`, `bench-local-agent` | registry endpoint = slice |
| **Backlog** (issues kanban) | ⚠ issues-backlog.md is the source | `aq-loop --list-open` ✅ | needs a parse endpoint |
| **Topology** (live system graph) | ✅ `/api/topology` exists | `aq-report` ✅ | render on new client = slice |

## Strangler execution order (each an activation-gated slice)
1. **Runs view** (highest value — tracing has no UI; "diagnose from the trace alone" made visual). Consumes `/api/trace/{id}` via the generated client. CLI twin exists.
2. **Approvals queue** (operator-critical — one place for repairs/intakes/deferrals).
3. **Evals trend** (regression history + the pass-rate alarm in context).
4. **Cost rollup** (needs a `/api/cost` endpoint aggregating the cascade ledger + token usage; then the view).
5. Fleet / Models / Memory / Backlog / Topology — as their backends firm up (several depend on WS7/WS9).

Each view: build on `aq_dashboard_client`, ship behind a lens tab, reach parity with the monolith section it replaces, then archive that section (Rule 12). SSE for live views comes from the existing websockets route.

## Delegation
Codex: the typed views (Runs, Approvals, Evals) on the generated client — structural frontend + endpoint work. Antigravity: design/UX of the view layouts. Local: CLI-parity audits per view. Claude: integration + the cost/registry endpoints + acceptance.
