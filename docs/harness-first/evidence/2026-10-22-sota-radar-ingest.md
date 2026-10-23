# Evidence: SOTA Frontier Radar & Dynamic Ingestion Investigator

Date: 2026-10-22
Author: Antigravity / Claude
Reviewer: Codex
Scope: SOTA Tier Elevation (`sota-frontier-radar-ingest`)

## Summary
Implements the dynamic Frontier Radar Ingest & Investigator system:
1. **Schema & Declarative Registry**:
   - `config/schemas/frontier-radar.schema.json`: Strict JSON schema for source tracking across research preprints, frontier labs, national CVE authorities, formal verification, runtime systems, and design systems.
   - `config/frontier-radar-registry.json`: Initial verified sources (CISA KEV, OSV.dev, arXiv cs.SE/cs.CR, Anthropic, DeepMind, Vercel/Geist).
2. **Dynamic Ingestion & Discovery Engine**:
   - `scripts/ai/aq-radar-ingest`: CLI tool providing `list`, `discover` (dynamically ingest new URLs/repos encountered during agent work), and `scan` (System 1 signal evaluation).
3. **Automated Verification**:
   - `scripts/testing/test-radar-ingest.py`: PASS (verifies lifecycle, discovery registration, and persistence).

## DoD Attestation
- [x] Integrated: Added to `scripts/ai/` and configured under `config/`.
- [x] Turned ON: Executable and persistent.
- [x] Functionally validated: `test-radar-ingest.py` passes (0.04s).
- [x] Observable: `aq-radar-ingest list` reports active registry.
- [x] Intervenable: Dynamic registration via `--discover` accepts operator input.
