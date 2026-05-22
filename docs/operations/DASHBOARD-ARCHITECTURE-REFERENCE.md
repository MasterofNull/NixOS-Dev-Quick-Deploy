# Dashboard Architecture Reference
Status: Active
Owner: AI Stack Maintainers
Last Updated: 2026-05-22

This document defines the supported operator and maintenance surfaces for the
dashboard stack. It exists to keep work on the still-large collector scripts
bounded and predictable.

## Supported Layers

1. Declarative runtime
   - `command-center-dashboard-api.service`
   - Primary production entrypoint
   - First place to check before debugging collector behavior
2. Collector lifecycle wrapper
   - `scripts/governance/manage-dashboard-collectors.sh`
   - Supported start/stop/restart/status/logs/refresh surface
3. Data producers
   - `scripts/data/generate-dashboard-data.sh`
   - `scripts/data/generate-dashboard-data-lite.sh`
   - `scripts/observability/collect-ai-metrics.sh`
4. AI reporting surface
   - `scripts/ai/aq-report --since=7d --format=text|json`
   - Preferred view for routing split, cache behavior, and coaching/remediation signals


## Current AI Command Center visibility contract

The production dashboard is not just a static status page. It is the operator
visibility layer for managed AI-harness changes. Current high-value cards and
backend routes include:

| Area | Dashboard/API surface | Operator question answered |
|---|---|---|
| Agent drift and overrides | `GET /api/agent-ops/status` | Is the coordinator in a nominal profile or reacting to drift? |
| Agent lessons | `GET /api/hints/report` | Which promoted lessons are shaping new sessions? |
| Hints registry | `GET /api/hints/active` | What active workflow hints are being injected? |
| Memory state | `GET /api/memory/stats`, `/api/memory/crystalline/status`, `/api/memory/supersede/history` | Is memory initialized, superseding facts, and crystallizing sessions? |
| Trace posture | `GET /api/traces/summary`, `/api/traces/drift` | Which intents/routes are active and is routing drifting? |
| Service topology | `GET /api/ports/registry`, `/api/health/aggregate` | Which managed services/ports are registered and healthy? |
| Runtime policy | `GET /api/harness/overview` | Which auth/profile/tool policy controls are currently active? |

When adding or changing a managed module, route, service, validation gate, agent
capability, or runtime policy, update either this table, a more specific runbook,
or the active PRD/plan in the same slice. If the change creates a measurable
health, drift, validation, or operational state, expose it through the Command
Center API/UI unless the handoff records why that is not applicable.

## Ownership Boundaries

Treat these as implementation details, not stable operator entrypoints:
- temporary runtime loop scripts created under `${TMPDIR:-/tmp}`
- transient collector PIDs
- ad-hoc manual background loops outside `manage-dashboard-collectors.sh`

If the dashboard is healthy but data is stale, change the supported scripts or
the declarative service wiring instead of editing temporary loop wrappers.

## Operator Flow

Health and service status:

```bash
systemctl status command-center-dashboard-api.service
bash scripts/governance/manage-dashboard-collectors.sh status
```

Refresh dashboard-facing AI metrics:

```bash
bash scripts/observability/collect-ai-metrics.sh
cat ~/.local/share/nixos-system-dashboard/ai_metrics.json | jq '.effectiveness, .services'
```

Inspect higher-level AI routing and cache evidence:

```bash
scripts/ai/aq-report --since=7d --format=text
scripts/ai/aq-report --since=7d --format=json
```

Refresh collector output manually:

```bash
bash scripts/data/generate-dashboard-data-lite.sh
bash scripts/data/generate-dashboard-data.sh
```

## Change Strategy

When making dashboard changes, prefer this order:

1. Update docs and supported operator commands first.
2. Change wrapper behavior in `manage-dashboard-collectors.sh` if lifecycle or refresh behavior is wrong.
3. Change `generate-dashboard-data*.sh` only when data production logic itself is wrong.
4. Keep temporary runtime loop mechanics hidden behind the wrapper.

## Refactor Priority

The collector scripts remain large. The current safe refactor target is not
"rewrite everything", it is:

- extract stable helper functions from `generate-dashboard-data.sh`
- preserve the supported wrapper commands
- keep `scripts/observability/collect-ai-metrics.sh` and `scripts/ai/aq-report` as the primary AI observability surfaces
- avoid introducing new operator-facing wrapper scripts unless they are clearly better than the current manager
