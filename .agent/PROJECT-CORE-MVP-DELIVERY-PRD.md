# Core AQ-OS MVP delivery

Owner direction: 2026-09-27. Prioritize working core agent, agentic, and system
features using the program tracker and existing approved plans. Antigravity/Gemini
owns the approval control plane. Security/containment activation is deferred until
that work lands and the subsequent activation decision; this work does not disable
existing protections or activate the deferred layer.

## Delivery procedure

1. Design: domain expert teams examine requirements, implementation, operations,
   UX, risks, and measurable acceptance criteria. Synthesize disagreements once
   into a frozen PRD/plan and named deferred questions.
2. Build: execute the frozen plan quickly with bounded ownership, focused tests,
   live integration checks, truthful dashboard telemetry, and atomic commits.
   Do not repeat full debate or seek per-slice consensus for ordinary fixes.
   Reopen only the affected decision for material scope change or a critical defect.
3. MVP audit: after an end-to-end demonstrable MVP, restore full independent expert
   scrutiny and cross-model consensus. Produce one consolidated defect list and
   bounded repairs; distinguish working MVP from accepted release.

## Current bounded work

- Reconcile tracker projections with actual source, service behavior, and evidence.
- Audit recent workspace/session/agent tooling; repair reproduced defects.
- Fix historical-session sweeps replacing active recovery context. Reporting must
  not imply that gzip archiving resets a live model context.
- Publish this delivery procedure through canonical agent instruction projection.
- Preserve parallel ACP edits, existing staged work, and historical review evidence.

## Acceptance and validation

- A documented core MVP scope maps to tracker items and end-to-end workflows.
- Session diagnostics cannot overwrite the current objective or remove live session
  files; dry-run performs no writes; regression tests use temporary fixture homes.
- Canonical delivery guidance reaches all agent projections without deleting peer edits.
- Core changes have focused tests and live checks where applicable; unavailable or
  deferred behavior is reported explicitly, never upgraded to operational by a label.
- Outstanding findings have owners/next actions; security activation remains deferred.

## Rollback and scope

Use ordinary follow-up commits to revert a bounded change when needed; preserve
session originals and peer edits. No new model, dependency, security key, containment
policy, provider login, or unrelated feature is required by this plan.
