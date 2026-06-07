---
doc_type: prd
id: agentic-mind-standardization-prd
title: Agentic Mind Standardization PRD
status: active
owner: codex
phase: "Phase 148"
priority: high
created_at: "2026-06-07"
---

# Agentic Mind Standardization PRD

## Problem

The harness has strong workflow rules, role docs, routing profiles, and parity
smokes, but behavior is still model-dependent. Claude currently follows the
canonical workflow more reliably than Gemini, remote OpenRouter-backed lanes,
and the local Qwen coding/chat lanes. The system can recover from many failures,
but recovery hides the fact that first-pass agent behavior is drifting.

Evidence found during Phase 148 orientation:

- `.reports/system-state-analysis.json` reports 80 delegated prompt failures in
  the current window, all recovered, split evenly between `provider_http_error`
  and `provider_request_error`.
- `data/harness-golden-evals.json` has only two golden cases and does not test
  workflow adherence, artifact shape, role compliance, review verdicts, or
  model-to-model behavioral equivalence.
- `scripts/testing/smoke-agent-harness-parity.sh` verifies profile headers and
  workflow endpoints, but not whether every model follows the same operating
  contract.
- `config/model-profile.json` was last probed on 2026-05-07, so local model
  budgets and capability assumptions may be stale.
- `docs/architecture/agent-behavior-parity-index.md` already marks runtime
  bounded delegation envelopes, MCP tool-boundary enforcement, and full trace
  path visibility as partial P1 work.

## Research Anchors

- MCP: standardize context/tool/resource/prompt exposure through protocol
  envelopes, not provider-specific habits.
- A2A: treat agent identity, capability cards, tasks, messages, and artifacts as
  explicit interchange objects.
- OpenAI Agents SDK: trace model generations, tool calls, handoffs, guardrails,
  and custom events as first-class run evidence.
- OpenTelemetry GenAI conventions: standardize agent/workflow/tool spans with
  `gen_ai.*` attributes so cross-model traces can be compared.

## Goal

Make every agent lane interoperable and swappable by enforcing the same outer
contract around all models:

1. same task envelope,
2. same role and workflow contract,
3. same context budget and prompt assembly policy,
4. same output schema and validation gate,
5. same trace and identity envelope,
6. same reviewer acceptance rubric,
7. same dashboard/aq-report visibility.

The target is not identical prose. The target is equivalent operational output:
correct artifacts, declared evidence, validated workflow steps, reviewable
changes, and traceable decisions.

## Non-Goals

- Do not tune prompts per model as the primary fix.
- Do not promote remote models as inherently correct.
- Do not make Claude-specific behavior the hidden standard; extract the behavior
  into machine-verifiable contracts.
- Do not accept fallback recovery as pass unless first-pass quality is tracked.

## Required Changes

### PR-1: Canonical Agent Task Envelope

Create a versioned task envelope used by all delegation surfaces:

```json
{
  "schema_version": "1.0",
  "task_id": "...",
  "agent_id": "...",
  "agent_type": "local|remote|codex|gemini|claude",
  "role": "orchestrator|architect|implementer|reviewer",
  "workflow_phase": "orient|research|plan|execute|validate|doc_update|commit",
  "objective": "...",
  "scope": {"files": [], "non_goals": []},
  "context_refs": [],
  "tools_allowed": [],
  "output_contract": {"format": "json|markdown|patch|review", "required_keys": []},
  "acceptance_criteria": [],
  "validation_commands": [],
  "identity": {"source": "...", "boundary": "..."}
}
```

Acceptance:

- `delegate-to-local`, `delegate-to-gemini`, `delegate-to-codex`, switchboard,
  and coordinator delegation can all emit or receive this envelope.
- Missing `role`, `workflow_phase`, `output_contract`, or identity is a contract
  failure, not a soft warning.

### PR-2: Workflow Adherence Evaluator

Add a deterministic evaluator that scores an agent response for:

- workflow phase coverage,
- role compliance,
- scope discipline,
- evidence references,
- validation plan or validation result,
- final artifact shape,
- review verdict when role is reviewer.

Acceptance:

- Add at least 12 golden cases covering planning, implementation, review,
  debugging, dashboard observability, and recovery.
- Score all configured lanes against the same cases.
- Record first-pass score separately from recovered score.

### PR-3: Local Model Re-Probe Gate

The local model profile must not remain stale after rebuilds or model changes.

Acceptance:

- `aq-qa 0` warns or fails when `config/model-profile.json.probed_at` is older
  than a configurable threshold or predates active model mtime.
- `aq-model-eval --force` refreshes the profile and records capability deltas.
- Switchboard and coordinator expose the profile age in dashboard/aq-report.

### PR-4: Output Guardrails Before Acceptance

Use external validators, not model self-report, to enforce output shape.

Acceptance:

- JSON tasks must parse and satisfy schema.
- Review tasks must contain explicit `PASS|FAIL|REQUEST_REVISION`.
- Implementation tasks must name changed files and validation commands.
- Any mismatch is recorded as `agent_contract_failed` with agent/profile/model.

### PR-5: Unified Trace Path

Every run must be replayable from prompt to route to memory to tools to response
to validation to review.

Acceptance:

- Trace events include model/provider, profile, role, task envelope hash,
  prompt hash, context refs, tool calls, token usage, output-contract result,
  validation status, and review status.
- Dashboard shows first-pass contract score by agent/profile.
- `aq-report --machine` exposes the same scorecard.

### PR-6: Prompt Assembly SSOT Audit

No local llama.cpp caller may build payloads inline unless explicitly waived.

Acceptance:

- Static test finds local `/v1/chat/completions` payload builders that bypass
  `build_llama_payload()`.
- The check verifies `chat_template_kwargs.enable_thinking=false`, tool result
  role `tool`, and local role injection.

### PR-7: Agent Interop Scorecard

Add a scorecard that answers: "Can this agent lane be swapped in for this task
class without violating the harness contract?"

Dimensions:

- task-envelope completeness,
- workflow adherence,
- output contract pass rate,
- validation success rate,
- review acceptance rate,
- trace completeness,
- first-pass vs recovered delta,
- latency/token budget fit.

Acceptance:

- Exposed in `aq-report`, `aq-qa`, and dashboard.
- Any agent/profile below threshold is routed only to eligible bounded tasks.

## Implementation Slices

### Phase 148.1: Baseline And PRD

- Commit this PRD.
- Record issue backlog entry.
- Run current parity/eval inventory.

### Phase 148.2: Golden Contract Corpus

- Expand `data/harness-golden-evals.json` into a workflow-adherence corpus.
- Include expected structured outputs and forbidden shortcuts.
- Add offline schema tests for the corpus.

### Phase 148.3: Agent Contract Evaluator

- Add `scripts/ai/aq-agent-contract-eval`.
- Evaluate saved outputs first; online model calls are optional.
- Emit JSON suitable for `aq-report`.

### Phase 148.4: aq-qa Governance Gate

- Add Phase 148 aq-qa checks:
  - golden corpus exists and validates,
  - contract evaluator exists,
  - local model profile freshness checked,
  - delegated first-pass failure telemetry visible.

### Phase 148.5: Runtime Envelope Integration

- Wrap delegate scripts and coordinator paths with the task envelope.
- Preserve backward compatibility by deriving envelopes from legacy prompts.

### Phase 148.6: Dashboard And Report Visibility

- Add Agent Interop Scorecard to `aq-report --machine`.
- Add dashboard card with agent/profile first-pass contract score.

### Phase 148.7: Routing Enforcement

- Route degraded lanes only to bounded eligible task classes.
- Require explicit override for lanes below contract threshold.

## Success Criteria

- Every model lane can be compared on the same task corpus.
- First-pass failures are visible and cannot be hidden by fallback recovery.
- Local model capability assumptions are fresh after rebuild/model changes.
- Agents that do not meet the contract are automatically constrained, not trusted
  because they eventually recover.
- Claude-like workflow adherence becomes a machine-verifiable contract shared by
  all agents, not a model-specific behavior.

