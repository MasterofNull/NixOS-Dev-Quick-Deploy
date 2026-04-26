# AI Harness Slice Registry & Scorecard Design

**Date:** 2026-04-25
**Status:** Proposed / Initial Implementation Landed
**Scope:** AI harness structure governance across tools, servers, MCP, monitoring, workflows, communications, data, dashboard, and security slices

---

## 1. Executive Summary

The AI harness already contains most of the right building blocks, but they are distributed across multiple subsystems with uneven discoverability, contract quality, and validation depth. The practical problem is not just missing features. It is the lack of one canonical inventory that says:

- what each slice is,
- where its implementation lives,
- how it is configured,
- how it is validated,
- how it is observed,
- how it is rolled back,
- and how mature it is relative to the rest of the harness.

This design introduces two repo-native assets:

1. `config/ai-harness-slice-registry.json`
   A declarative inventory of harness slices and their contracts.
2. `scripts/governance/ai-harness-slice-scorecard.py`
   A governance tool that validates the registry and computes a maturity scorecard using repo-grounded evidence.

The goal is to make slice quality measurable and to turn architectural guidance into something enforceable by tooling.

---

## 2. Problem Statement

Today the harness is discoverable only by reading several directories and mentally composing the system:

- `ai-stack/mcp-servers/`
- `ai-stack/workflows/`
- `ai-stack/monitoring/`
- `dashboard/backend/api/`
- `scripts/ai/`
- `scripts/governance/`
- `config/`
- `nix/modules/`

That is workable for a human already deep in the repo, but weak for:

- new contributors,
- agents resuming work midstream,
- reviewers deciding whether a subsystem is well-governed,
- and operators trying to understand which areas are mature versus fragile.

The absence of a slice registry produces recurring failure modes:

- duplicated architecture logic with no declared owner,
- hidden runtime contracts,
- validation gaps between code and service wiring,
- observability implemented in one subsystem but not discoverable from another,
- and “backend-only” capability additions with no operator-facing surface.

---

## 3. Design Goals

The slice registry and scorecard should:

- provide one canonical slice inventory,
- stay repo-native and declarative,
- require evidence, not narrative claims,
- be cheap to validate locally,
- map to existing governance and Tier 0 workflows,
- and support gradual adoption without forcing a full harness rewrite.

Non-goals for this first cut:

- runtime auto-discovery of every slice,
- full dashboard integration,
- auto-generated service graphs,
- or deep semantic validation of every command and endpoint.

---

## 4. Slice Model

Each harness domain is treated as a slice with seven evaluation dimensions:

1. `contract`
2. `owner_surface`
3. `control_plane`
4. `data_plane`
5. `observability`
6. `quality_gate`
7. `discoverability`
8. `governance`

Each slice must answer these questions:

| Dimension | Question |
|-----------|----------|
| Contract | What does this slice do, what goes in/out, and what must always hold true? |
| Owner surface | Which repo paths and entrypoints own the implementation? |
| Control plane | How is it configured, enabled, routed, or policy-controlled? |
| Data plane | What runtime paths, APIs, tools, and persistence surfaces execute the logic? |
| Observability | How do we know the slice is healthy, degraded, or drifting? |
| Quality gate | What commands/tests prove changes are safe? |
| Discoverability | How does an operator or agent reach this slice through normal interfaces? |
| Governance | What risk level, secrets, rollback, and review constraints apply? |

---

## 5. Maturity Levels

The scorecard maps slices to four maturity levels:

### 5.1 Defined

The slice has:

- a stable `id`,
- summary and domain,
- owner paths,
- contract invariants,
- and control/data plane references.

### 5.2 Validated

Defined plus:

- validation commands,
- test or verification paths,
- explicit acceptance signals.

### 5.3 Observable

Validated plus:

- health or metric signals,
- dashboards or alert surfaces,
- log/probe sources.

### 5.4 Governed

Observable plus:

- risk classification,
- rollback guidance,
- secret surface declaration,
- review or policy checks.

This is intentionally strict. A powerful subsystem without explicit validation or rollback is not mature.

---

## 6. Registry Schema

The initial registry lives at:

- `config/ai-harness-slice-registry.json`

Top-level fields:

- `version`
- `description`
- `score_dimensions`
- `maturity_levels`
- `slices`

Each slice includes:

- identity: `id`, `name`, `domain`, `summary`, `maturity_target`
- owner surface: `primary_paths`, `entrypoints`
- contract: `inputs`, `outputs`, `invariants`, `failure_modes`, `rollback_commands`
- control plane: `config_paths`, `policy_paths`, `service_units`, `upstream_dependencies`, `downstream_consumers`
- data plane: `runtime_paths`, `storage_paths`, `api_endpoints`, `mcp_tools`
- observability: `health_checks`, `dashboards`, `alerts`, `metrics_signals`, `log_sources`
- quality gate: `validation_commands`, `test_paths`, `acceptance_signals`
- discoverability: `docs`, `cli_entrypoints`, `dashboard_routes`
- governance: `risk_level`, `secret_surfaces`, `review_commands`, `notes`

The registry is intended to be small enough to review directly, but structured enough for tooling.

---

## 7. Scorecard Logic

The governance script computes two related outputs:

1. structural validation
2. maturity scorecard

### 7.1 Structural Validation

The script checks:

- required top-level keys exist,
- each slice has required sections,
- file paths referenced by the registry exist in the repo,
- maturity targets are valid,
- risk levels are valid,
- required arrays are not empty where emptiness would make the slice meaningless.

### 7.2 Maturity Scoring

Each dimension is scored pass/warn/fail using repo evidence:

- `contract`: non-empty inputs, outputs, invariants, failure modes, rollback commands
- `owner_surface`: primary paths exist and entrypoints are declared
- `control_plane`: config or policy references exist
- `data_plane`: runtime paths exist and at least one execution surface is declared
- `observability`: at least one health/metric/log surface and one operator signal exist
- `quality_gate`: validation commands and test paths exist
- `discoverability`: docs and at least one CLI/API/dashboard entry surface exist
- `governance`: risk level and review commands are present

The scorecard then derives:

- raw score
- percent score
- achieved maturity
- target maturity
- blockers

This makes the output useful both for architecture review and backlog prioritization.

---

## 8. Initial Slice Set

The initial registry covers these high-level slices:

1. `routing-orchestration`
2. `switchboard-frontdoor`
3. `mcp-server-platform`
4. `aidb-memory-data`
5. `workflow-engine`
6. `aq-cli-tooling`
7. `monitoring-observability`
8. `dashboard-operator-surfaces`
9. `agent-guidance-communications`
10. `security-governance`

This is not the final slice taxonomy. It is the minimum useful first pass that reflects the repo’s current system boundaries.

### 8.1 Decomposition Wave 1

The first refinement wave starts by decomposing the broad `aq-*` tooling area into narrower operational slices:

1. `aq-bootstrap-hints-tooling`
2. `aq-runtime-diagnostics-tooling`
3. `aq-workflow-orchestration-tooling`
4. `aq-reporting-knowledge-tooling`

This is the preferred pattern for future refinement:

- start with one broad slice,
- split it only when the repo already contains distinct contracts and entrypoints,
- keep the scorecard engine stable while the taxonomy becomes more precise.

### 8.2 Decomposition Wave 2

The second refinement wave decomposes the old `monitoring-observability` slice into:

1. `service-health-monitoring`
2. `telemetry-alerting-observability`
3. `readiness-insights-observability`

This split follows the actual repo boundaries:

- `scripts/health/` and dashboard health services own service probe truth,
- `ai-stack/monitoring/`, `ai-stack/observability/`, and alert configs own telemetry and alerting,
- `dashboard/backend/api/services/ai_insights.py` and `routes/insights.py` own readiness aggregation.

### 8.3 Decomposition Wave 3

The third refinement wave decomposes the old `agent-guidance-communications` slice into:

1. `prompt-registry-evaluation-guidance`
2. `hints-context-guidance`
3. `agent-instruction-sync-distribution`

This split follows the current repo boundaries:

- `ai-stack/prompts/registry.yaml` plus `aq-prompt-eval` own prompt registry and scoring,
- `hints_engine.py`, `aq-hints`, and context-card/bootstrap surfaces own task-scoped guidance,
- `sync-agent-instructions` and `import-agent-instructions.sh` own policy distribution and AIDB-facing instruction sync.

---

## 9. Recommended Use

Use the registry and scorecard in four places:

### 9.1 Architecture Review

Before large subsystem work:

```bash
python3 scripts/governance/ai-harness-slice-scorecard.py --format text
```

Use the results to decide which slice lacks contracts, tests, or observability.

### 9.2 Task Scoping

Before implementing a new harness capability:

- identify the owning slice,
- update that slice’s registry entry,
- reject backend-only changes that add no discoverability or validation surface.

### 9.3 Governance / Readiness

Use the scorecard as a readiness summary for:

- roadmap reviews,
- deploy readiness,
- subsystem hardening,
- architectural debt prioritization.

### 9.4 Incremental Enforcement

The first cut is advisory. Recommended follow-up:

1. add this script to broader governance checks,
2. add dashboard/API exposure for slice readiness,
3. require registry updates for major harness subsystems,
4. add slice-specific acceptance reports.

---

## 10. Re-engineering Guidance By Dimension

### 10.1 Contract

- Replace magic-string behavior with explicit registries and decision objects.
- Require invariants and rollback notes for every slice.

### 10.2 Owner Surface

- Reduce split-brain ownership.
- Prefer one canonical runtime path and one canonical config path per behavior.

### 10.3 Control Plane

- Keep Nix and `config/` as the source of truth for ports, profiles, and feature enablement.
- Reject runtime-only policy that has no declarative owner when a declarative owner is viable.

### 10.4 Data Plane

- Make API routes, MCP tools, and persistence surfaces explicit.
- Remove hidden runtime entrypoints where possible.

### 10.5 Observability

- Every slice needs health, logs, and at least one operator-visible signal.
- Prefer per-slice readiness over only global system health.

### 10.6 Quality Gate

- Every slice needs small focused checks plus Tier 0.
- Validation commands should be runnable without guesswork.

### 10.7 Discoverability

- Surface capabilities through `aq-*`, dashboard, routes, or runbooks.
- Avoid hidden internals that require source spelunking to use.

### 10.8 Governance

- Risk should be declared per slice.
- Secret surfaces and review commands must be explicit.

---

## 11. Rollout Plan

### Phase 1

- Land the registry and scorecard tool.
- Populate high-level slices only.

### Phase 2

- Add slice ownership to major architecture docs.
- Expand registry entries with stronger acceptance signals.
- Continue decomposing broad slices whose notes or evidence show they are carrying multiple operational roles.

### Phase 3

- Expose readiness through dashboard insights.
- Add CI or Tier 0 hooks for strict validation.

### Phase 4

- Break broad slices into sub-slices where scorecard data shows they are too coarse.

---

## 12. Acceptance Criteria

This design is successful when:

- the repo has one canonical slice registry,
- the registry is machine-validated,
- the scorecard identifies weak slices using real path evidence,
- and contributors can use it to scope improvements without inventing a new taxonomy each time.

---

## 13. Initial Artifacts

- Registry: `config/ai-harness-slice-registry.json`
- Scorecard tool: `scripts/governance/ai-harness-slice-scorecard.py`

These artifacts are intentionally conservative. They create a stable governance surface first, then leave room for deeper runtime integration later.
