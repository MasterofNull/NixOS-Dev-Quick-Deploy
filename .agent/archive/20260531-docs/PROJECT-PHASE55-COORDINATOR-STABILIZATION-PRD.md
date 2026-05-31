# Project PRD — Phase 55 Coordinator Stabilization

## Objective
Finish the next recovery slice after restoring dashboard trace delivery by removing the remaining Phase 55 startup/schema mismatch without regressing the now-working trace timeline.

## Current state
- Dashboard observatory route is live again.
- Coordinator is healthy and serves `/api/traces`.
- Startup previously logged a non-fatal `memory_superseder` schema mismatch because two similarly named implementations use different table contracts.

## In scope
1. Reconcile the active Phase 55 memory supersession implementation path.
2. Remove the startup warning caused by incompatible schema assumptions.
3. Keep `/memory/supersede*`, drift, crystallization, and trace APIs healthy.
4. Validate with focused tests, live endpoint checks, and Tier 0 gate.

## Out of scope
- Broad redesign of Phase 55 memory architecture.
- New dashboard features.
- Unrelated AppArmor or identity permission cleanup unless needed for this slice.

## Success criteria
- Coordinator starts without the `successor_id` schema warning.
- Trace timeline endpoint still returns live rows through the dashboard proxy.
- Memory supersession HTTP surface responds successfully.
- Python syntax and relevant focused tests pass.
- Slice is committed with handoff notes updated.

## Risks / assumptions
- Two modules named `memory_superseder` exist for different concerns; the safest path is to pick one runtime source of truth rather than force both schemas into one table.
- Any migration must preserve existing data or remain backward compatible with the already-created table.
