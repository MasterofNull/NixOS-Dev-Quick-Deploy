# Handoff Memo — 2026-05-18

**Status:** Phase 58B validation evidence in progress. All six domain PRDs have Codex acceptance PASS; all six AIDB namespaces are seeded; all six domains now have representative workflow evidence, with mobile-web partial due fixture Lighthouse mode.
**Last Action:** Added and ran `scripts/testing/mobile-web-masa-harness.py`; it produced Lighthouse-shaped JSON and MASVS static scan PASS without external installs. Real Lighthouse packaging remains a decision before validation if strict Lighthouse CLI evidence is required.
**Next Step:** run/record review-gate PASS evidence before any `implemented → validated` lifecycle update. Do **not** advance domains to `candidate` yet.
**Context Bloat:** Medium

## Phase 58B.0 reviewer verdict

Verdict: **PASS**

Acceptance evidence checked:
- six PRDs have `**Status:** Implemented — Phase 58A capability expansion`
- mobile-web PRD uses an on-demand Lighthouse npm hint and contains no `nodePackages.lighthouse`
- GIS PRD explicitly says standalone `pkgs.postgis` is not used and references `postgresqlPackages.postgis` only for service configuration
- PRDs state AIDB seeding remains pending or follow-on before validation/promotion
- PRDs contain no `not yet provisioned` wording for live tools such as ShellCheck v0.11 or the embedded toolchain

## Codex acceptance review — domain PRDs

Verdict: **PASS after revision**

The initial review found stale PRD drift (all six still marked `Proposed`, superseded package references for mobile-web/gis, and ambiguous AIDB timing). Those issues have been corrected in the PRDs. The set now matches the implemented architecture and the accepted domain template.

| Domain PRD | Verdict | Notes |
|---|---|---|
| security-systems | PASS | Tooling state corrected; validation boundary clarified |
| systems-software | PASS | ShellCheck state corrected; AIDB seeding moved to pre-validation evidence |
| embedded-hardware | PASS | Tool availability corrected; validation boundary clarified |
| mobile-web | PASS | Lighthouse / Playwright nixpkgs references corrected |
| scientific-research | PASS | Implemented shell vs future workflow evidence clarified |
| gis-systems | PASS | `spatialite-tools` / `postgresqlPackages.postgis` distinction corrected |

## Domain registry summary

| Domain | Shell | AIDB namespace | Profile | State |
|---|---|---|---|---|
| security-systems | `.#security` | security-findings | remote-reasoning / local-tool-calling | implemented |
| systems-software | `.#systems` | nix-systems-patterns | local-tool-calling | implemented |
| embedded-hardware | `.#embedded` | embedded-hardware-patterns | remote-reasoning | implemented |
| mobile-web | `.#mobile-web` | mobile-web-patterns | remote-reasoning | implemented |
| scientific-research | `.#scientific` | scientific-research-patterns | remote-reasoning | implemented |
| gis-systems | `.#gis` | gis-systems-patterns | local-tool-calling | implemented |

## Correct next transition path

Per `docs/architecture/capability-lifecycle.md`, domains must not skip from `implemented` to `candidate`.

Required order:
1. **implemented** — current state
2. **validated** — requires domain health evidence, representative workflow evidence, AIDB namespace completion where declared, and review-gate PASS where required
3. **candidate** — orchestrator opt-in decision
4. **promoted** — after soak period and no P0/P1 regressions

## Validation evidence currently known

- `aq-qa 0`: reported `67/67 PASS` in latest team handoff
- Codex rerun of tier0 pre-commit gate: `14/14 PASS`, including QA phase 0 `65 checks`
- all 6 domain health checks: reported PASS
- dev shells verified by team post-rebuild; Codex independently revalidated:
  - `.#embedded` — PASS
  - `.#scientific` — PASS
  - `.#gis` — PASS
  - `.#mobile-web` — validation still in progress / dependency-heavy
- `shellcheck` and `trivy` reported present in the system profile
- AIDB namespace seed evidence from live `GET /documents?project=<namespace>&limit=1000`:
  - `security-findings`: 19 documents
  - `nix-systems-patterns`: 347 documents
  - `embedded-hardware-patterns`: 13 documents
  - `mobile-web-patterns`: 10 documents
  - `scientific-research-patterns`: 11 documents
  - `gis-systems-patterns`: 11 documents
- Representative workflow evidence:
  - `security-systems`: PASS — Bandit + local Semgrep rule on safe sample source
  - `systems-software`: PASS — Nix parse + statix/deadnix + shellcheck fixture
  - `embedded-hardware`: PASS — Verilator lint of tiny Verilog module
  - `gis-systems`: PASS — GeoJSON CRS validation, EPSG:3857 transform, GDAL PNG generation
  - `scientific-research`: PASS — Snakemake CSV → deterministic summary → Pandoc PDF, repeated with identical numerical output
  - `mobile-web`: PASS / partial — deterministic MASA harness emitted Lighthouse-shaped JSON and MASVS static scan PASS; real Lighthouse binary still absent and `.#mobile-web` remains dependency-heavy/silent

## Outstanding operational work

1. Record review-gate evidence where required by each PRD.
2. Decide whether mobile-web fixture Lighthouse mode is sufficient for `validated`, or require a real Lighthouse binary before validation.
3. Move domains from `implemented` to `validated` only after representative workflow and review evidence exists.
4. Then begin soak tracking for later `candidate` / `promoted` decisions.

## Files added or reconciled by Codex in this continuation

- `.agent/CODEX.md`
- `.agents/plans/phase-58b-domain-prd-reconciliation.md`
- updated six domain PRDs to reflect implemented truth
- updated 58A review-plan statuses to reflect completed Codex acceptance
- `nix/home/base.nix` fix for VSCodium theme convergence
- `config/domain-knowledge-seeds.json`
- `scripts/data/seed-domain-knowledge.py`
- `scripts/automation/aidb-reindex.sh` now includes capability-domain seeding
- `scripts/data/ingest-project-knowledge.py` default AIDB URL now uses `127.0.0.1` to match the bound service and avoid `localhost` timeout ambiguity
- `.agents/plans/phase-58b-domain-validation-workflows.md`
- `.agents/plans/phase-58b-domain-validation-evidence.md`
- `scripts/ai/aq-collaborate` retargeted from removed `ai-stack/agentic-patterns` to `lib/l4-coord/agents` and repaired `start`
- `scripts/testing/mobile-web-masa-harness.py`
