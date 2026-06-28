# Plan - GIS Systems

**PRD:** `.agent/PROJECT-GIS-SYSTEMS-PRD.md`
**Status:** Baseline implemented
**Last updated:** 2026-06-28

## Scope

Activate GIS guidance for CRS validation, vector/raster transformation, tile generation, and public geodata ingestion.

## Implementation Slices

1. Domain instruction anchor
   - Implemented: `.agent/GIS-SYSTEMS-INSTRUCTIONS.md`

2. Lifecycle registry entry
   - Implemented: `gis-systems` in `config/capability-lifecycle-registry.json`

3. Safety and CRS boundary
   - Implemented in PRD and domain instructions: default public CRS is EPSG:4326, and sensitive geolocation workflows require refusal or authorized-scope review.

## Validation

- Focused CI: `gis-systems domain baseline artifact presence check`
- `AQ_QA_SKIP_REPORT_BACKED_CHECKS=1 scripts/governance/tier0-validation-gate.sh --pre-commit`

## Remaining Work

- Add deterministic GeoJSON/CRS fixture tests before introducing new geospatial automation services.
- Add dashboard visibility if a GIS ingestion or tile-generation service is added.
