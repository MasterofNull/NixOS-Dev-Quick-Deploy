# Portfolio Classification and Tracking PRD

## Objective

Make every plan directory individually classifiable and visible in the portfolio, and define authoritative routes for its child goals, slices, tasks, and operational actions without duplicating projected status.

## Contract

- Each plan has an explicit `classification` and `tracking_route` declaration with evidence and optional parent reference.
- The portfolio index displays these fields and reports missing or invalid declarations as `unclassified`; it never infers classifications from names or recency.
- Durable-plan goals, slices, and tasks remain authored in that plan's `tracker.json`; status remains projected from evidence.
- Reviews, decisions, collaboration events, lifecycle decisions, and execution actions remain in their current authoritative registries and are linked by stable plan/task identifiers where supported.
- Lifecycle and progress remain separate. No status, lifecycle, or completion value is backfilled by this work.

## Scope and acceptance

- Extend `aq-plans-index` with validated per-plan classification metadata and portfolio counts by classification and tracking route.
- Render classification and route in JSON and HTML; malformed declarations fail visibly as unclassified with an issue detail.
- Add focused tests for valid, missing, malformed metadata, counts, and rendering.
- Inventory all existing plan directories and classify only from explicit evidence in their primary records; leave unresolved cases visible with a reason and do not invent type, owner, status, or completion.
- Update the development map with the taxonomy and source-of-truth routing for plan child items and operational records.
- Preserve unrelated working-tree changes; no retirement, archive, or system activation in this slice.

## Taxonomy

`program`, `durable_plan`, `review`, `decision`, `baseline`, `inventory`, `coordination`, `record`, or `unclassified`. Tracking routes identify the authoritative source, such as `aq-refactor-status`, `tracker.json`, collaboration round/event records, `.plan-lifecycle.json`, or a named domain registry.
