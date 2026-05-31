# Phase 58A.6 — Capability Lifecycle Schema

## Objective

Define the canonical state machine and evidence requirements for harness capabilities, and create a machine-readable registry that tracks the lifecycle state of all active agent-facing capabilities.

## Outputs

- `docs/architecture/capability-lifecycle.md` — state machine, evidence table, registry shape, operator workflow
- `config/capability-lifecycle-registry.json` — registry seed with 8 capabilities from current system
- `.agents/plans/phase-58a-capability-lifecycle.md` — this slice plan

## Acceptance criteria per team plan

1. States present: proposed, implemented, validated, candidate, promoted, default, superseded, retired — all 7 plus blocked. ✓
2. Evidence requirements defined per state. ✓
3. Runtime / operator / validation / rollback surfaces documented. ✓
4. Registry shape defined with domain/state/evidence/blocked/superseded fields. ✓
5. Domain activation template (58A.7) hook noted. ✓

## Registry seed entries

| ID | State |
|---|---|
| `local-inference-qwen3-35b` | default |
| `rocm-promotion` | blocked |
| `hybrid-coordinator-control-plane` | default |
| `brokered-memory-path` | promoted |
| `route-alias-resolver` | default |
| `intent-classifier-routing` | validated |
| `workflow-executor-dag` | promoted |
| `edge-tier-local-coding` | proposed (blocked) |

## Status

ACCEPTED — 2026-05-18 (Claude authored, Codex final acceptance complete)
