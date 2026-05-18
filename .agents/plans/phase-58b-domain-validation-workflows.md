# Phase 58B — Domain Validation Workflows

**Owner:** Codex orchestration with team review gates  
**Date:** 2026-05-18  
**Lifecycle boundary:** `implemented → validated` only. Do not move any domain to `candidate` or `promoted` from this slice.

## Goal

Capture representative workflow evidence for the six Phase 58A capability domains after Codex PRD acceptance and live AIDB namespace seeding.

## Current evidence already complete

- Six PRDs accepted by Codex after reconciliation.
- Six AIDB namespaces live-seeded:
  - `security-findings`
  - `nix-systems-patterns`
  - `embedded-hardware-patterns`
  - `mobile-web-patterns`
  - `scientific-research-patterns`
  - `gis-systems-patterns`
- `scripts/automation/aidb-reindex.sh` now keeps those namespaces in the periodic reindex path.
- Tier0 pre-commit gate passed after seeding changes.

## Validation slices

### Slice 58B.2a — deterministic local workflow evidence

Run small representative workflows that do not require external network access or destructive hardware actions.

| Domain | Representative workflow | Evidence target |
|---|---|---|
| security-systems | Static scan of safe sample source with Bandit/Semgrep availability check | JSON or log artifact |
| systems-software | Nix/shell validation with statix/deadnix/shellcheck availability | log artifact |
| embedded-hardware | HDL lint of tiny Verilog module with Verilator | log artifact |
| gis-systems | CRS validation/transform + static map generation from local GeoJSON | output files + log |

### Slice 58B.2b — heavier artifact workflows

Run workflows that may pull larger dev-shell closures or require longer runtime.

| Domain | Representative workflow | Evidence target |
|---|---|---|
| scientific-research | Snakemake pipeline from CSV → deterministic result → PDF report | output files + reproducibility log |
| mobile-web | Lighthouse JSON and MASVS-aligned static sample scan | JSON/log artifact |

### Slice 58B.2c — review gate

Submit one representative output per domain through the review gate. Gemini output must be reviewed by Claude or Codex before lifecycle state changes.

### Slice 58B.2d — lifecycle update

Only after slices 58B.2a–c pass, update `config/capability-lifecycle-registry.json` from `implemented` to `validated` with evidence references.

## Safety constraints

- No firmware flash, JTAG, device writes, or destructive hardware operations.
- No external API keys or secrets in validation artifacts.
- No lifecycle promotion without review evidence.
- Keep validation artifacts small and reproducible.

