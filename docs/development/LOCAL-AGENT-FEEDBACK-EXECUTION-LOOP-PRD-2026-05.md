# Local Agent Feedback Execution Loop PRD

Status: Active
Owner: AI Stack Maintainers
Last Updated: 2026-05-09

## Problem

The local agent is producing useful qualitative feedback, but that feedback is not
consistently converted into a bounded development loop. The harness has the right
primitives already: context bootstrap, hints, memory checkpointing, QA, planning,
and commit discipline. The gap is packaging and operator workflow.

The latest feedback clustered around four recurring issues:

1. continuation work starts without a compact recalled context packet
2. multi-step execution does not foreground a health gate strongly enough
3. remote delegation lacks a compact, obvious task contract at the workflow level
4. introspection responses still drift into plausible-but-unverified claims

## Goals

1. Give operators and agents a single repo-native loop that turns feedback into:
   - PRD
   - plan
   - memory checkpoint
   - execution
   - validation
   - commit
2. Make the loop reuse existing harness tooling instead of introducing a second orchestration path.
3. Keep the first slice lightweight enough to use during normal repo work.

## Non-Goals

1. Replace PRSI, workflow orchestration, or the hybrid coordinator.
2. Solve every memory, routing, or remote-agent issue in one batch.
3. Add a new long-running service just for feedback processing.

## Users

- human operators driving the repo from terminal or editor
- local harness agents that need a compact execution contract
- remote lanes that need a clearer task envelope and validation target

## Proposed Solution

Add a small operator-facing tool, `aq-feedback-loop`, that translates agent or operator feedback into a bounded execution contract using existing harness tools. The tool should:

1. bootstrap context with `aq-context-bootstrap`
2. recommend the first QA and report commands
3. recommend PRD and plan artifact paths
4. recommend a memory checkpoint command
5. expose the main workstreams implied by the feedback
6. expose validation and commit steps explicitly

## Workstreams

### 1. Context Injection Preflight

- Start long-running or continuation tasks with context bootstrap and memory recall before broad exploration.
- Acceptance:
  - the loop recommends `aq-context-bootstrap`
  - the loop recommends `aq-context-manage checkpoint`
  - the loop recommends the `long-running-context-offload` blueprint

### 2. Health-Gated Execution

- Make `aq-qa 0 --json` explicit before runtime-heavy or multi-step work.
- Acceptance:
  - the loop prints `aq-qa 0 --json`
  - the loop keeps validation separate from execution

### 3. Remote Task Schema

- Turn “use a JSON schema for remote tasks” into an explicit workstream with repo references and acceptance criteria.
- Acceptance:
  - the loop references the orchestration/session handlers and harness SDK
  - the plan names objective, constraints, output, timeout, and validation as the contract fields

### 4. Evidence-First Introspection

- Keep the introspection hardening work visible as an active stream, not a one-off prompt patch.
- Acceptance:
  - the loop points back to the prompt contract files and tests
  - the plan keeps `observed_signals`, `inferred_constraints`, `evidence_sources`, and `unknowns_or_next_checks`

## Success Criteria

1. A user can run one command and get a compact execution loop for feedback-driven work.
2. The loop emits explicit artifact paths, commands, validation steps, and commit guidance.
3. The loop is documented and test-covered.
4. The loop can be checkpointed into harness memory during execution.

## Risks

1. The loop becomes too generic and duplicates what `aq-context-bootstrap` already does.
2. It becomes another documentation artifact without being easy to run.
3. It hides real implementation work under process language.

## Mitigations

1. Build directly on top of `aq-context-bootstrap` instead of replacing it.
2. Keep the output short and command-driven.
3. Tie the loop to a test and commit workflow so it stays executable.

## Validation

- `python3 scripts/ai/aq-feedback-loop --task "..."`
- `bash scripts/testing/check-feedback-loop.sh`
- `scripts/governance/tier0-validation-gate.sh --pre-commit`
