# Flat Model-Team PRD Protocol

Date: 2026-06-08
Status: Collaboration contract for PRD and plan creation
Scope: Gemini, Codex, local models, Claude/remote lanes, and future model teams
Gemini remediation companion: `.agents/prompts/GEMINI_WORKFLOW_REMEDIATION_HANDOFF.md`

## Intent

Move from "one orchestrator assigns one agent" to a flat collaborative structure:

1. Each model forms or simulates the expert team it needs.
2. Each model team creates its own PRD/plan proposal from the same scoped brief.
3. Every model team reviews every other team proposal.
4. The teams merge agreed additions and explicitly record disagreements.
5. Only after consensus does the system delegate implementation slices to role/domain experts.
6. Each model executes selected/assigned slices and reviews other models' work.
7. Lessons, failures, and routing choices are fed back into the harness.

This is not a replacement for the canonical 8-step workflow. It is the collaboration pattern used inside `PRD/PLAN`, `EXECUTE(slice)`, `VALIDATE`, and `DOC-UPDATE`.

## Why Gemini Is Drifting

Observed symptoms:
- Gemini is editing PRD/policy files directly rather than spawning/referencing peer model teams.
- Its plans are useful but do not show independent model-team proposals, peer review, consensus, or merged deltas.
- It has added workflow-like rules in `.agent/WORKFLOW-CANON.md` instead of keeping parity work in PRDs/overlays.
- It does not consistently demonstrate validation, commit readiness, correct tool-mode behavior, or collaboration-state transitions before declaring work complete.

Likely local causes to verify before implementation:
- `config/local-agent-config.yaml` currently marks `multi_agent_collaboration: false`.
- `config/workflow-automation.yaml` currently marks `collaborative_workflows: false`.
- Existing collaboration docs/configs describe team formation and consensus, but current delegation CLIs do not appear to enforce this protocol for Gemini direct CLI work.
- `delegate-to-local` has an open artifact/status mismatch, so direct local-team work cannot yet be trusted as fully observable.

Gemini-specific remediation requirements are captured in `.agents/prompts/GEMINI_WORKFLOW_REMEDIATION_HANDOFF.md`. Model teams must read that file before accepting Gemini-authored PRDs, plans, implementation slices, validation claims, or commits.

## Required Team Shape

Each model must create or simulate the experts needed for the PRD:

- Architect: system layering, abstractions, integration boundaries.
- Implementer: file paths, slice order, smallest viable changes.
- Reviewer: pass/fail criteria, regression risks, missing tests.
- Security Reviewer: prompt injection, permissions, auth, sandboxing, autonomous action boundaries.
- Performance/Tokenomics Engineer: token use, latency, cache pressure, model/profile selection.
- Operator/Observability Owner: dashboard, aq-qa, health-spider, alerts, run replay.
- Domain Expert(s): selected based on task, such as NixOS, frontend, RAG, MLOps, QA automation.

Each model may add specialists, but must state why.

## Flat PRD Workflow

### 1. Shared Brief

The human or initiating agent writes one shared brief:
- Objective.
- Scope.
- Non-goals.
- Known constraints.
- Relevant files by path only.
- Required sources.
- Acceptance criteria for the planning phase.

Current briefs:
- `.agents/prompts/TOKENOMICS_PARITY_TEAM_HANDOFF.md`
- `.agents/plans/OBSERVABILITY-PARITY-PLAN.md`

### 2. Independent Model-Team Proposals

Each model team produces a proposal artifact:

```
.agents/plans/model-proposals/<topic>/<model>-proposal.md
```

Required sections:
- Team roster and why each role was selected.
- Current-state findings with file references.
- Proposed architecture.
- Slice backlog with owners and dependencies.
- Validation matrix.
- Risks and rollback.
- Explicit disagreement with the shared brief, if any.

Rules:
- Do not read other teams' proposals before writing your own first pass.
- Do not implement code during proposal generation.
- Do not alter `.agent/WORKFLOW-CANON.md` unless the requested work is specifically a workflow-contract change.

### 3. Cross-Review

Every model reviews every other proposal:

```
.agents/plans/model-proposals/<topic>/reviews/<reviewer>-on-<author>.md
```

Review verdicts:
- `ACCEPT`
- `ACCEPT_WITH_EDITS`
- `REQUEST_REVISION`
- `REJECT`

Required review dimensions:
- Correctness against repo facts.
- Tokenomics/resource impact.
- Security and autonomy boundaries.
- Observability coverage.
- aq-qa/dashboard coverage.
- Feasibility on current hardware.
- Whether the plan preserves the canonical workflow.

### 4. Consensus Merge

A synthesis pass creates:

```
.agents/plans/<topic>-CONSENSUS-PRD.md
.agents/plans/<topic>-SLICE-BACKLOG.md
.agents/plans/<topic>-DECISION-LOG.md
```

Consensus merge rules:
- Keep only additions supported by at least two model teams or by one team plus strong repo evidence.
- Preserve minority objections in the decision log.
- Mark unverified external claims as `research_required`.
- Convert broad goals into measurable acceptance criteria.
- Assign each implementation slice to the best-fit role/model, not the model that proposed it.

### 5. Slice Delegation

After consensus:
- Slice owners select or receive slices.
- Each slice has one implementer and a different reviewer.
- Security-sensitive slices require an eligible security reviewer.
- Dashboard/API/service slices require aq-qa and visible dashboard coverage.
- Local model slices must use measured token budgets and `enable_thinking=false` in llama.cpp payloads.

### 6. Review and Learning

After each slice:
- Another model reviews the diff.
- Findings are structured as `critical`, `warning`, or `suggestion`.
- Accepted lessons are added to HANDOFF, memory/issues backlog, or RAG seeds as appropriate.
- Routing decisions and tokenomics metrics are captured for future team selection.

## Observability PRD Specific Requirements

Gemini's current `.agents/plans/OBSERVABILITY-PARITY-PLAN.md` must be treated as one model-team proposal, not the final plan.

Before implementation, require:
- Codex review.
- Local model review if delegation artifact persistence is fixed or via `aq-chat`/raw local prompt with captured output.
- A merged consensus PRD.
- A dashboard coverage plan for each telemetry addition.
- An aq-qa check for each new event type or replay behavior.
- A clear stance on `<think>` handling: capture only when policy allows and never leak hidden chain-of-thought from providers that forbid exposing it.

Specific caution:
- Adding `thought` and `planning` to `EVENT_TYPES` is not enough. The schema, producers, dashboard, privacy/redaction behavior, and tests must all agree.

## Tokenomics PRD Specific Requirements

Tokenomics parity must include measurement before optimization:
- prompt tokens,
- completion tokens,
- tool-output tokens,
- accepted artifact tokens,
- rework tokens,
- duplicate context ratio,
- elapsed time,
- retry/failback counts,
- useful finding count,
- false-positive rate.

KV-cache sharing is research-only until llama.cpp support, memory cost, correctness, and invalidation are proven locally.

## Required Handoff Prompt For Each Model

Use this prompt skeleton:

```
You are one flat model-team in NixOS-Dev-Quick-Deploy.

Shared brief: <path>
Protocol: .agents/prompts/FLAT_MODEL_TEAM_PRD_PROTOCOL.md

Form the expert roster needed for this PRD. Write your independent proposal first.
Do not implement code. Do not modify WORKFLOW-CANON.

Output:
1. Team roster.
2. Current-state findings with file refs.
3. Proposed PRD/plan.
4. Slice backlog.
5. Validation matrix.
6. Risks/disagreements.

Save proposal to:
.agents/plans/model-proposals/<topic>/<model>-proposal.md
```

## Acceptance Criteria For The Flat Collaboration Layer

- At least two independent model-team proposals exist before synthesis.
- At least two cross-reviews exist before consensus merge.
- Consensus PRD includes decision log and rejected/uncertain items.
- Implementation slices are assigned after consensus, not during first-pass PRD writing.
- No model reviews its own implementation slice.
- Tokenomics and observability slices include dashboard and aq-qa gates.
- All model outputs are traceable to proposal/review/synthesis artifacts.
