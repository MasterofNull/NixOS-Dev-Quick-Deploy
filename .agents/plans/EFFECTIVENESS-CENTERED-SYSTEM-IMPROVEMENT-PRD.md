---
doc_type: prd
id: effectiveness-centered-system-improvement-prd
title: Effectiveness-Centered System Improvement PRD
status: active
owner: codex
phase: "Phase 93"
priority: high
---

# Effectiveness-Centered System Improvement PRD

## Executive Summary

This PRD revisits `.agents/plans/TECHNICAL-ANALYSIS-PRD.md` after team review of the Pi coding-agent observability video context:

- Video: <https://www.youtube.com/watch?v=o4KZH_KSqYQ>
- Title resolved via YouTube oEmbed: `Pi Coding Agent Observability: HTML Specs with Gemini 3.5 Flash and GPT Image 2`
- Channel: IndyDevDan

Transcript access was not reliable in this session: YouTube exposed an auto-caption track, but timedtext returned empty content. Therefore this PRD treats the video as external inspiration around observability, specs, and agent workflow visibility, not as transcript-verified architecture authority. Related public references confirm the relevant pattern: Pi observability surfaces tokens, cost, TPS, runtime, git stats, context usage, and per-turn session history; Pi itself emphasizes extensible context engineering, skills, prompt templates, dynamic context, and exportable session trees.

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
- Keep canonical specs in Markdown plus YAML frontmatter; allow generated HTML or visual specs only as read-only observability views.
- Block Rust/runtime migrations unless low-level telemetry is tied to degraded workflow outcomes.

## Non-Goals

- No full migration from Markdown to HTML.
- No Rust rewrite as the next slice.
- No permanent expansion of agent roles around tool/model names.
- No generated dashboard or HTML artifact that becomes a canonical source of truth.
- No efficiency-only success criteria.

## Team Perspectives

### Architecture

The prior PRD optimized scaffolding: token cost, grepability, runtime speed, and machine-readable checks. Those are input metrics. The revised goal is task success: delegated slices completed without rework, spec-to-outcome fidelity, review issues caught before integration, and time-to-correct-result.

Architecture recommendation: keep Markdown/YAML as the canonical planning substrate, but add fields that improve delivery quality: `user_outcome`, `effectiveness_metric`, `acceptance_signals`, `observable_surface`, `risk`, `reviewer_gate`, and `evidence_required`.

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

### PR-3: Spec Effectiveness Metadata

PRDs and action plans should carry fields that improve task execution, not just routing.

Acceptance:

- New PRD/plan template includes outcome, effectiveness metric, evidence, observable surface, reviewer gate, and risk fields.
- A validation check can identify active plans missing acceptance criteria or effectiveness evidence.
- Existing legacy docs are not bulk-rewritten unless touched.

### PR-4: Dashboard Parity

Effectiveness must be visible in the operator dashboard after `aq-report` has stable machine output.

Acceptance:

- Dashboard has a live Effectiveness Scorecard card or KPI cluster.
- It distinguishes outcome metrics from efficiency inputs.
- No hardcoded success values; unavailable data renders unavailable/no_data with reason.

### PR-5: Evidence-Gated Runtime Migration

Rust or runtime rewrites require workflow evidence, not only implementation preference.

Acceptance:

- Attention queue emits contention telemetry before any Rust rewrite decision.
- Migration only proceeds if contention correlates with failed, delayed, or degraded agent work.
- Migration proposal documents no-regression gates for correctness, completion reliability, and observability.

## Action Plan

### Slice 93.1: Make Doc-Frontmatter Validation Real

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

### Slice 93.2: Focused-CI Diagnostic JSON

Scope:

- `scripts/governance/run-focused-ci-checks.sh`

Acceptance:

- `FOCUSED_CI_JSON=/tmp/focused.json scripts/governance/run-focused-ci-checks.sh --pre-commit` writes structured check results.
- JSON includes trigger paths matched, command, status, duration, exit code, stdout tail, stderr tail.
- Existing text output and exit behavior remain compatible.

### Slice 93.3: Validation Health In `aq-report`

Scope:

- `scripts/ai/aq-report`
- focused tests for report JSON

Acceptance:

- `aq-report --machine` includes latest focused-CI/Tier0 summary if artifact exists.
- Missing artifact reports unavailable with reason.
- Top failure ids and commands are included when available.

### Slice 93.4: Effectiveness Scorecard Prototype

Scope:

- `scripts/ai/aq-report`
- tests around scorecard schema and failure/no-data behavior

Acceptance:

- `aq-report --machine` emits `effectiveness_scorecard`.
- Scorecard separates outcomes from efficiency inputs.
- `overall_status` obeys blocking rules.
- QA check verifies schema.

### Slice 93.5: Dashboard Effectiveness Card

Scope:

- dashboard API/UI surface that already consumes `aq-report` or harness scorecard data
- `aq-qa` integration check

Acceptance:

- Live dashboard shows scorecard status, baseline/current/delta where data exists, and no-data reasons where it does not.
- No newly touched field renders `--` when source data exists.
- `aq-qa 0` includes an integration-path check for the card/source route.

### Slice 93.6: Attention Queue Contention Instrumentation

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
- Generated HTML/spec views are allowed only if derived from Markdown/YAML and labeled read-only.
- Every new subsystem ships with telemetry and a dashboard/QA/report surface.
- Any discovered no-data metric is a visibility bug, not a cosmetic issue.

## Source Notes

- YouTube video link supplied by user: <https://www.youtube.com/watch?v=o4KZH_KSqYQ>
- Pi observability package: live session observability for tokens, cost, TPS, runtime, git stats, context usage, dashboard, and per-turn history.
- Pi home page: extensible terminal coding harness with context engineering, skills, prompt templates, dynamic context, and exportable session trees.
- Planu changelog: relevant external pattern for spec status, reviewer gates, lifecycle state, and evidence-gated spec workflows.
