# Plan Supersession / Retirement Map (proposed)

Owner ask 2026-07-25: retire/supersede past plans the AQ-OS refactor replaces. Retirement =
**mark + keep** (Rule 12 NO DELETE): a `.plan-lifecycle.json` in the plan dir sets
`lifecycle: superseded|retired|complete|active` + `superseded_by`; `aq-plans-index` reads it
and shows those plans struck-through under the Superseded/Complete filters. Nothing is deleted.

Retirement is a judgment call, so only **high-confidence** rows are applied now; the rest are
**proposed** for your confirmation (or a delegated per-dir analysis pass when the Claude lane
returns).

## APPLIED — superseded (high confidence, hard evidence)
| Plan | Superseded by | Evidence |
|---|---|---|
| `aqos-v1` | `unified-program` | UNIFIED-PROGRAM-PLAN folds aqos-v1 Beat-0 + synthesis + VF-0 into one round |
| `program-progress-tracker` | `aqos-refactor-status` + `aq-plans-index` | hand-tracker replaced by ground-truth projectors |
| `f3-capability-otel` | `aqos-foundation-c` | Foundation C design explicitly absorbs F3 (CapabilityLease+OTel+signed-A2A) |

## PROPOSED — superseded (medium confidence — CONFIRM)
Absorbed into the unified program / foundations; the standalone brief is no longer the plan of
record.
| Plan | Proposed superseded_by | Rationale |
|---|---|---|
| `factory-critique` | `unified-program` | critique corpus that fed the unified program synthesis |
| `f1-plan-consensus`, `f1-round-state-machine` | `agent-agnostic-factory` / F1 shipped | F1 round-state machine landed (aq-collab-round); briefs absorbed |
| `f2-plan-consensus`, `f2-session-mode`, `f2-local-scheduler` | `aqos-foundation-*` / Product D | F2 Phase-A done, F2.5 wiring tracked under Product D |
| `plan-consensus`, `prd-consensus` | `.agent/WORKFLOW-CANON.md` flat-collab workflow | early consensus rounds now canonical workflow, not standalone plans |

## PROPOSED — complete (shipped/finished, not superseded — CONFIRM)
| Plan | Rationale |
|---|---|
| `local-inference-l2b-a` | L2B-A landed |
(others likely, pending the review pass below)

## ACTIVE — keep (current refactor)
`unified-program`, `aqos-foundation-c`, `aqos-foundation-b2`, `aqos-foundation-b3`,
`aqos-refoundation-cycle0` (Foundation A), `aqos-refactor-status`, `pm-tracker-standard`,
`agent-agnostic-factory`, `verified-factory` (Track V), `infra-fixes`, `local-embed-context`
(Slice 2b in revision), `local-inference-b1-parity`, `local-inference-l2b-b`.

## REVIEW-NEEDED — cannot classify without reading each dir (delegated pass on lane-return)
`agent-connection-reliability`, `agent-ops-traceability-r0m`, `antigravity-lane-restoration`,
`antigravity-routing-honesty-accept`, `c05-tiered-policy-architecture`,
`capability-intake-security`, `delegate-codex-quota-precheck`, `dispatch-integration-review`,
`generic-flake-baseline`, `lean-ctx-workspace-identity`, `local-delegation-reliability-r0`,
`multi-agent-edge-harness`, `qa-provider-probe-reliability`, `reentry-intent`, `rsi-readiness`,
`security-validation-reliability`, `stream-auth-rereview`, `usability-parity`,
`usability-parity-v2`, `b1-parity-design-review`, `phase-173`, `tiered-agent-memory`.
Each: read its status doc + last commit → propose complete / superseded / active, apply after
owner confirm. Good delegated task (cheap implementer) when the lane returns.

## How to apply a decision
`echo '{"lifecycle":"superseded","superseded_by":"<id>","date":"<d>","reason":"..."}' >
.agents/plans/<plan>/.plan-lifecycle.json` (or lifecycle `complete`/`retired`), then
`aq-plans-index --html` regenerates the dashboard. Reversible: delete the marker to restore.
