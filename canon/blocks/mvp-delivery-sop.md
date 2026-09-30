## Design, Build, and MVP Audit (owner directive 2026-09-27)

This procedure governs delivery cadence for every agent and supersedes older
requirements for repeated full expert rounds during ordinary implementation.
The eight workflow steps remain; the depth of ceremony depends on the phase.

### Design and freeze

Use full, independent domain-expert teams across available model lanes for the
PRD and plan. Cover architecture, implementation, UX, operations, measurement,
failure modes, and security implications. Give teams the same evidence and
criteria; consolidate disagreements into one decision record. Freeze the MVP
scope, dependency contracts, owners, acceptance tests, rollout/rollback limits,
and deferred questions as PLAN_READY or PLAN_READY_WITH_FOLLOWUPS. Existing
approved plans are reused, not redrafted solely to satisfy this procedure.
Record unavailable lanes honestly; never manufacture their consensus.

### Build the working MVP

Once the plan is frozen, prioritize implementation and end-to-end operation.
Use bounded slices, the cheapest eligible implementers, and focused regression,
integration, and live checks. Fix ordinary defects directly within the frozen
scope. Do not require a fresh full expert round, debate, or all-model consensus
for each implementation slice, fix, or commit. Collect non-blocking critique for
the MVP audit instead of repeatedly reopening accepted design decisions.

Keep atomic commits, evidence, service/dashboard coverage, and required automated
gates. Preserve existing protections and explicit activation boundaries. A
specific high-risk change may require targeted independent review; that is not
a reason to restart the entire ceremony. Reopen only the affected decision for
material scope/contract changes or critical correctness, data-loss, authority,
or security defects. MVP implementation is not automatically release acceptance.

Declare a working MVP only after the frozen end-to-end user journeys succeed
with real dependencies, visible progress and terminal outcomes, and reproducible
evidence. Source presence, green syntax checks, staged files, and simulated
success do not prove operational readiness. Record limitations explicitly.

### Full MVP audit and acceptance

At the working MVP boundary, restore full expert scrutiny: independent code and
runtime review, adversarial and failure testing, operator UX, performance,
observability, and cross-model consensus. Review one exact integrated subject
against the frozen criteria. Consolidate findings into one prioritized list;
repair blockers and validate affected paths without restarting unrelated debate.
Record real participant verdicts and outstanding concerns. Only that evidence
can support release acceptance; deferred security/containment activation still
requires its own readiness evidence and owner decision.

Track delivery phase, demonstrable journeys, defects, and implementation versus
live readiness separately. Measure time to working MVP and review overhead;
never inflate progress to make the fast-build phase appear complete.
