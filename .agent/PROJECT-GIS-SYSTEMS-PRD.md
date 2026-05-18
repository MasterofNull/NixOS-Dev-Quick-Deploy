# PRD — gis-systems Domain Activation

**Domain tag:** `gis-systems`
**Status:** Proposed — Phase 58A capability expansion
**Authors:** Claude (orchestrator/architect) · Gemini (research synthesizer)
**Date:** 2026-05-18
**Upstream template:** `docs/architecture/domain-activation-template.md`
**Gemini research:** `.agents/delegation/outputs/gemini-20260518-121439-w2gzy1.log` (Domain C)

---

## Problem Statement

GIS capability is essentially absent from the harness today. Per the master PRD: the harness needs GDAL/OGR, PROJ, PostGIS, GeoPandas, Rasterio, Shapely, QGIS/GRASS references, CRS discipline rules, and geospatial data pipelines (Natural Earth, OSM, elevation data, tile generation, raster/vector processing).

Without a formal domain:
- Agents have no canonical tool order for geospatial work
- CRS (Coordinate Reference System) discipline is undefined — a critical correctness requirement for spatial data
- No AIDB namespace for geospatial knowledge
- No routing preference for spatial reasoning vs CLI-based data transformation
- No dual-use safety boundary for critical infrastructure geolocation data

---

## Goal

Establish `gis-systems` as a first-class capability domain. Initial activation covers:

1. Registering the domain (proposed state)
2. Declaring routing preference and AIDB namespace
3. Authoring the agent instruction surface
4. Wiring a baseline validation hook

Provisioning of the full geospatial Nix dev shell and AIDB seeding are follow-on slices.

**First follow-on slice (per Gemini research):** Geospatial Data Ingest & CRS Validator — a tool that inspects incoming spatial data, validates its CRS, and converts it to the project's canonical CRS standard.

---

## Kernel Objects Touched

| Kernel object | How this domain touches it |
|---|---|
| `intent` | Adds `gis-systems` intent class → `remote-reasoning` for spatial analysis; `local-tool-calling` for GDAL/OGR format conversion |
| `memory-evidence` | CRS rules, PostGIS patterns, raster/tile workflows → AIDB namespace `gis-systems-patterns` |
| `workflow-session` | Spatial data pipelines (ingest → validate CRS → transform → index) map to WorkflowExecutor DAG pattern |

---

## Routing Profile(s)

| Use case | Profile | Notes (Gemini research) |
|---|---|---|
| Spatial analysis & modeling | `remote-reasoning` | Requires understanding of complex geometric relationships |
| Format conversion & CLI mapping | `local-tool-calling` | GDAL/OGR syntax is complex but bounded; fully local |
| Geospatial concepts & CRS definitions | `default` | General GIS terminology; Qwen adequate |

---

## AIDB Namespace

**Namespace:** `gis-systems-patterns`

Seed content per Gemini research:
- `crs_discipline_rules` — EPSG code dictionary and projection transformation logic (WGS84, UTM zones, national grids); canonical CRS for this project = EPSG:4326 (WGS84) unless stated otherwise
- `geospatial_data_index` — Natural Earth, OSM, and NASA data retrieval patterns and sources
- `postgis_optimization_patterns` — Spatial indexing (GIST) and optimized PostGIS query snippets
- `raster_tiling_workflows` — Patterns for generating XYZ/TMS tiles from large GeoTIFFs
- `spatial_test_fixtures` — Known-good WKT/GeoJSON datasets for unit testing spatial operations

---

## Tool Preferences

### Recommended Nix packages (from Gemini research)

| Package | nixpkgs attribute | Purpose |
|---|---|---|
| GDAL | `pkgs.gdal` | Core raster/vector geospatial data library |
| PostGIS | `pkgs.postgis` | Spatial database extension (non-trivial GIS workflows) |
| GeoPandas | `pkgs.python3Packages.geopandas` | High-level Python spatial dataframes |
| QGIS | `pkgs.qgis` | Visual analysis; runs headlessly for processing |
| SpatiaLite | `pkgs.spatialite-tools` | Local file-based GIS via SQLite (low overhead) |

### Tool order

1. `nix develop .#gis` — domain dev shell (provision in gis-systems.1)
2. Validate CRS before any transform: `ogrinfo -al -so <file>` — check CRS declaration
3. `ogr2ogr -t_srs EPSG:4326` — canonical CRS transform (GDAL)
4. `python3 -c "import geopandas"` — GeoPandas health check
5. `qgis --nologo --code <script.py>` — headless QGIS processing (provision in gis-systems.1)
6. `spatialite` — local SQLite-based spatial queries without PostGIS
7. `scripts/governance/tier0-validation-gate.sh --pre-commit` — always before commit

### CRS Discipline Rules (mandatory)

- **Always declare CRS** on any spatial dataset before storing or transforming
- **Canonical project CRS:** EPSG:4326 (WGS84) unless explicitly overridden with documented justification
- **Validate CRS** with `ogrinfo` before spatial join or overlay operations
- **Never assume CRS** from file naming or context — always read from metadata

### Forbidden

- Geolocation of critical infrastructure (power, water, communications) without explicit user authorization and documented legal context
- Large-scale surveillance automation (real-time tracking/telemetry at scale) without authorization
- Storing sensitive geolocation data in AIDB without user approval (privacy risk)
- CRS-unspecified spatial operations (undefined projection = wrong results)
- `pip install gdal` (NixOS-first: Nix dev shell only; GDAL Python bindings must match system libgdal)

---

## Security and Safety Considerations

Per Gemini research — key dual-use concerns:

1. **Critical infrastructure geolocation**: High-fidelity mapping of power, water, communications infrastructure. Treat as approval-gated; require explicit user authorization and legal documentation.
2. **Large-scale surveillance**: Processing real-time tracking or telemetry at scale — forbidden without explicit authorization.
3. **Privacy of geolocation data**: Any personal geolocation data must be handled per local privacy laws; do not store in AIDB without user approval.

---

## Acceptance Criteria

Per Gemini research:
1. `config/capability-lifecycle-registry.json` contains `gis-systems` at state ≥ `proposed`.
2. `.agent/GIS-SYSTEMS-INSTRUCTIONS.md` exists with domain tag, CRS discipline rules, tool order.
3. `gis-systems-health` validation check exits 0.
4. When `implemented`: CRS transformation of GeoJSON between two CRS succeeds via GDAL; spatial join between two datasets succeeds in GeoPandas or PostGIS; static map PNG generated from vector dataset via headless GDAL/QGIS script.
5. When `validated`: Gemini review-gate PASS on one geospatial pipeline output; no P0/P1 regressions.

---

## Rollback Procedure

1. Set `gis-systems` registry state to `blocked`.
2. Remove `gis-systems` intent class from `config/intent-routing-map.json` if added.
3. Disable `gis-systems-health` check (`"enabled": false`).
4. Archive `gis-systems-patterns` AIDB namespace content.
5. Remove `.#gis` dev shell from `flake.nix` if added.

---

## Open Items

| Item | Slice |
|---|---|
| Provision gdal, postgis, geopandas, qgis, spatialite-tools in `nix develop .#gis` | gis-systems.1 |
| CRS Validator tool: ogrinfo → validate → canonical transform | gis-systems.2 |
| Seed `gis-systems-patterns` AIDB namespace (CRS rules + OSM/Natural Earth patterns) | gis-systems.3 |
| Wire `gis-systems` intent class in `config/intent-routing-map.json` | gis-systems.4 |
| Natural Earth + OSM data ingest pipeline | gis-systems.5 |
| Gemini review gate on first geospatial pipeline output | gis-systems.6 (→ validated) |

---

## Related Docs

- `docs/architecture/domain-activation-template.md`
- `docs/architecture/gemini-review-gate.md`
- `docs/architecture/routing-profile-inventory.md`
- `.agents/delegation/outputs/gemini-20260518-121439-w2gzy1.log` (Gemini research — Domain C)
