# Development Map and Plan-Organization PRD

## Objective

Make task organization, plan lifecycle, progress tracking, and AQ-OS/system development discoverable through one SSOT-aligned map. Reuse the existing plan index and tracker projections; do not introduce a second manually maintained status catalog.

## Current problem

`.agents/plans/README.md` is dated 2026-05-25, directs readers to an old parity plan, and requires hand-maintained status/date headers. The current workflow contract instead says progress is projected from ground truth and `aq-plans-index`/`aq-pm-tracker` are the plan and tracker surfaces. The plans tree also contains durable implementation plans alongside reviews, consensus rounds, and short-lived coordination artifacts, with no clear distinction at the entrypoint.

## Scope

- Document the canonical map, authority boundaries, lifecycle, and commands.
- Refresh `.agents/plans/README.md` as a concise routing index into that map.
- Preserve existing plan records and statuses; no mass backfill, retirement, archive, or status edits in this slice.
- Do not change projector behavior or create a competing rollup.

## SSOT decisions

1. `.agent/WORKFLOW-CANON.md` and its canonical behavioral rules define workflow and tracking policy.
2. `.agents/plans/<plan>/tracker.json` is authored editorial scope and detection signals; projected status comes from `aq-pm-tracker` and ground truth.
3. `.plan-lifecycle.json` records explicit lifecycle decisions (active, complete, superseded, retired); it is not a progress field.
4. `aq-plans-index` is the portfolio entrypoint, `aq-pm-tracker` is the per-plan projection, and `aq-refactor-status` is the AQ-OS program rollup.
5. Collaboration rounds, reviews, and transient handoffs are evidence/work records, not automatically durable development plans. Durable work receives a plan directory and tracker when it meets the active-plan policy.

## Acceptance

- A new architecture map names the SSOT sources, their boundaries, the three read surfaces, and the intended lifecycle.
- The plans README routes to the map and removes hand-maintained status metadata and obsolete plan-specific starting guidance.
- No existing plan status, lifecycle declaration, or other agent’s active work is changed.
- `aq-plans-index --json` and `aq-pm-tracker --all-json` still render valid projections; focused plan-index validation passes if available.

## Follow-up (separate slices)

- Inventory and reconcile active versus transient plan directories with owners and evidence.
- Add or repair trackers for confirmed active plans only.
- Retire or archive superseded records using the established lifecycle policy, with provenance preserved.
- Add creation-time scaffolding and gates only after the current projector contracts are verified.
