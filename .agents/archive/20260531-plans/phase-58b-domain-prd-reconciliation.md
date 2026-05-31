# Phase 58B.0 — Domain PRD Reconciliation Before Acceptance

## Objective

Reconcile the six domain PRDs with the implemented system state before Codex issues final acceptance. The domains were implemented faster than their PRDs were refreshed, leaving stale status labels, superseded package names, and ambiguous lifecycle criteria.

## Findings driving this slice

1. All six domain PRDs still say `Status: Proposed` although the registry and handoff report `implemented`.
2. `mobile-web` still references `nodePackages.lighthouse` even though nixpkgs 25.11 no longer exposes it and the implemented shell uses an on-demand npm hint.
3. `gis-systems` still references standalone `pkgs.postgis`; the implemented shell uses `spatialite-tools`, with PostGIS available via `postgresqlPackages.postgis` for service config.
4. Some PRDs define AIDB seeding as an `implemented` criterion while the latest team handoff says namespace seeding is still pending; the implementation/validation boundary must be clarified before promotion.
5. Several tool-availability sections still describe tools as unprovisioned even though the dev shells now exist and were validated.

## Scope lock

### In scope
- Correct stale status and implementation notes in the six PRDs.
- Correct superseded package/tool references.
- Clarify that AIDB seeding is required before `validated`/promotion when it has not yet happened, rather than pretending it is already done.
- Preserve the accepted domain intent, safety boundaries, and open future slices.

### Out of scope
- New domain features.
- AIDB seeding itself.
- Lifecycle promotion beyond `implemented`.

## Acceptance criteria

1. Each domain PRD reflects current implemented state truthfully.
2. Package/tool references match the actual implemented shells.
3. No PRD claims AIDB seeding is complete when it is still pending.
4. Codex can issue a review verdict grounded in current evidence rather than stale docs.
