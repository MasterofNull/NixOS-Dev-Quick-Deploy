---
doc_type: prd
id: effectiveness-centered-system-improvement-prd
title: Effectiveness-Centered System Improvement PRD
status: complete
owner: codex
phase: "Phase 93"
priority: high
completed_at: "2026-06-04"
---

# Effectiveness-Centered System Improvement PRD

## Executive Summary

This PRD revisits `.agents/plans/TECHNICAL-ANALYSIS-PRD.md` after team review of the Pi coding-agent observability video context:

- Video: <https://www.youtube.com/watch?v=o4KZH_KSqYQ>
- Title resolved via YouTube oEmbed: `Pi Coding Agent Observability: HTML Specs with Gemini 3.5 Flash and GPT Image 2`
- Channel: IndyDevDan

Transcript access was not reliable in the first pass: YouTube exposed an auto-caption track, but timedtext returned empty content. The missing context was in the YouTube description metadata. The description states that the video runs three Gemini 3.5 Flash Pi coding agents against the same prompt using three spec types: Markdown, HTML, and enhanced visual HTML. The runs are observed live through a Pi agent observability dashboard that compares performance, speed, cost, and useful tokens. It also describes the architecture as streaming every event to a centralized server, persisting to a DB, and reading back into a UI with swim lane, single-agent, and race views. Captured data includes every tool call, token count, system prompt, trace, and context/skill bloat.

Corrected interpretation: the video is not simply an argument for HTML replacing Markdown. It is an argument for closed-loop agent engineering: controlled same-prompt experiments, first-class agent trace observability, useful-token accounting, and multimodal/visual specs as measured implementation aids. Related public references confirm the relevant pattern: Pi observability surfaces tokens, cost, TPS, runtime, git stats, context usage, and per-turn session history; Pi itself emphasizes extensible context engineering, skills, prompt templates, dynamic context, and exportable session trees.

Team consensus: the previous PRD was useful but too centered on efficiency and tooling mechanics. The next system improvement slice must optimize for effective outcomes: correct work, fewer rescue loops, better review, visible operating state, and stronger spec-to-result fidelity. Efficiency remains measured, but it cannot compensate for correctness, reliability, or observability regressions.

## Problem

The harness already measures many operational inputs: QA pass counts, routing decisions, token/cost-like metrics, cache behavior, latency, local routing, and governance checks. Those are necessary but insufficient.

Current planning can still drift toward:

- faster agent loops that do not produce better accepted work,
- cleaner CI output that does not improve diagnosis or remediation,
- doc metadata hygiene that does not improve delegation quality,
- Rust or runtime migration justified by low-level contention rather than real workflow harm,
- generated visual/spec artifacts that look useful but become second sources of truth.

The system needs a first-class effectiveness layer that answers: did this change help agents and operators ship correct, observable, reviewable work with less rework?

## Goals

- Define effectiveness before efficiency in all Phase 93 system-improvement decisions.
- Add a machine-readable effectiveness scorecard suitable for `aq-report`, QA, and dashboard surfacing.
- Require every slice to state its user/system outcome, observable evidence, validation gate, and reviewer gate.
- Convert validation output into actionable diagnosis: owner, command, affected capability, likely cause, stderr tail, and next action.
- Keep canonical specs in Markdown plus YAML frontmatter, but explicitly test generated HTML and visual HTML spec packs as read-only implementation briefs for UI/product-agent work.
- Add Pi-style run observability: central event stream, persisted replay, single-agent view, swimlane view, race mode, prompt/context/tool/token traceability, and closed-loop human controls.
- Block Rust/runtime migrations unless low-level telemetry is tied to degraded workflow outcomes.

## Non-Goals

- No full migration from Markdown to HTML.
- No Rust rewrite as the next slice.
- No permanent expansion of agent roles around tool/model names.
- No generated dashboard, HTML, or visual spec artifact that becomes a canonical source of truth.
- No efficiency-only success criteria.

## Team Perspectives

### Architecture

The prior PRD optimized scaffolding: token cost, grepability, runtime speed, and machine-readable checks. Those are input metrics. The revised goal is task success: delegated slices completed without rework, spec-to-outcome fidelity, review issues caught before integration, and time-to-correct-result.

Architecture recommendation: keep Markdown/YAML as the canonical planning substrate, but add fields that improve delivery quality: `user_outcome`, `effectiveness_metric`, `acceptance_signals`, `observable_surface`, `risk`, `reviewer_gate`, and `evidence_required`.

Corrected spec-format recommendation: the earlier HTML analysis over-indexed on text-token overhead, grepability, and diff noise. Those remain real source-control concerns, but they do not answer the video's stronger question: can a richer spec format produce better accepted artifacts for the same task? HTML and visual HTML should be evaluated as derived, hash-checked experiment variants, not rejected as if they were only replacement doc formats.

### QA And Observability

Effectiveness must be visible as an explicit scorecard, not inferred from latency or token savings. Scorecard dimensions:

- Outcome Correctness: eval pass rate, RAG relevance, faithfulness, task `final_ok`.
- Completion Reliability: delegation success, workflow completion, repair success, recurrence of unresolved failures.
- Operator Trust: intent-contract coverage, trace completeness, definition-of-done coverage, missing telemetry count.
- Regression Containment: `aq-qa` pass rate, xfail age, focused-CI failure clarity, recurring QA failures.
- Context Quality: hint adoption, memory recall usefulness, query-gap closure, context precision.
- Efficiency Inputs: latency, tokens, cost, TPS, cache hit rate, local routing, lock contention.

Gate: efficiency inputs can explain outcomes, but cannot mark a slice successful when correctness, completion, trust, or regression containment fail.

### Collaboration Reliability

Use context distillation, not team expansion. The orchestrator admits external context as a short source-labeled brief, maps it to repo problems, and passes only slice-local implications to implementers.

Review gates:

- Context Admission Gate: external claims must be source-labeled and mapped to a repo problem.
- Agent Sprawl Gate: every new agent role needs a unique owned artifact.
- Spec Format Gate: Markdown/YAML remains canonical unless a future PRD overturns it with evidence.
- Observability Gate: adopted ideas must surface measurable status in dashboard, QA, or `aq-report`.
- Independent Review Gate: implementers do not self-approve.

### Implementation Strategy

Do not start Rust work next. The highest-value slices are governance observability and decision-quality improvements:

- define an agent-run event envelope before adding more dashboards,
- build a controlled spec-variant race harness for Markdown vs HTML vs visual HTML,
- expose prompt, loaded skills, tool calls, token counts, traces, and artifacts in replayable run views,
- make doc-frontmatter validation actually check changed agentic docs,
- emit focused-CI diagnostic JSON,
- surface latest validation health in `aq-report` and then dashboard,
- instrument attention-queue contention before migration decisions,
- add spec quality scoring for active PRDs/plans/skills.

## Product Requirements

### PR-1: Effectiveness Scorecard

`aq-report --machine` should expose:

```json
{
  "effectiveness_scorecard": {
    "overall_status": "pass|warn|fail|no_data",
    "outcome_correctness": {},
    "completion_reliability": {},
    "operator_trust": {},
    "regression_containment": {},
    "context_quality": {},
    "efficiency_inputs": {},
    "blocking_reasons": []
  }
}
```

Acceptance:

- Missing data reports `no_data` with reason, not green.
- Efficiency metrics are nested under `efficiency_inputs`.
- Overall status cannot be `pass` if outcome correctness or operator trust is failing.

### PR-2: Actionable Validation Diagnostics

Focused CI and Tier0 outputs must be machine-readable enough for agents to fix failures without rerunning blindly.

Acceptance:

- `run-focused-ci-checks.sh` can write JSON with check id, status, trigger paths, command, duration, exit code, stderr tail, and stdout tail.
- Tier0 continues to fail nonzero on failed focused checks.
- Human output remains backward compatible.

### PR-3: Agent Run Event Stream And Replay

The harness should normalize every agent run into a replayable lifecycle event stream.

Acceptance:

- Events include `run_id`, `experiment_id`, `session_id`, `agent_id`, `lane_id`, `event_type`, timestamp, duration, parent event, trace id, route/profile, status, redacted payload, and source.
- Event types cover prompt load, spec variant, system prompt metadata, memory recall, skill load, model call, tool call, tool result, token usage, artifact, validation, review, human control, and final outcome.
- A run can be replayed from persisted events without reading raw logs manually.
- Sensitive prompt/tool fields are redacted or represented by digest plus safe excerpt.

### PR-4: Spec Variant Experiment Model

HTML and visual HTML are experiment variants, not canonical planning sources.

Acceptance:

- Canonical Markdown/YAML remains the source of truth for requirements, acceptance criteria, status, and data contracts.
- Derived spec packs include `derived_from`, `source_hash`, generation timestamp, generator command, variant type, and visible "Derived view, not canonical" labeling.
- Supported variants: `markdown`, `html`, `visual_html`.
- Visual HTML packs may include interface mockup asset paths, model/prompt provenance, layout annotations, and expected screenshot references.
- CI or validation fails when a derived artifact source hash no longer matches its canonical source.

### PR-5: Useful-Token And Cost-Per-Accepted-Result Metrics

Token effectiveness is the key metric: useful tokens beat fewer tokens.

Acceptance:

- `aq-report --machine` exposes total tokens, context tokens, tool-output tokens, final-output tokens, accepted-artifact tokens, rework tokens, and useful-token ratio when data exists.
- `no_data` is emitted when attribution is missing.
- Race/experiment views compare cost and speed only beside correctness, validation, and reviewer outcomes.
- Efficiency cannot pick a winner if correctness or operator-trust gates fail.

### PR-6: Pi-Style Operator Views

The dashboard should become a live debugger for agent work, not only a health summary.

Acceptance:

- Single-agent replay view answers what the agent was instructed with, which skills/context loaded, what it called, what tokens it used, what it produced, and why it failed or passed.
- Swimlane view shows N agents/sessions on a shared time axis with tool calls, waits, validation, review, and human interventions.
- Race mode compares agents/profiles/spec variants on the same prompt with outcome, latency, useful-token ratio, validation status, reviewer result, and artifact links.
- Detail drawer exposes redacted system prompt metadata, prompt hash/snippet, selected route/profile, memory collections, tool args hash/redacted args, stdout/stderr tail, token/cost/TPS, and linked QA/review result.

### PR-7: Spec Effectiveness Metadata

PRDs and action plans should carry fields that improve task execution, not just routing.

Acceptance:

- New PRD/plan template includes outcome, effectiveness metric, evidence, observable surface, reviewer gate, and risk fields.
- A validation check can identify active plans missing acceptance criteria, effectiveness evidence, or spec-variant eligibility.
- Existing legacy docs are not bulk-rewritten unless touched.

### PR-8: Dashboard Parity

Effectiveness must be visible in the operator dashboard after `aq-report` has stable machine output.

Acceptance:

- Dashboard has a live Effectiveness Scorecard card or KPI cluster.
- It distinguishes outcome metrics from efficiency inputs.
- No hardcoded success values; unavailable data renders unavailable/no_data with reason.

### PR-9: Evidence-Gated Runtime Migration

Rust or runtime rewrites require workflow evidence, not only implementation preference.

Acceptance:

- Attention queue emits contention telemetry before any Rust rewrite decision.
- Migration only proceeds if contention correlates with failed, delayed, or degraded agent work.
- Migration proposal documents no-regression gates for correctness, completion reliability, and observability.

## Action Plan

### Slice 93.1: Agent Run Event Envelope

Problem: current traces, delegation logs, tool audit logs, and workflow events are fragmented. Pi parity requires a normalized event contract before UI/race views can be trusted.

Scope:

- event schema doc/config
- lightweight emitter/parser around existing `hybrid-events.jsonl`, delegation registry, and tool-audit sources
- fixture-backed tests

Acceptance:

- A real or fixture-backed run emits/reconstructs events for prompt/spec, route, system prompt metadata, skill/context loads, tool calls, token usage, artifact, validation, review, and final outcome.
- Every event has stable IDs and can be replayed into a timeline.
- Sensitive payloads are redacted or digest-only.

### Slice 93.2: Central Agent Event API

Scope:

- dashboard backend route or existing telemetry API surface
- event reader over JSONL first; DB backing store later

Acceptance:

- `curl` can retrieve a full session trace and a compact latest-state summary.
- API supports filters by run/session/agent/spec variant/event type.
- Missing fields return `no_data` with reason.

### Slice 93.3: Spec Variant Pack Contract

Scope:

- spec pack metadata contract
- generator stub for Markdown -> HTML and Markdown -> visual HTML derived artifacts
- validation that prevents canonical-source drift

Acceptance:

- One canonical Markdown plan can produce `markdown`, `html`, and `visual_html` pack metadata.
- Derived artifacts contain `derived_from`, `source_hash`, variant, generator command, and generated-at fields.
- Validation detects stale derived artifacts.

### Slice 93.4: Multi-Agent Race Harness

Scope:

- controlled runner/registry for same prompt across selected agents/profiles/spec variants
- no production delegation behavior rewrite

Acceptance:

- A dry-run or fixture mode records three comparable runs for one prompt: Markdown, HTML, visual HTML.
- Run records include variant, agent/profile, start/end, outcome, artifact refs, token/cost/speed fields, and evaluator/reviewer verdict.
- Race winner requires correctness/operator-trust gates, not cost or speed alone.

### Slice 93.5: Useful-Token Instrumentation

Scope:

- `aq-report`
- event aggregation helpers/tests

Acceptance:

- `aq-report --machine` reports useful-token ratio or `no_data`.
- Waste buckets include abandoned context, failed retries, rejected output, duplicate search, and dead-end tool calls when attributable.
- Accepted-artifact cost and time-to-accepted-result are reported per run/spec variant when available.

### Slice 93.6: Single-Agent Replay View

Scope:

- dashboard API/UI
- QA integration check

Acceptance:

- Operator can inspect one run's prompt/spec metadata, route/profile, loaded skills, memory recall, tool calls, token counts, artifacts, validation, review, and final status.
- Redaction prevents raw secrets or unsafe prompt/tool payloads from leaking.
- `aq-qa` covers the route/view with fixture-backed events.

### Slice 93.7: Swimlane And Race Dashboard Views

Scope:

- dashboard UI/API aggregation
- visual comparison for agent/spec races

Acceptance:

- Swimlane renders one lane per agent/session/spec variant.
- Race mode compares Markdown vs HTML vs visual HTML, or agent/profile variants, using outcome, useful-token ratio, validation, reviewer verdict, latency, and artifact links.
- Missing data renders `no_data`, not `--`.

### Slice 93.8: Closed-Loop Human-Agent Controls

Scope:

- event/control model first
- UI controls after replay surfaces are stable

Acceptance:

- Human actions include pause, resume, redirect, approve, reject, request review, promote artifact, and terminate run.
- Each action emits an event and updates run state.
- Controls are permissioned and auditable.

### Slice 93.9: Make Doc-Frontmatter Validation Real

Problem: `doc-frontmatter` exists in `config/validation-check-registry.json`, but the command currently calls `check-doc-frontmatter.py` without files or `--all`, so focused CI can pass without checking changed docs.

Scope:

- `config/validation-check-registry.json`
- `scripts/governance/check-doc-frontmatter.py` if needed
- focused regression test if the repo has an established pattern for this runner

Acceptance:

- Staging a changed `.agents/plans/*.md` with invalid `doc_type` fails focused CI.
- Staging a valid migrated PRD passes.
- Failure output includes the exact file.
- `scripts/governance/tier0-validation-gate.sh --pre-commit` passes after the fix.

### Slice 93.10: Focused-CI Diagnostic JSON

Scope:

- `scripts/governance/run-focused-ci-checks.sh`

Acceptance:

- `FOCUSED_CI_JSON=/tmp/focused.json scripts/governance/run-focused-ci-checks.sh --pre-commit` writes structured check results.
- JSON includes trigger paths matched, command, status, duration, exit code, stdout tail, stderr tail.
- Existing text output and exit behavior remain compatible.

### Slice 93.11: Validation Health In `aq-report`

Scope:

- `scripts/ai/aq-report`
- focused tests for report JSON

Acceptance:

- `aq-report --machine` includes latest focused-CI/Tier0 summary if artifact exists.
- Missing artifact reports unavailable with reason.
- Top failure ids and commands are included when available.

### Slice 93.12: Effectiveness Scorecard Prototype

Scope:

- `scripts/ai/aq-report`
- tests around scorecard schema and failure/no-data behavior

Acceptance:

- `aq-report --machine` emits `effectiveness_scorecard`.
- Scorecard separates outcomes from efficiency inputs.
- `overall_status` obeys blocking rules.
- QA check verifies schema.

### Slice 93.13: Dashboard Effectiveness Card

Scope:

- dashboard API/UI surface that already consumes `aq-report` or harness scorecard data
- `aq-qa` integration check

Acceptance:

- Live dashboard shows scorecard status, baseline/current/delta where data exists, and no-data reasons where it does not.
- No newly touched field renders `--` when source data exists.
- `aq-qa 0` includes an integration-path check for the card/source route.

### Slice 93.14: Attention Queue Contention Instrumentation

Scope:

- `scripts/ai/lib/attention_queue.py`
- focused test or static contract test

Acceptance:

- Lock retry/slow-acquire events emit timestamp, operation, retry count, elapsed ms, and path or queue id.
- A report can answer whether retries exceeded 3/hour.
- No Rust, Nix packaging, or behavior rewrite in this slice.

## Decision Rules

- Prefer outcome quality over throughput.
- Treat efficiency as a measured input, not a delivery gate by itself.
- HTML and visual HTML specs are allowed as derived, hash-checked experiment variants for UI/product-agent work.
- Every new subsystem ships with telemetry and a dashboard/QA/report surface.
- Any discovered no-data metric is a visibility bug, not a cosmetic issue.

## Source Notes

- YouTube video link supplied by user: <https://www.youtube.com/watch?v=o4KZH_KSqYQ>
- Pi observability package: live session observability for tokens, cost, TPS, runtime, git stats, context usage, dashboard, and per-turn history.
- Pi home page: extensible terminal coding harness with context engineering, skills, prompt templates, dynamic context, and exportable session trees.
- Planu changelog: relevant external pattern for spec status, reviewer gates, lifecycle state, and evidence-gated spec workflows.
