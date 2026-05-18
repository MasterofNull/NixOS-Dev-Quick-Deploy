# Handoff Memo — 2026-05-18

**Status:** Phase 58A COMPLETE. All 6 capability domains at `implemented`. aq-qa 0: 67/67 PASS.
**Last Action:** Advanced all 6 domains to `implemented`; added `.#full` unified shell; fixed mobile-web/gis nixpkgs 25.11 breakage; committed f6711ea5 + 8cee9e25.
**Next Step:** Soak period for all 6 domains (≥1 session each, no P0/P1) → promote to `candidate`. Then orchestrator decision to `promoted` or `default`.
**Context Bloat:** Low — fresh session recommended before soak validation.

## Domain registry summary (all implemented, commit f6711ea5)

| Domain | Shell | AIDB namespace | Profile | State |
|---|---|---|---|---|
| security-systems | `.#security` | security-findings | remote-reasoning / local-tool-calling | implemented |
| systems-software | `.#systems` | nix-systems-patterns | local-tool-calling | implemented |
| embedded-hardware | `.#embedded` | embedded-hardware-patterns | remote-reasoning | implemented |
| mobile-web | `.#mobile-web` | mobile-web-patterns | remote-reasoning | implemented |
| scientific-research | `.#scientific` | scientific-research-patterns | remote-reasoning | implemented |
| gis-systems | `.#gis` | gis-systems-patterns | local-tool-calling | implemented |
| **unified** | `.#full` | all 6 namespaces | intent-classified | runtime |

## Intent routing (config/intent-routing-map.json v1.1)
All 6 domain intent classes wired: `security_analysis`, `systems_software`, `embedded_hardware`,
`mobile_web`, `scientific_research`, `gis_systems`. Hot-reload: `POST /control/intent/reload`.

## Validation evidence
- aq-qa 0: **67/67 PASS** (was 65; +2 from new domain checks in phase 58A)
- tier0: **14/14 PASS**
- All 6 domain health checks: **6/6 PASS** (from validation-check-registry.json)
- shellcheck 0.11.0: in system profile ✓
- trivy 0.66.0: in system profile ✓
- Dev shells verified post-rebuild: verilator 5.040, yosys 0.55, gdal 3.11.4, geopandas 1.1.1, semgrep 1.143.0

## Fixed during this session
- `nodePackages.lighthouse` removed from nixpkgs 25.11 → replaced with on-demand npm hint
- `postgis` standalone removed from nixpkgs 25.11 → use `spatialite-tools` in dev shell; `postgresqlPackages.postgis` for service config
- aq-qa 0.8.1 delegate rate fix (non-terminal events filtered from success ratio) — deployed
- aq-qa 0.1.2 reindex timeout raised to 3h — deployed via nixos-rebuild switch ✓

## Pending (next session)
1. Soak validation: run each domain shell on a real task; record in registry `soak_sessions`
2. AIDB namespace seeding: POST representative docs to each of the 6 namespaces
3. Advance domains from `implemented` → `candidate` → `promoted` per lifecycle.md
4. Codex acceptance review of all 6 domain PRDs (when Codex available)
