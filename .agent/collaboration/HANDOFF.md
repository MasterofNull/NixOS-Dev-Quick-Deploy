# Handoff Memo — 2026-05-18

**Status:** PHASE 58A COMPLETE + DOMAIN EXPANSION IN PROGRESS
**Last Action:** Activated security-systems (26505303) and systems-software (89d9b2a4) capability domains. Both validation hooks (security-systems-health, systems-software-health) run in focused-CI and pass. Registry now has 10 capabilities.
**Next Step:** Third domain expansion (embedded-hardware or data-analytics from master PRD). Then Codex final acceptance review of 58A.4–58A.7 when available.
**Context Bloat:** Low

## Domain Expansion — All 6 Domains Proposed

All 6 domains from master PRD activated. Registry at 14 capabilities.
Gemini used as research synthesizer for mobile-web, scientific-research, gis-systems.
Gemini research: `.agents/delegation/outputs/gemini-20260518-121439-w2gzy1.log`

**New workflow contract: Gemini researches all PRDs and plans before Claude finalizes.**

| Domain | Commit | State | Validation hook |
|---|---|---|---|
| security-systems | `26505303` | proposed | security-systems-health ✓ |
| systems-software | `89d9b2a4` | proposed | systems-software-health ✓ |
| embedded-hardware | `df140d93` | proposed | embedded-hardware-health ✓ |
| mobile-web | `6f4ca57d` | proposed | mobile-web-health ✓ |
| scientific-research | `6f4ca57d` | proposed | scientific-research-health ✓ |
| gis-systems | `6f4ca57d` | proposed | gis-systems-health ✓ |

Priority follow-on slices (to reach `implemented`):
- security-systems.1: Semgrep/Bandit/Trivy in Nix profile
- systems-software.1: shellcheck in Nix profile + nix-systems-patterns AIDB seeding
- embedded-hardware.1: Verilator/GHDL/Yosys/OpenOCD/ARM cross-toolchain dev shell
- mobile-web.1: Flutter/android-tools/nodejs/lighthouse/playwright dev shell
- scientific-research.1: jupyter/snakemake/texlive/pandoc dev shell
- gis-systems.1: gdal/postgis/geopandas/qgis/spatialite dev shell

## Phase 58A — All slices complete

| Slice | Commit | Status |
|---|---|---|
| 58A.x — tool contract | `cb5a58b7` | ✓ |
| 58A.0 — kernel declaration | `cb5a58b7` | ✓ Accepted |
| 58A.1 — role matrix SSOT | `f17b0372` | ✓ |
| 58A.2 — routing/profile inventory | `0d00f692` | ✓ |
| 58A.3 — instruction projections | `c8bf1088` | ✓ |
| 58A.4 — Gemini review-gate | `5a4a65ad` | ✓ (Codex final pending) |
| 58A.5 — Qwen eligibility | `07c1fa90` | ✓ (Codex final pending) |
| 58A.6 — capability lifecycle schema | `0953ce66` | ✓ (Codex final pending) |
| 58A.7 — domain activation template | `dc3e989c` | ✓ (Codex final pending) |
| Routing drift D-1–D-5 | `5851226b` | ✓ |

## Architecture artifacts produced

| Artifact | Status |
|---|---|
| `docs/architecture/canonical-kernel-declaration.md` | Accepted SSOT |
| `docs/architecture/role-matrix.md` | Accepted SSOT |
| `docs/architecture/routing-profile-inventory.md` | Accepted inventory |
| `docs/architecture/gemini-review-gate.md` | Accepted contract |
| `docs/architecture/qwen-task-eligibility.md` | Accepted contract |
| `docs/architecture/capability-lifecycle.md` | Accepted schema |
| `docs/architecture/domain-activation-template.md` | Accepted template |
| `config/capability-lifecycle-registry.json` | Seed registry (8 entries) |
| `docs/agent-guides/47-AGENT-TOOL-CONTRACT.md` | Accepted baseline |

## Phase 58A validation criteria check

Per `.agents/plans/phase-58a-capability-expansion-team-plan.md`:

1. ✓ Every active agent surface refers to the same role model (role-matrix.md SSOT)
2. ✓ Docs/config/runtime agree on active lanes and profile semantics (routing inventory + D-1–D-5 cleanup)
3. ✗ Codex first-class instruction surface — deferred (Codex rate-limited; 58A.3 noted as incomplete)
4. ✓ Gemini review policy is concrete enough to implement (gemini-review-gate.md)
5. ✓ Qwen bounded-task eligibility explicit and testable (Tier A/B/C tables + complexity bounds)
6. ✓ Lifecycle schema represents all 7 required states + blocked (capability-lifecycle.md)
7. ✓ Future domain can be described from standard template (domain-activation-template.md)

**Phase 58A is functionally complete. Item 3 (Codex instruction surface) is the one open item.**

## For Codex when available

1. Review and provide final acceptance verdict for 58A.4, 58A.5, 58A.6, 58A.7.
2. Author first-class Codex instruction surface (58A.3 remainder): Codex-specific SSOT instruction file analogous to GEMINI.md, citing role-matrix.md and routing-profile-inventory.md.
3. Begin first capability-domain expansion using domain-activation-template.md.

## Baseline health

`aq-qa 0`: 65 passed · 2 failed · 0 skipped (pre-existing; named in kernel declaration §7).
The routing drift cleanup (D-1 fix: `local` alias) caused focused-CI to re-run and PASS the intent-routing-map check.
