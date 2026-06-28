# PRD - GIS Systems Domain Activation

**Domain tag:** `gis-systems`
**Status:** Active foundation, sensitive geolocation approval-gated
**Last updated:** 2026-06-28

## Objective

Provide agents with safe geospatial workflows for CRS validation, vector/raster transformation, tile generation, and public geodata ingestion.

## Current Scope

- GeoJSON and CRS validation.
- Spatial transforms with canonical CRS handling.
- Raster/tile generation and GDAL-style processing.
- Public Natural Earth/OSM-style data ingestion guidance.
- Retrieval namespace: `gis-systems-patterns`.

## Safety Boundary

- Critical infrastructure geolocation, individual tracking, sensitive facility targeting, and doxxing workflows require refusal or explicit authorized-scope review.
- Canonical public default CRS is EPSG:4326 unless a workflow declares another CRS.

## Acceptance Criteria

- `gis-systems` exists in `config/capability-lifecycle-registry.json`.
- `.agent/GIS-SYSTEMS-INSTRUCTIONS.md` is present.
- CRS assumptions are explicit in generated datasets, reports, and visualizations.
