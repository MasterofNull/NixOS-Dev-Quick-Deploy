# Google ADK Parity Matrix and Integration Suggestions

Date: 2026-03-20
Status: active reference for Phase 4.4
Owner: codex

## Scope

This note compares the current harness against Google Agent Development Kit (ADK)
capabilities and integration patterns that are relevant to this repo. The goal
is not to replace the existing stack with ADK. The goal is to use ADK as an
external compatibility baseline for:

- multi-agent composition
- A2A and MCP interoperability
- retrieval and vector-store integration
- observability and evaluation plumbing
- workflow resilience and durable execution patterns

This matrix is repo-grounded. Scores are an inference from current code,
roadmaps, tests, and dashboard surfaces, not a claim of upstream certification.

## Repo Evidence

Current repo evidence used for this matrix:

- Hybrid workflow parity smoke covers planning, sessions, fork, tree, advance,
  and acceptance review:
  [scripts/testing/smoke-agent-harness-parity.sh](/home/hyperd/Documents/NixOS-Dev-Quick-Deploy/scripts/testing/smoke-agent-harness-parity.sh)
- A2A source-contract checks exist for the hybrid coordinator:
  [scripts/testing/test-a2a-compat.py](/home/hyperd/Documents/NixOS-Dev-Quick-Deploy/scripts/testing/test-a2a-compat.py)
- Dashboard exposes workflow compliance and A2A readiness surfaces:
  [dashboard/backend/api/routes/insights.py](/home/hyperd/Documents/NixOS-Dev-Quick-Deploy/dashboard/backend/api/routes/insights.py)
- Workflow session and evaluation trend routes already exist:
  [dashboard/backend/api/routes/aistack.py](/home/hyperd/Documents/NixOS-Dev-Quick-Deploy/dashboard/backend/api/routes/aistack.py)
- Qdrant and workflow tooling are already wired through the AI stack role:
  [nix/modules/roles/ai-stack.nix](/home/hyperd/Documents/NixOS-Dev-Quick-Deploy/nix/modules/roles/ai-stack.nix)
- Context-aware retrieval, graph-backed service/config retrieval, and ranking
  live in:
  [dashboard/backend/api/services/context_store.py](/home/hyperd/Documents/NixOS-Dev-Quick-Deploy/dashboard/backend/api/services/context_store.py)

## ADK Comparison Matrix

| Area | ADK reference surface | Current repo status | Score | Decision | Why it matters |
| --- | --- | --- | ---: | --- | --- |
| Multi-agent composition | ADK agent categories plus workflow agents | Workflow orchestration, reviewer-gate policy, team formation, and bounded sub-agent behavior are already present, but dynamic composition remains narrower than ADK's broader agent model | 75 | adapt | Good conceptual parity already exists; focus on better planner-to-runtime mapping rather than framework swap |
| A2A interoperability | ADK A2A exposure and consumption patterns | Hybrid coordinator already exposes A2A agent card, JSON-RPC task routes, SSE task events, and dashboard readiness surfaces | 85 | adapt | This is already a strength; use ADK A2A docs as a regression baseline, not a rebuild target |
| MCP interoperability | ADK MCP client/server patterns | Repo has strong MCP investment, multiple MCP services, health checks, and contract validation | 90 | adopt for parity checks | MCP is already core architecture here; ADK is useful as a standards-facing check on tool exposure patterns |
| Sessions and state | ADK REST `/run`, session-oriented runners, state delta support | Repo already has workflow session start/get/list/fork/advance and lineage views, but state semantics are workflow-centric rather than agent-runtime-centric | 78 | adapt | Map workflow sessions to a more explicit portable state contract |
| Qdrant retrieval | ADK Qdrant MCP integration for semantic memory, code search, and knowledge retrieval | Repo already uses Qdrant declaratively and now has stronger graph-backed retrieval, but retrieval QA and eval loops remain thinner than the desired parity bar | 72 | adopt selectively | Use ADK Qdrant patterns to improve retrieval eval and memory workflows, not storage ownership |
| Observability | ADK OpenTelemetry plus Phoenix/MLflow/AgentOps integrations | Repo has dashboard metrics and some evaluation trends, but lacks one canonical trace pipeline for agent, tool, retrieval, and reviewer-gate spans | 55 | adapt | This is the clearest near-term gap |
| Evaluation | ADK observability/eval integrations and batch testing surfaces | Repo has reviewer acceptance, parity smoke, and evaluation trends, but no single cross-slice eval scorecard joining routing, retrieval, workflow, and operator outcomes | 58 | adapt | Needed for Phase 4 validation and later Phase 6 QA |
| Retry / resilience plugins | ADK reflect-and-retry plugin | Repo has robust workflow guards, but not a first-class tool retry/reflection plugin with explicit policy and telemetry | 45 | adapt | Good candidate for a small internal plugin patterned after ADK behavior |
| Visual workflow/agent builder | ADK Visual Builder + Agent Config | Repo is code-first and Nix-first; ADK visual generation would currently cut across declarative ownership and create drift | 20 | defer | Useful only if constrained to non-authoritative prototypes |
| Tool/API discovery | ADK MCP tools and Cloud API Registry connector | Repo already has discovery manifests and workflow/tooling routes, but not a unified external-tool registry abstraction | 52 | adapt | Worth studying for future connector normalization, not urgent for current phases |

## Priority Integration Decisions

### Adopt

- ADK A2A and MCP documentation as an external parity checklist
  - This fits the current architecture and strengthens standards regression
    checks without changing ownership.
- ADK Qdrant integration ideas for semantic memory and retrieval evaluation
  - Keep Qdrant ownership in Nix and current services.
- ADK observability integration patterns where they can sit behind env-driven
  wiring and stay optional.

### Adapt

- Session/state model
  - Keep workflow sessions as source of truth, but define a portable state
    contract that can be compared against ADK runner/session patterns.
- Evaluation and observability
  - Create one internal trace/eval contract joining workflow phase progress,
    tool calls, retrieval results, reviewer outcomes, and operator-facing
    insights.
- Retry and reflection
  - Add an internal tool-retry policy layer influenced by ADK's reflect-and-
    retry plugin rather than importing a framework-level dependency blindly.

### Defer

- Visual Builder and Agent Config generation
  - Useful for experiments, but not as a source of truth in a Nix-first repo.
- Cloud API Registry-style connector expansion
  - Interesting long-term path, but lower value than retrieval validation and
    observability parity right now.

## Observability and Eval Recommendation

If one ADK-inspired area should move next, it is observability and evaluation.
The official ADK integrations for Phoenix, MLflow, and AgentOps all center on
the same idea: one trace stream across agent execution, model calls, and tool
usage. The repo currently has pieces of this, but not one canonical join.

Recommended order:

1. Phoenix-style self-hosted trace spine first
2. MLflow-style trace retention and eval views second
3. AgentOps-style replay and latency/cost views only if an external SaaS is acceptable

Why this order:

- Phoenix is the closest fit to the repo's self-hosted bias.
- MLflow is useful if evaluation artifacts become first-class release evidence.
- AgentOps is attractive, but introduces external SaaS coupling and telemetry
  ownership questions.

## Concrete System Improvement Suggestions

### 1. Create a single workflow trace envelope

Add a canonical event schema that spans:

- workflow plan creation
- workflow run phase transitions
- tool calls and tool failures
- retrieval query, sources, scores, and operator guidance
- reviewer-gate acceptance/rejection
- final operator-visible result

Best location:

- primary implementation in hybrid coordinator runtime
- dashboard reads via existing API routes
- env injection only through Nix modules

Expected outcome:

- Phase 4.1 and 4.2 validation becomes measurable instead of narrative

### 2. Add an ADK-style parity smoke for retrieval and state

Extend parity validation so it verifies:

- workflow session start/get/fork/advance still behaves consistently
- context-aware retrieval returns service/config evidence for operator queries
- retrieval sources and scores are exposed in a stable response contract

Best fit:

- extend [scripts/testing/smoke-agent-harness-parity.sh](/home/hyperd/Documents/NixOS-Dev-Quick-Deploy/scripts/testing/smoke-agent-harness-parity.sh)

### 3. Add a tool reflection and retry policy layer

Introduce a small internal plugin around tool failures:

- classify retriable vs non-retriable tool failures
- capture retry reason and attempt count
- persist retry telemetry into workflow/eval history
- keep retries bounded and reviewer-visible

This is a direct place to borrow from ADK's reflect-and-retry plugin without
changing the rest of the architecture.

### 4. Define a portable session-state contract

Document a stable session payload with:

- objective
- current phase
- reviewer contract
- accepted evidence
- result summaries
- learned follow-ups

This gives the harness a better external compatibility story and makes future
ADK-style comparisons more objective.

### 5. Add an integration registry with explicit decisions

Track candidate integrations as:

- `adopt`
- `adapt`
- `defer`
- `not_applicable`

For each entry record:

- rationale
- required secrets
- Nix option owner
- env vars
- validation command
- rollback note

## Suggested Phase Sequencing

### Immediate

- Phase 4.1: deployment -> monitoring -> alerting validation
- Phase 4.2: query -> agent -> storage -> learning validation
- add parity checks that prove trace/eval evidence exists for those flows

### Near-term

- implement the workflow trace envelope
- extend parity smoke with retrieval/state assertions
- add retry telemetry for tool failures

### Later

- revisit self-hosted observability choice between Phoenix and MLflow-backed
  tracing/eval
- evaluate whether any external SaaS observability is acceptable

## Recurring Discovery Loop

Run this lightweight review whenever ADK roadmap work is touched:

1. Review ADK pages for A2A, MCP, Qdrant, observability, and retry plugins.
2. Compare against current repo tests, routes, and Nix-owned wiring.
3. Update this matrix with score deltas and new `adopt|adapt|defer` decisions.
4. If a gap is actionable, attach it to a concrete roadmap batch and validation command.

## Sources

- Google ADK overview: <https://google.github.io/adk-docs/>
- Google ADK A2A docs: <https://google.github.io/adk-docs/a2a/>
- Google ADK MCP docs: <https://google.github.io/adk-docs/mcp/>
- Google ADK Qdrant integration: <https://google.github.io/adk-docs/tools/third-party/qdrant/>
- Google ADK Phoenix observability: <https://google.github.io/adk-docs/observability/phoenix/>
- Google ADK MLflow observability: <https://google.github.io/adk-docs/observability/mlflow/>
- Google ADK AgentOps observability: <https://google.github.io/adk-docs/observability/agentops/>
- Google ADK reflect-and-retry plugin: <https://google.github.io/adk-docs/plugins/reflect-and-retry/>
- Google ADK Visual Builder: <https://google.github.io/adk-docs/visual-builder/>
