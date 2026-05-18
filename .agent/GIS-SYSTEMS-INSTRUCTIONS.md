# GIS-Systems Domain — Agent Instruction Payload

**Domain tag:** `gis-systems`
**State:** proposed (2026-05-18)
**Upstream authority:** `.agent/PROJECT-GIS-SYSTEMS-PRD.md`, `docs/architecture/capability-lifecycle.md`
**Registry ID:** `gis-systems` in `config/capability-lifecycle-registry.json`

---

## Domain Scope

Applies when performing: geospatial data transformation (GDAL/OGR), spatial analysis (GeoPandas, PostGIS, SpatiaLite), CRS validation, raster/tile generation, Natural Earth/OSM data ingestion, QGIS headless processing, or GIS knowledge retrieval from AIDB (`gis-systems-patterns` namespace).

---

## CRS Discipline Rules (mandatory — non-negotiable)

1. **Always declare CRS** on any spatial dataset before storing, transforming, or joining
2. **Canonical project CRS:** EPSG:4326 (WGS84) unless explicitly overridden with documented justification
3. **Validate CRS first:** `ogrinfo -al -so <file>` before any spatial operation
4. **Never assume CRS** from file naming, context, or LLM output — always read from metadata
5. **Document CRS** in any AIDB write: include `"crs": "EPSG:XXXX"` in metadata

---

## Eligible Task Classes

| Task class | Eligible agents | Notes |
|---|---|---|
| CRS lookup from AIDB / EPSG registry | Qwen (Tier A) | Pure retrieval |
| GDAL format conversion (single file) | Qwen (Tier A) | Deterministic; bounded |
| Spatial join / overlay (≤2 datasets, known CRS) | Qwen (Tier B) | Review-gated; validate CRS first |
| Spatial analysis & modeling | Claude/Gemini | `remote-reasoning`; Gemini review gate |
| Critical infrastructure geolocation | Human-gated | Requires explicit user authorization + legal docs |
| Large-scale surveillance automation | Forbidden (autonomous) | Authorization + legal required |

---

## Tool Preferences

1. **ALWAYS validate CRS first:** `ogrinfo -al -so <file>` before any operation
2. `nix develop .#gis` — domain dev shell (not yet provisioned; gis-systems.1)
3. `ogr2ogr -t_srs EPSG:4326 out.geojson in.shp` — canonical CRS transform
4. `python3 -c "import geopandas; print('ok')"` — GeoPandas health check
5. `spatialite` — local SQLite-based spatial queries (no PostGIS required)
6. `qgis --nologo --code <script.py>` — headless QGIS processing
7. `scripts/governance/tier0-validation-gate.sh --pre-commit` — mandatory before commit

**Forbidden:** CRS-unspecified spatial operations; critical infrastructure geolocation without authorization; `pip install gdal` (Python GDAL bindings must match system libgdal — Nix dev shell only).

---

## AIDB Namespace Binding

**Namespace:** `gis-systems-patterns`

- Read: query `crs_discipline_rules` before any CRS transform; query `postgis_optimization_patterns` before spatial joins.
- Write: after resolving spatial challenge. Include `"crs"`, `"data_source"`, `"epsg_code"` in metadata.

---

## Review Requirements

| Work category | Gate required |
|---|---|
| Spatial analysis & modeling | Gemini review gate |
| Domain dev shell (flake.nix) | Gemini review gate |
| Critical infrastructure geolocation (if authorized) | Gemini review gate + user confirm |
| CRS transform (single file, known CRS) | No gate required |
| AIDB pattern lookup | No gate required |

---

## Routing Preference

| Query type | Profile |
|---|---|
| Spatial analysis & modeling | `remote-reasoning` |
| Format conversion & CLI mapping | `local-tool-calling` |
| Geospatial concepts & CRS definitions | `default` |
