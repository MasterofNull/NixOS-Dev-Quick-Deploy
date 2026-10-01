# Development Plans

Status: Active
Owner: AI Stack Maintainers
Last Updated: 2026-10-01

This directory contains durable implementation plans and some historical or operational records. Use the [system and software development map](../../docs/architecture/development-map.md) for the canonical source-of-truth boundaries, lifecycle, and workflow.

## Start here

- Portfolio and lifecycle view: `aq-plans-index`
- A plan’s projected tasks and dependencies: `aq-pm-tracker <plan>`
- AQ-OS program rollup: `aq-refactor-status`
- Workflow and tracker policy: `.agent/WORKFLOW-CANON.md`
- Document retention and archival: `docs/operations/document-lifecycle-hygiene.md`
- Agent behavior parity index: `docs/architecture/agent-behavior-parity-index.md`

Historical plans are evidence, not default instructions.

Use `--help` on the installed commands for supported output modes. The generated views are projections; this README and plan prose do not maintain completion percentages or current status.

## What belongs here

Put durable, owned implementation work in a plan directory with a stable objective, scope, dependencies, validation goals, and completion condition. Follow the workflow contract for its editorial `tracker.json`; projected progress is derived from evidence.

Keep short-lived coordination, handoffs, reviews, and consensus-round records in their established operational locations. Where an existing record lives under this tree, do not treat its location alone as evidence that it is an active project. Link operational evidence to the durable plan it supports.

## Lifecycle and records

Use `.plan-lifecycle.json` for explicit `active`, `complete`, `superseded`, or `retired` decisions. A superseded record names its replacement; a retired record states why work stopped. Preserve plans and their evidence according to the [document lifecycle policy](../../docs/operations/document-lifecycle-hygiene.md). Age alone does not establish that work is dormant or obsolete.

Before bulk status or lifecycle changes, reconcile each candidate against its plan, tracker, lifecycle evidence, recent work, and owner. Perform that reconciliation as a separately reviewable slice.
