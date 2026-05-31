# Phase 53 Card Inventory And Consolidation Matrix

## Product Direction
The command center should optimize for complete system observability and exploration, with prominent error and alert notification paths. The first viewport should answer:

- Is the machine alive and responsive?
- Are CPU, GPU, memory, disk, network, and live request paths saturated?
- Which OSI layer is currently degraded?
- What is actively failing or waiting?
- What recovery/debug/admin action is available?

The dashboard should keep depth. The polish comes from hierarchy, correlation, and drill-down, not from removing data.

## Logging Recommendation
Use a unified event stream as the default command-center log model:

- Normalize events into: timestamp, severity, OSI layer, subsystem, component, summary, evidence, probable cause, related cards, and action.
- Keep raw subsystem logs available from each component detail drawer.
- Add filters for OSI layer, subsystem, severity, current incident, deployment id, workflow execution id, and time window.
- Treat logs and LLM-generated diagnostics as untrusted text; render escaped text and only expose bounded recovery actions.

This gives a professional command center: the operator watches one correlated event spine, then drills into raw logs only when needed.

## Target Command Center Modules

| Module | Purpose | Primary Layers |
| --- | --- | --- |
| Command Deck | Critical host, health, alert, and wait/crash signals | L1-L7 |
| Layer Explorer | OSI-layer health map and dependency topology | L1-L7 |
| Runtime Operations | Services, models, containers, ports, routing, circuit breakers | L2-L4 |
| Data And Memory | AIDB, embeddings, databases, RAG collections, persistence telemetry | L5-L6 |
| Intelligence Workbench | AI insights, orchestration, learning, discovery, graphs | L4-L7 |
| Validation And Release | QA, tests, deployments, workflow execution, rollback | L2-L7 |
| Security And Network | Firewall, audit, compliance, hardening, port exposure | L1-L5 |
| Recovery And Admin | Restart, debug, maintenance, package/file/security/network tools | L1-L7 |
| Event Spine | Alerts, logs, incidents, recoveries, user/system actions | L1-L7 |

## OSI Layer Interpretation

| Layer | Dashboard Meaning | Example Data |
| --- | --- | --- |
| L1 Infrastructure | Host, hardware, NixOS declarative system, packages, files, disk | CPU, GPU, memory, disk, Nix config, filesystem state |
| L2 Runtime | Processes, services, containers, jobs, deploy/runtime execution | systemd units, containers, llama runtime, deployment execution |
| L3 Connectivity | Ports, HTTP reachability, websocket health, firewall, DNS | open ports, service URLs, network IO, firewall/CrowdSec |
| L4 Coordination | Routing, switchboard, hybrid coordinator, workflow orchestration | profiles, route decisions, queues, graph flow |
| L5 Session And Persistence | AIDB, Postgres, Qdrant, caches, telemetry files, continuity | vector collections, DB metrics, persistent data, logs |
| L6 Cognitive And Semantic | RAG, embeddings, insights, learning, model optimization | semantic search, lessons, prompt/cache metrics, discovery |
| L7 Interaction | Operator UI, controls, dashboards, UX, alerts, actions | command lenses, deployment UI, recovery controls, exports |

## Current Card Inventory

| # | Current Card | Current Role | Primary Layer | New Module | Decision |
| --- | --- | --- | --- | --- | --- |
| 1 | System Overview (Host) | CPU/GPU/memory/disk/network/uptime | L1 | Command Deck | Keep as first critical panel; tighten into hardware strip plus trend drawer |
| 2 | AI Stack Status | AI service status and model cache | L2 | Runtime Operations | Merge with Runtime Inventory and AI Stack Services into AI Stack Runtime |
| 3 | Agentic Readiness | RAG and learning readiness | L6 | Intelligence Workbench | Move out of Security nav; merge with Knowledge Base summary |
| 4 | OSI Layer Health | Layer health from `aq-qa` | L1-L7 | Layer Explorer | Promote to command deck row and layer drilldown |
| 5 | System Map | Topology visualization | L3-L4 | Layer Explorer | Keep; evolve into layer-aware dependency map |
| 6 | Request Routing Flow | Mermaid routing flow | L4 | Layer Explorer | Keep; merge with workflow/routing graph surfaces |
| 7 | AIDB Health & Security | AIDB probes, dependencies, metrics | L5 | Data And Memory | Merge with Persistent AI Data and Database Metrics |
| 8 | Stack Health (Aggregate) | Aggregate service health | L2-L3 | Command Deck | Promote summary; duplicate details merge into AI Stack Runtime |
| 9 | Knowledge Base | Vector/RAG collection summary | L5-L6 | Data And Memory | Merge with Agentic Readiness and Persistent AI Data |
| 10 | Telemetry Proof | Feedback/local telemetry metrics | L5 | Event Spine | Merge with Feedback Pipeline and Local Usage Proof |
| 11 | Hybrid Coordinator Metrics | Routing, offloading, optimization | L4-L6 | Runtime Operations | Keep as Hybrid Runtime detail drawer |
| 12 | AI Internals | Prometheus-derived AI internals | L6 | Intelligence Workbench | Merge into AI Runtime Metrics detail |
| 13 | QA Phase 0 Status | Validation phase status | L7 | Validation And Release | Keep; promote failures into alerts |
| 14 | Switchboard Profiles | Routing profile status | L4 | Runtime Operations | Merge with Task Classifier Routing |
| 15 | Task Classifier Routing | Local/remote routing stats | L4 | Runtime Operations | Merge with Switchboard and Hybrid Coordinator |
| 16 | Verifier Self-Consistency | Verification status | L6 | Intelligence Workbench | Keep as Quality Guardrail detail |
| 17 | Continuous Improvement | Improvement candidates/reviews | L6 | Intelligence Workbench | Move to secondary; alert only on actionable queue |
| 18 | AI Orchestration | Sessions, teams, scoring, arbiter | L4-L7 | Intelligence Workbench | Keep, but move out of main scan path |
| 19 | Agent Evaluation Trends | Agent performance history | L6 | Intelligence Workbench | Merge with AI Orchestration quality tab |
| 20 | Discovery Signals | Discovery/low-trust signals | L6 | Event Spine | Merge into Event Spine and Intelligence Workbench |
| 21 | Local Usage Proof | Local system proof metrics | L5-L6 | Event Spine | Merge with Telemetry Proof |
| 22 | Feedback Pipeline | Telemetry file health | L5 | Event Spine | Merge with Telemetry Proof |
| 23 | Network & Firewall | Network devices, ports, firewall controls | L3 | Security And Network | Keep; make it Security nav target |
| 24 | Security Monitor | Hardening/security status | L3-L5 | Security And Network | Merge with Network & Firewall and audit surfaces |
| 25 | System Configuration | Config/runtime surfaces | L1-L7 | Recovery And Admin | Move to Admin Console |
| 26 | Continuous Learning Status | Learning stats | L6 | Intelligence Workbench | Merge with Continuous Improvement |
| 27 | Circuit Breakers (P2-REL-002) | Runtime resilience state | L2-L4 | Runtime Operations | Promote critical breakers to Command Deck alerts |
| 28 | AI Harness Operations | Maintenance/recovery actions | L7 | Recovery And Admin | Keep; move under guarded Recovery Console |
| 29 | PRSI Orchestrator Queue | Action queue/approvals | L4-L7 | Recovery And Admin | Keep; combine with actionable event spine |
| 30 | Production Hardening Progress | Hardening progress | L1-L5 | Security And Network | Move to Governance/Admin; not primary monitoring |
| 31 | Runtime Inventory | Service/runtime inventory | L2 | Runtime Operations | Merge with AI Stack Status and AI Stack Services |
| 32 | AI Stack Services | Service control list | L2-L7 | Runtime Operations | Keep controls; separate read-only state from write actions |
| 33 | Deployment Operations | Deployments, approvals, rollback | L2-L7 | Validation And Release | Keep as first-class workspace |
| 34 | Testing Operations | Test suites/execution | L7 | Validation And Release | Keep; tie failures to Event Spine |
| 35 | Persistent AI Data | Data directories/persistence | L5 | Data And Memory | Merge with AIDB and DB cards |
| 36 | Database Metrics | DB metrics | L5 | Data And Memory | Merge with Persistent AI Data |
| 37 | Quick Access | Static operator links | L7 | Recovery And Admin | Convert into command palette / admin links |
| 38 | AI Insights & Intelligence | Insights/report surfaces | L6-L7 | Intelligence Workbench | Keep; split into insight summaries and deep report drawer |
| 39 | Workflow DAG Visualization | Workflow graph | L4-L7 | Validation And Release | Merge with Graph Intelligence |
| 40 | Execution History | Workflow execution history/logs | L5-L7 | Event Spine | Keep; make logs part of unified event stream |
| 41 | Ralph Wiggum Configuration | RAG service config | L6-L7 | Recovery And Admin | Move to settings/detail drawer |
| 42 | Relational Repo File / Folder Graph | Repo graph | L6-L7 | Intelligence Workbench | Keep in Graph Intelligence workspace |
| 43 | Agentic Harness Workflow Logic | Harness workflow graph | L4-L7 | Intelligence Workbench | Keep in Graph Intelligence workspace |

## Consolidated Data Sets

### Critical System Metrics
Sources: `/api/metrics/system`, `/ws/metrics`, `/api/health/aggregate`, `/api/health/layered`.

Contains:
- CPU usage, model, temp, load average
- GPU name, utilization, VRAM
- Memory pressure
- Disk pressure
- Network throughput
- Uptime and host identity
- Aggregate health and OSI layer confidence

Command-center treatment:
- Always visible.
- Use threshold color bands and compact trend sparklines.
- Add “wait/crash” heuristics: high load, memory pressure, GPU saturation, disk full, websocket offline, no heartbeat.

### Runtime And Routing
Sources: `/api/services`, `/api/containers`, `/api/ports/registry`, `/api/ai/metrics`, `/api/aistack/routing/summary`, `/api/aistack/routing/decisions`, `/api/aistack/switchboard/profiles`, `/api/aistack/task-classification/stats`.

Contains:
- Service and container state
- Ports and endpoints
- Switchboard profiles
- Hybrid coordinator metrics
- Route decisions and lane failures
- Circuit breaker state

Command-center treatment:
- One AI Stack Runtime workspace.
- Read-only status first; action controls gated in Recovery/Admin.

### Data, Memory, And Persistence
Sources: `/api/aidb/health/detailed`, `/api/aidb/metrics`, `/api/insights/metrics/ai-specific`, `/api/stats/learning`, `/api/metrics`, telemetry files.

Contains:
- AIDB probes and dependencies
- Vector/RAG collections
- Embeddings status
- Postgres/Qdrant data
- Telemetry file sizes and last event
- Feedback pipeline state

Command-center treatment:
- One Data And Memory workspace.
- Surface stale/missing telemetry as warnings, not as separate primary cards.

### Validation, Deployments, And Recovery
Sources: `/api/aistack/aq-qa/run/0`, `/api/testing/*`, `/api/deployments/*`, `/api/workflows/*`, `/api/harness/maintenance/run`, `/api/actions/execute`, `/api/prsi/*`.

Contains:
- QA phase status
- Test suites and executions
- Deployments, approvals, rollback, logs
- Workflow DAG/execution history
- Maintenance scripts and PRSI actions

Command-center treatment:
- One Validation And Release workspace with an operator action rail.
- Failed validations become Event Spine entries with recovery suggestions.

### Security, Network, And Governance
Sources: `/api/firewall/*`, `/api/security/audit`, `/api/audit/operator/*`, `/api/config`, `/api/insights/security/compliance`, `/api/stats/circuit-breakers`.

Contains:
- Firewall backend, CrowdSec, captive portal, decisions
- Listening ports and DNS
- Security audit and hardening posture
- Operator audit events
- Configuration surfaces

Command-center treatment:
- One Security And Network workspace.
- Potentially destructive actions require confirm states and audit evidence.

### Intelligence And Graphs
Sources: `/api/insights/*`, `/api/aistack/orchestration/*`, `/api/config/graphs/*`, `/api/topology`, `/api/topology/flow`, `/api/discovery/signals`.

Contains:
- AI insights reports
- Lessons, recommendations, hints, workflow compliance
- Orchestration sessions and agent trends
- Topology, workflow, and repo graphs
- Discovery signals

Command-center treatment:
- One Intelligence Workbench.
- Make graphs workspaces, not decorative panels.

## Professional Visualization Direction

### First View: Command Deck
- Top status strip: health, active alerts, websocket/API transport, last update, runtime mode.
- Critical hardware strip: CPU, GPU, memory, disk, network, uptime.
- Layer status rail: seven compact layer cells with confidence and worst failing component.
- Active incident/event spine preview: latest severe events and recovery action.
- Mini topology: current service path and broken edge.

### Exploration Views
- Layer Explorer: click a layer to reveal cards, logs, endpoints, and recovery actions tied to that layer.
- Runtime Operations: service table with health, port, latency, logs, controls.
- Data And Memory: AIDB/Postgres/Qdrant/embeddings health and persistence timeline.
- Validation And Release: deployments, tests, rollback, workflow DAG.
- Security And Network: firewall, ports, audit, hardening.
- Intelligence Workbench: insights, graphs, learning, orchestration.

### Visual Treatment
- Keep the cyberpunk palette, but use color semantically:
  - Cyan: normal live data and selected context
  - Green: healthy / completed
  - Yellow: degraded / waiting / high load
  - Magenta: critical / action required
  - Muted blue-gray: inactive detail
- Avoid every card glowing equally. Glow only active alerts, selected layers, and live edges.
- Add compact sparklines and threshold bands for real-time hardware.
- Use linked brushing: selecting an OSI layer filters cards, logs, topology nodes, and actions.

## Recovery And Admin Capability Model

Recovery/Admin should be powerful but clearly bounded:

- Restart service / restart stack / restart dashboard API
- Run `aq-qa` by layer or full phase 0
- Open service logs and workflow logs
- Trigger deployment rollback
- Run package, file, and security maintenance scripts from allowlisted endpoints
- Rebuild/redeploy only through existing governed scripts
- Firewall/CrowdSec/captive portal controls with audit
- AIDB reindex and telemetry repair tools after explicit confirmation

Controls should live in a guarded action rail:
- Read-only monitoring is default.
- Write actions require confirmation.
- Every action writes an operator audit event.
- Action results feed back into the Event Spine.

## Implementation Passes

### Pass 1: Inventory And Semantic Classes
- Add stable `data-layer`, `data-module`, and `data-criticality` annotations to cards.
- Keep existing IDs and tests stable.
- Generate a card inventory from markup for regression checks.

### Pass 2: Command Deck
- Build the first viewport from existing data sources.
- Add active alerts and event preview.
- Add critical hardware strip and layer rail.

### Pass 3: Unified Event Spine
- Add backend aggregation endpoint for recent alerts/logs/actions.
- Normalize event payloads by layer and subsystem.
- Add frontend filters and raw-log drilldowns.

### Pass 4: Workspace Consolidation
- Reorganize cards into modules without losing detail.
- Convert duplicate cards into summary + detail drawers.
- Move low-priority governance/config cards out of the default scan path.

### Pass 5: Recovery/Admin Console
- Group recovery, debug, package, file, security, and network tools.
- Add confirmation/audit/result states.
- Tie action outputs back to alerts and logs.

### Pass 6: Visualization Polish
- Improve topology, graphs, sparklines, threshold bands, responsive behavior, keyboard accessibility, and motion restraint.
- Vendor external assets or explicitly document CSP exceptions.

## Immediate Next Slice Recommendation
Implement Pass 1: annotate each card with `data-layer`, `data-module`, and `data-criticality`, then update the Command Lenses code to filter by these attributes instead of matching card titles. This gives us a durable foundation for all later design passes without breaking existing tests or deleting data.
