# Tool Working Set GC PRD

Updated: 2026-05-24T16:00:04Z

## Objective

Reduce local and remote tool/context overhead by selecting a narrow tool working set per request instead of injecting the same static local tool bundle for every local tool-calling turn.

## Problem

Local tool-calling currently defaults to a fixed core set. This keeps the schema smaller than the full registry, but it still injects tools into casual or narrow requests that do not need them. Long tasks also accumulate raw tool observations until the model exhausts its context or tool budget.

## Scope

- Add deterministic intent classification in switchboard from the current user turn.
- Map intent classes to compact built-in tool bundles.
- Preserve explicit caller tool lists, including full-registry `*` behavior.
- Surface telemetry for selected intent and tool bundle.
- Add regression coverage for conversational zero-tool and targeted bundles.

## Out Of Scope

- Full multi-phase workflow executor.
- Cross-turn persistent MCP session GC.
- Dashboard UI card changes.

## Acceptance

- Casual chat can execute through `local-tool-calling` without injected tools.
- Git, search, sys-ops, and harness-analysis prompts receive only their relevant bundle.
- Explicit tool lists still override automatic selection.
- `/health` reports working-set policy metadata.
- Python compile, focused regression, live health, and tier0 validation pass.
