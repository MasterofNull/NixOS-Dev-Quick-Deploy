# System and Software Development Map

This page is the navigation map for AQ-OS and harness development. Workflow policy remains in [the canonical workflow contract](../../.agent/WORKFLOW-CANON.md); this page explains where work is planned, how its state is represented, and which generated views to use.

## Source of truth by concern

| Concern | Authoritative source | How to use it |
|---|---|---|
| Agent workflow and mandatory gates | `.agent/WORKFLOW-CANON.md` | Follow the canonical task lifecycle and behavioral rules. |
| Plan intent, scope, dependencies, validation goals, detection signals | `.agents/plans/<plan>/tracker.json` plus its linked plan/PRD | Edit editorial scope when the plan changes; never hand-edit projected progress. |
| Explicit lifecycle decision | `.agents/plans/<plan>/.plan-lifecycle.json` | Record active, complete, superseded, or retired only with supporting rationale and links. |
| Portfolio of plans | `aq-plans-index` | Find plans across active and historical work and inspect projected lifecycle/progress. |
| One plan’s progress | `aq-pm-tracker <plan>` | Inspect its projected tasks, dependencies, and validation goals. |
| AQ-OS refactor/program rollup | `aq-refactor-status` | Inspect the program-level phase and capability view. |
| AQ-OS requirements and queued slices | `.agents/plans/aqos-requirements-inventory/tracker.json` | Track requirement-level scope, priority, dependencies, and validation goals; currently includes `req-guest-init-evaluation`. |
| Current collaboration, handoff, and review activity | `.agent/collaboration/` and `.agents/delegation/` | Treat as operational records with their own event/round sources, not as durable plan status. |
| Classification and authoritative tracking route | `.agents/plans/<plan>/.plan-classification.json` | Declare type, tracking route, and evidence; unresolved or invalid declarations stay in the visible classification queue. |

The manifest is editorial input; the projector’s result is the progress view. Git evidence, lifecycle records, activation evidence, claims, and blockers are interpreted by the projectors according to their contracts. Do not duplicate projected status in plan headers, dashboards, or another manually maintained index.

## Coverage and completeness

`aq-pm-tracker --all-json` rolls up only plans with valid tracker manifests. A healthy projector result means those inputs were read successfully; it does not establish that every indexed plan is represented. Compare its manifest count with `aq-plans-index --json` and review indexed `active` plans where `has_tracker` is false. Classify each as durable implementation work, a transient/operational record, or a lifecycle candidate before changing it. Create trackers for confirmed durable active plans; retain operational evidence in its owning plan or collaboration record. Never treat the aggregate percentage as whole-program completion until that coverage reconciliation is complete. `aq-refactor-status` remains the AQ-OS-specific rollup and has its own scope.

For each indexed directory, `.plan-classification.json` records a taxonomy value, tracking route, and evidence. `aq-plans-index --json` reports `by_classification`, `by_tracking_route`, and `unclassified_count`; its HTML view offers an Unclassified filter and coverage card. Missing, malformed, or weakly evidenced declarations must remain unresolved. Classification does not alter lifecycle or projected progress. Durable plans track child goals, slices, and tasks in `tracker.json`; operational actions stay in their owning registries and link to stable plan/task IDs where supported.

### Child-work routing (source of truth by record type)

| Record type | Child goals, slices, tasks, actions live in | Notes |
|---|---|---|
| `durable_plan`, `inventory` | the plan's `tracker.json` (editorial); status projected by `aq-pm-tracker` | Never copy status/percent into prose, dashboards, or another index. |
| `program` | the named projector (`aq-refactor-status` and `config/refactor-milestones.json`) | AQ-OS requirement slices stay in `aqos-requirements-inventory/tracker.json`; the two views are separate measures. |
| `coordination` (collaboration rounds) | the plan's `round.json` plus per-agent contribution files and `AGGREGATE.md` | Operational record; not promoted to a durable plan to raise coverage. |
| `review`, `decision`, `baseline`, `record` | the registry that owns them (review receipts, acceptance/authorization records, `.plan-lifecycle.json` for lifecycle decisions) | Link by stable plan/task ID where the registry supports it. |

Coverage checks: `aq-plans-index` reports a declared file route (`tracker.json`, `round.json`, `.plan-lifecycle.json`) whose file is absent as unresolved, so a route cannot point at a non-existent source. The dashboard Program tab shows classified vs unresolved totals and an "Unresolved only" filter; each unresolved record carries a specific reason (`unresolved: ...`) rather than being guessed.

## Find the current state

Run the portfolio index first, then open the linked plan and its tracker. For AQ-OS phase-level progress, use `aq-refactor-status --machine`; for per-plan editorial goals and projected task evidence, use `aq-pm-tracker <plan>` or the aggregate `aq-pm-tracker --all-json`. Machine-readable views are the operational reports; the sources named above remain authoritative.

The directory [plans README](../../.agents/plans/README.md) is the short routing guide. It is not a separate status source. `tracker.json` records planned work and detection signals; current completion must be derived from the projector output and supporting evidence.

## Durable plans and operational records

A durable plan is an owned body of implementation work with a stable objective, bounded scope, dependencies, validation goals, and completion/retirement condition. It belongs in `.agents/plans/<plan>/` and follows the active-plan tracker policy in the workflow contract.

Reviews, consensus rounds, candidate slates, handoffs, and coordination sessions are operational evidence. Keep them in their established collaboration or review locations. A record under `.agents/plans/` is not automatically an active project: classify it from its purpose and lifecycle evidence, not its directory name alone. When an operational record has a durable implementation outcome, link that outcome to its owning plan instead of turning each round into another project tracker.

## Lifecycle

- **Active:** work is authorized and has a current objective. Maintain its editorial plan and tracker; progress remains projected.
- **Complete:** acceptance evidence shows the objective is done. Preserve the record and its evidence.
- **Superseded:** a named replacement carries the continuing objective. Record the replacement and reason.
- **Retired:** work is intentionally stopped without a replacement. Record the reason and preserve the record.

Do not infer that a plan is dormant or obsolete from age alone. Before bulk reconciliation, inspect the plan, tracker, lifecycle record, recent commits, and collaboration ownership; then make lifecycle changes in a separate reviewable slice. Archive only under the document lifecycle policy, retaining provenance and links.

## Creating or changing work

1. Decide whether the work is a durable plan or a transient operational record.
2. For durable work, create a plan/PRD with an objective, scope, dependencies, validation goals, and retirement condition; create its `tracker.json` with detection signals.
3. Record lifecycle decisions in `.plan-lifecycle.json`; keep status/progress out of hand-maintained prose.
4. Update the tracker’s editorial goals when scope changes, then inspect the generated projection to confirm what the evidence supports.
5. Link collaboration/review evidence to the plan. Keep one logical objective per durable plan and split independent objectives rather than accumulating unrelated slices.

## Planned organization work

The portfolio classification implementation and reconciliation queue are tracked in [its PRD](../../.agents/plans/portfolio-classification/PRD.md) and [tracker](../../.agents/plans/portfolio-classification/tracker.json). On 2026-10-08, `aq-plans-index --json` reported 113 indexed records (93 active, 4 dormant, 14 superseded, 2 retired): 53 classified from explicit primary-record evidence (14 durable plans, 4 inventories, 34 collaboration rounds, 1 program) and 60 unresolved, each carrying a recorded reason. These are separate gaps: classification must be based on source evidence, and trackers should be added only for confirmed durable plans. Review rounds and acceptance records must not be promoted to durable projects just to increase coverage. Re-run the machine view for current counts instead of treating this dated snapshot as live status.

The AQ-OS projection remains a separate view: 12 tracks are done or active, with two high blockers currently recorded (local dispatch contention and the built-in-tool lease gap). The guest init objective is captured both as requirement `req-guest-init-evaluation` in the requirements inventory and as milestone `PID1` in `config/refactor-milestones.json`; `aq-refactor-status --machine` currently reports it as not started at 0%. The requirements inventory reports the slice at DESIGNED (10%), reflecting definition of scope; that design tier and the program milestone's execution progress are distinct measures. Its scope is isolated Flake-built VM/container evaluation of publicly supported PID 1 options while retaining host systemd. No candidate is selected and no host PID 1 switch is authorized. Use the live projector for current detail; do not copy projected percentages into this map. Existing dormant, superseded, and retired lifecycle decisions remain in force. Archive or change them only when provenance and the lifecycle policy support the specific action.
