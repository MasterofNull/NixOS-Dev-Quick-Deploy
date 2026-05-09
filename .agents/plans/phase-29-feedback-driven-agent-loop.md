# Phase 29 - Feedback-Driven Agent Workflow Loop

## Objective
- Turn local-agent feedback into a repeatable harness loop: PRD, plan, memory checkpoint, execution, validation, and commit.

## Scope Lock
- In scope:
  - Add a repo-native workflow tool for translating agent feedback into actionable slices.
  - Capture a PRD and bounded slice plan for the feedback themes already surfaced by the local agent.
  - Reuse existing harness primitives for context bootstrap, memory checkpointing, QA, and commit discipline.
- Out of scope:
  - Replacing workflow orchestration or PRSI.
  - Building a new remote-agent runtime.
  - Solving every context/memory/delegation issue in one pass.
- Constraints:
  - Prefer existing `aq-*` tools and workflow planner outputs over bespoke one-off scripts.
  - Keep the loop compact and evidence-oriented.
  - One reversible slice per commit.

## Context References
- Files to read first:
  - `scripts/ai/aq-context-bootstrap`
  - `scripts/ai/aq-context-manage`
  - `ai-stack/mcp-servers/hybrid-coordinator/workflow/workflow_planning.py`
  - `nix/modules/core/options.nix`
- Docs to read first:
  - `docs/AGENTS.md`
  - `docs/operations/agent-context-bootstrap.md`
  - `docs/development/LOCAL-AGENT-FEEDBACK-EXECUTION-LOOP-PRD-2026-05.md`

## Steps
1. Capture the feedback themes in a PRD with explicit goals, non-goals, and acceptance criteria.
2. Add `scripts/ai/aq-feedback-loop` to package context bootstrap, health gating, memory checkpointing, and validation into one operator-facing loop.
3. Add docs and discovery wiring so the loop is visible in the operator tool catalog.
4. Run focused tests, checkpoint the decision, and commit the slice.

## Validation
- Syntax:
  - `python3 -m py_compile scripts/ai/aq-feedback-loop`
  - `bash -n scripts/testing/check-feedback-loop.sh`
- Tests:
  - `python3 scripts/ai/aq-feedback-loop --task "act on local agent feedback for context injection, health gating, remote task schema, and evidence-first introspection" --format json`
  - `bash scripts/testing/check-feedback-loop.sh`
- Smoke:
  - `python3 scripts/testing/test-local-agent-config.py`
  - `scripts/governance/tier0-validation-gate.sh --pre-commit`

## Evidence
- Files changed:
  - `scripts/ai/aq-feedback-loop`
  - `scripts/testing/check-feedback-loop.sh`
  - `docs/development/LOCAL-AGENT-FEEDBACK-EXECUTION-LOOP-PRD-2026-05.md`
  - `docs/operations/agent-feedback-loop.md`
  - `nix/modules/roles/ai-stack.nix`
- Commands run:
  - `scripts/ai/aq-hints ...`
  - `scripts/ai/aq-context-bootstrap ...`
  - `curl -sS -H 'Content-Type: application/json' -X POST http://127.0.0.1:8003/workflow/plan ...`
- Output snippets:
  - workflow planner recommended `context-offload`
  - hints reported low memory recall usage and local-first retrieval pressure

## Rollback
- Remove `scripts/ai/aq-feedback-loop` and its test/doc wiring.
- Remove the wrapper/discovery entries from `nix/modules/roles/ai-stack.nix`.
- Revert the PRD/plan artifacts if the workflow direction changes.
