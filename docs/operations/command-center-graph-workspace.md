# Command Center Graph Workspace

Status: active
Owner: hyperd
Last Updated: 2026-05-07

## Purpose

The command center now exposes two operator-facing 3D graph workspaces that are meant to untangle local, remote, and harness-side logic without leaving the dashboard:

- `Relational Repo File / Folder Graph`
- `Agentic Harness Workflow Logic`

These are not decorative graphs. They are the visual control surfaces for:

- understanding which files and directories own which system behaviors
- tracing how bootstrap, hints, planning, persisted runs, review gates, and runtime monitoring fit together
- comparing routing and workflow changes against live decision logs and validation evidence

## Graph Sources

Repo graph:

- API: `/api/config/graphs/repo-structure`
- source of truth: repo topology plus curated relationship edges from:
  - `AGENTS.md`
  - `config/service-endpoints.sh`
  - `config/workflow-blueprints.json`
  - `config/route-aliases.json`
  - `dashboard/backend/api/routes/config.py`
  - `dashboard/backend/api/routes/aistack.py`
  - `dashboard.html`
  - `scripts/ai/aq-prime`
  - `scripts/ai/aq-hints`
  - `scripts/ai/aq-context-bootstrap`
  - `scripts/ai/aq-qa`

Workflow graph:

- API: `/api/config/graphs/workflow-blueprints`
- source of truth: `config/workflow-blueprints.json`
- augmented with shared workflow surfaces:
  - `aq-prime`
  - `aq-context-bootstrap`
  - `aq-hints`
  - `POST /workflow/plan`
  - `POST /workflow/run/start`
  - `POST /review/acceptance`
  - `aq-qa 0 --json`
  - dashboard routing visibility endpoints

## Operational Use

Use the repo graph when you need to answer:

- which files own routing, dashboard visualization, or workflow contracts
- which docs or tests validate a control surface
- where a change should land to remain declarative and reviewable

Use the workflow graph when you need to answer:

- which blueprint governs a task family
- where reviewer gates appear
- which tool or endpoint a phase actually uses
- how local and remote lanes are selected or escalated
- which monitoring surfaces show the result afterward

## Monitoring and Comparison Loop

The workflow graph is meant to be read alongside:

- `/api/aistack/routing/summary`
- `/api/aistack/routing/decisions?limit=25`
- `scripts/ai/aq-qa 0 --json`

That gives one loop:

1. inspect the workflow logic graph
2. make a routing or workflow change
3. watch recent routing decisions and category drift
4. verify with `aq-qa` and Tier 0
5. compare node/edge logic against runtime behavior instead of relying on prompt history

## Validation

Run these checks after graph or workflow-logic changes:

```bash
python3 scripts/testing/test-dashboard-command-center-graphs.py
python3 scripts/testing/test-dashboard-command-center-graph-ui.py
python3 scripts/testing/test-dashboard-command-center-graph-payloads.py
scripts/ai/aq-qa 0 --json
scripts/governance/tier0-validation-gate.sh --pre-commit
```
