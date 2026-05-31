# Phase 58B Candidate Soak Log

**Date:** 2026-05-18  
**Owner:** Codex  
**Lifecycle transition:** `candidate → promoted`  
**Result:** PASS — no P0/P1 regressions observed during soak.

## Soak command summary

The candidate soak suite ran one non-trivial workflow per Phase 58A domain:

| Domain | Soak workflow | Result |
|---|---|---:|
| systems-software | Nix parse + statix/deadnix + shellcheck fixture through `.#systems` | PASS |
| security-systems | Bandit + local Semgrep fixture through `.#security` | PASS |
| embedded-hardware | Verilator lint fixture through `.#embedded` | PASS |
| gis-systems | GeoJSON CRS validation, EPSG:3857 transform, GDAL PNG through `.#gis` | PASS |
| scientific-research | Snakemake CSV → summary → Pandoc PDF through `.#scientific` | PASS |
| mobile-web | MASA harness fixture Lighthouse JSON + MASVS static scan | PASS |

## Observed non-blocking warnings

- Nix reported dirty tree warnings during `nix develop`; expected in this active working session.
- Nix eval-cache SQLite busy warnings were reported as ignored; the shell commands proceeded and passed.
- Pandoc/LaTeX emitted a `\\showhyphens` package warning during PDF generation; output artifact was produced and workflow passed.
- Mobile-web remains in fixture Lighthouse mode; real Lighthouse CLI remains a future hardening item before defaulting.

## Final soak output markers

```text
systems-software-soak=PASS
security-systems-soak=PASS
embedded-hardware-soak=PASS
gis-systems-soak=PASS
scientific-research-soak=PASS
[masa] status=pass lighthouse=fixture masvs_findings=0 high=0
```

## Recommendation

Promote all six domains from `candidate` to `promoted` for opt-in recommended use.

Do **not** set any domain to `default` yet. Defaulting requires a separate routing/default policy decision.

