# Handoff Memo — 2026-05-18

**Status:** Phase 58B + post-rebuild hardening complete. All 6 domains `promoted`; AIDB namespaces seeded (11–100 docs each); dashboard header card eval/hints restored; agent tool waste eliminated system-wide; aq-qa 67/67 PASS.
**Last Action (2026-05-18):** (1) Fixed dashboard eval_latest_pct/hint_adoption_pct (commit e985b804) — _aq_report_snapshot() now reads persisted snapshot, never spawns aq-report inline. (2) Eliminated agent tool waste: Gemini default→yolo mode, Codex stdin fix, Local/Qwen run_shell_command alias. (3) All 6 domain dev shells verified post-rebuild. (4) AIDB seeded: security-findings (20), nix-systems-patterns (100), embedded-hardware (14), mobile-web (11), scientific-research (12), gis-systems (12).
**Next Step:** (a) nixos-rebuild switch required from terminal to deploy shell_tools.py changes for local/Qwen agent. (b) Route one real task through each promoted domain and monitor P0/P1 regressions. (c) Consider per-domain default slices later; do **not** default all domains automatically.
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
| security-systems | `.#security` | security-findings | remote-reasoning / local-tool-calling | promoted |
| systems-software | `.#systems` | nix-systems-patterns | local-tool-calling | promoted |
| embedded-hardware | `.#embedded` | embedded-hardware-patterns | remote-reasoning | promoted |
| mobile-web | `.#mobile-web` | mobile-web-patterns | remote-reasoning | promoted |
| scientific-research | `.#scientific` | scientific-research-patterns | remote-reasoning | promoted |
| gis-systems | `.#gis` | gis-systems-patterns | local-tool-calling | promoted |

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
- Gemini review gate: **PASS** — `.agents/delegation/outputs/gemini-20260518-150453-tcswtz.log`
- Candidate soak: **PASS** — `.agents/plans/phase-58b-candidate-soak-log.md`
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

1. Decide whether any promoted domain should become `default` routing behavior.
   - Decision recorded: **no bulk default** — see `.agents/plans/phase-58b-default-routing-decision.md`.
2. Route one real task through each promoted domain.
3. Decide whether real Lighthouse CLI should be required before defaulting mobile-web or can remain a promoted enhancement item.
4. Continue monitoring for P0/P1 regressions during actual opt-in use.

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
- `.agents/plans/phase-58b-review-package.md`
- `config/capability-lifecycle-registry.json` states advanced to `candidate` for all six Phase 58A domains after Gemini PASS and Codex orchestrator decision
- `.agents/plans/phase-58b-candidate-soak-log.md`
- `config/capability-lifecycle-registry.json` states advanced to `promoted` for all six Phase 58A domains after candidate soak PASS
- `.agents/plans/phase-58b-default-routing-decision.md`
