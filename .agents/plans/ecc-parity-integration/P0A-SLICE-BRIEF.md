# P0-A slice brief — extend native capability-gap resolution

Status: repository implementation ACCEPTED after Gate-A commit `2e1ac332`.
Independent Codex review passed implementation subject `0800714240bcdad4b78dd3f0c2341d4725618377a2c383f46dc198208e94620d`;
Claude supplied confirmatory PASS. Final metadata-bound hash is recorded in the
commit review trailers. Running-system activation is not performed.

## Objective and baseline

Extend the existing `aq-capability-gap` and discovery surfaces so the coordinator
can answer “already covered, partially covered, missing, denied, or ambiguous”
across tools, workflows, skills, roles/domain guidance and QA visibility. Do not
create a second discovery service or import ECC prompts.

Current measured baseline:

- `aq-capability-gap` resolves tools, workflow blueprints and exact project skill
  paths, but has no normalized outcome taxonomy across role/domain/provider names.
- `scripts/testing/test-capability-gap-integration.py` is static coordinator
  wiring coverage, not taxonomy/resolution behavior coverage.
- `/discovery/capabilities` ranks AIDB tools/skills/servers/datasets for queries;
  it does not emit equivalent/partial/missing/denied/ambiguous outcome verdicts.
- Dashboard exposes aggregate `capability_gap` counts and shared-skill totals, not
  a searchable evidence-backed coverage/gap catalog.

## Ownership

Implementer-owned files:

- `scripts/ai/aq-capability-gap`
- `config/capability-gap-catalog.json`
- new `config/schemas/capability-gap-catalog.schema.json`
- new `scripts/testing/test-capability-outcome-resolver.py`
- focused documentation under `docs/agent-guides/`

Root integration-owned files (separate claim, same slice):

- `scripts/testing/harness_qa/phases/phase0.py`
- `scripts/ai/_aq-qa-bash` (dual QA registration)
- `dashboard.html`
- `assets/dashboard.js`
- `dashboard/backend/api/routes/aistack.py` (existing runtime-summary projection)
- `scripts/testing/test-dashboard-advanced-runtime-summary.py`
- `scripts/testing/test-capability-gap-integration.py` (repair pre-existing
  removed-monolith path drift in the required validation)

Do not edit coordinator routing, shared-skill persistence, capability leases,
installer code, agent prompts, provider configs or external ECC source.

## Required behavior

- Versioned catalog entries declare canonical outcome ID, aliases, kind,
  evidence paths, authority class, status and QA/visibility references.
- Pure resolution accepts a bounded task/capability query plus optional domain and
  returns deterministic ranked candidates with verdict and evidence; ambiguity
  remains explicit and denied capability never becomes an install suggestion.
- Existing tool/workflow/skill CLI behavior remains compatible.
- Missing observations preserve bounded state and promotion thresholds; no
  automatic skill creation, package installation, network call or activation.
- Machine JSON distinguishes `equivalent`, `partial`, `missing`, `denied`,
  `ambiguous` and `unverified`.

## Validation and stop conditions

Focused commands:

```bash
python3 scripts/testing/test-capability-outcome-resolver.py
python3 scripts/testing/test-capability-gap-integration.py
aq-capability-gap --tool rg --format json
aq-capability-gap --skill testing-patterns --format json
aq-qa 0 --machine
scripts/governance/tier0-validation-gate.sh --pre-commit
```

Fixtures must cover canonical match, alias, cross-kind overlap, ambiguity, denied,
missing, stale evidence path and existing CLI compatibility. QA must exercise the
resolver's integration path, not only file presence. Dashboard must show catalog
freshness, equivalent/partial/missing/denied/ambiguous totals and explicit
`UNVERIFIED` when evidence is absent.

Stop successfully when focused tests, QA, dashboard fixture/syntax and Tier-0
pass, an independent non-author reviewer accepts the exact subject hash, and one
atomic commit records activation/exclusions. Stop for owner authority only if the
slice would require secrets, external accounts, deployment/rebuild or networked
installation. Nonblocking taxonomy suggestions go to the next slice.
