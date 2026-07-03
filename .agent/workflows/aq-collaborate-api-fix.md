# Slice record: aq-collaborate plan/synthesize API fix (2026-07-02)

## Bug (backlog: aq-collaborate-plan-import-error)
`scripts/ai/aq-collaborate` `cmd_plan` and `cmd_synthesize` imported a
non-existent class `CollaborativePlanner`. The module
`lib/l4-coord/agents/collaborative_planning.py` defines `CollaborativePlanning`.
Every `aq-collaborate plan` / `synthesize` invocation crashed at import
(`ImportError`), leaving the A2A plan/synthesize commands dead — an earlier
session had to fall back to `PULSE.log` broadcast for coordination.

## Root cause
Call sites written against an assumed API that never existed. Beyond the class
name, three downstream mismatches:

| Call site assumption | Real API |
|----------------------|----------|
| `create_plan(objective)` async | `create_plan(task_id, team_id, mode=) -> str` sync |
| `await planner.close()` | no such method |
| `synthesized.synthesized_phases` / `phase.title` | `.phases` (PlanPhase) / `.name` |
| `agent_capabilities: Dict[str, float]` | `Dict[str, List[str]]` (capability lists) |

## Fix
- Class name → `CollaborativePlanning` in both call sites (+ import).
- `create_plan(task_id=collab_id, team_id='collab')` synchronous + `_save_state()`.
- Dropped the phantom `await planner.close()`.
- Corrected synth output attrs `.phases` / `.name`; capability mock → `List[str]`.

## Validation (live)
- `aq-collaborate plan test-collab-001 "..."` → `✓ Plan created: plan-test-collab-001-<ts>` (was ImportError).
- `aq-collaborate synthesize <id>` → no crash; accurate "Plan not found" degrade.

## Known follow-up (separate slice — aq-collaborate-plan-persistence)
`active_plans` is in-memory per process; `create_plan` does not persist plans to
disk (only `plan_history` persists). So cross-invocation `synthesize` can never
find a plan created in a prior process. Surfaced explicitly in the not-found
message. Requires plan-state serialization design — out of scope for this
import-correctness slice. Logged in memory rather than `issues-backlog.md`
(the backlog file is held uncommitted by the concurrent Codex Rust-rewrite
session; avoiding a shared-index collision).
