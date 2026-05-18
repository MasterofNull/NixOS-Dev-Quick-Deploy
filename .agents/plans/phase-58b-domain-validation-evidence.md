# Phase 58B Domain Validation Evidence

**Date:** 2026-05-18  
**Owner:** Codex  
**Scope:** Representative workflow evidence for `implemented → validated` readiness.

## Summary

| Domain | Representative workflow | Result | Notes |
|---|---|---:|---|
| security-systems | `nix develop .#security` static scan fixture using Bandit + local Semgrep rule | PASS | Safe Python fixture scanned; no external rules required |
| systems-software | `nix develop .#systems` Nix parse + statix/deadnix + shellcheck fixture | PASS | Uses local temp Nix module and shell script |
| embedded-hardware | `nix develop .#embedded` Verilator lint on tiny Verilog module | PASS | No hardware/JTAG/write operations |
| gis-systems | `nix develop .#gis` GeoJSON CRS validation, EPSG:3857 transform, GDAL PNG generation | PASS | Initial matplotlib approach failed because GIS shell lacks matplotlib; GDAL-native map generation passed |
| scientific-research | `nix develop .#scientific` Snakemake CSV → deterministic summary → Pandoc PDF, run twice | PASS | Initial pandas-in-Snakemake attempt failed; standard-library analysis path passed while preserving reproducibility criterion |
| mobile-web | Lighthouse JSON + MASVS static sample scan | BLOCKED / follow-up | `.#mobile-web` validation is dependency-heavy and remained silent/running; no local `lighthouse` binary present |

## Live AIDB namespace evidence

Verified with live AIDB `GET /documents?project=<namespace>&limit=1000`:

| Namespace | Documents |
|---|---:|
| `security-findings` | 19 |
| `nix-systems-patterns` | 347 |
| `embedded-hardware-patterns` | 13 |
| `mobile-web-patterns` | 10 |
| `scientific-research-patterns` | 11 |
| `gis-systems-patterns` | 11 |

## Validation observations / follow-up fixes

1. `aq-collaborate start` was broken because it pointed to removed `ai-stack/agentic-patterns`; Codex retargeted it to `lib/l4-coord/agents` and fixed the start command import/class usage.
2. `scripts/data/ingest-project-knowledge.py` defaulted to `localhost:8002`; Codex changed it to `127.0.0.1:8002` to match service binding and avoid intermittent timeout ambiguity.
3. GIS shell includes GeoPandas but not matplotlib; static map validation should use GDAL-native tools unless matplotlib is intentionally added.
4. Scientific shell exposes pandas to `python3`, but the first Snakemake job using `python` failed to import pandas. The successful validation used `python3` and standard library; future templates should prefer explicit `python3` or shell-specific interpreter paths.
5. Mobile-web validation needs a smaller deterministic harness:
   - either package/provide Lighthouse in the dev shell,
   - or add a repo-local audit fixture that produces Lighthouse-compatible JSON without network installs,
   - then run MASVS-aligned static sample scan.

## Lifecycle recommendation

Do **not** promote domains yet.

- Security, systems, embedded, GIS, and scientific have representative workflow evidence and can move toward review-gate evaluation.
- Mobile-web remains pending representative Lighthouse/MASVS workflow evidence.
- No domain should move from `implemented` to `validated` until the required review-gate PASS is recorded.

