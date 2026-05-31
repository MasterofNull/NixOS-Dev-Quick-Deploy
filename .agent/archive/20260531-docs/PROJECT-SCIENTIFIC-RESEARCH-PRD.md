# PRD — scientific-research Domain Activation

**Domain tag:** `scientific-research`
**Status:** Implemented — Phase 58A capability expansion
**Authors:** Claude (orchestrator/architect) · Gemini (research synthesizer)
**Date:** 2026-05-18
**Upstream template:** `docs/architecture/domain-activation-template.md`
**Gemini research:** `.agents/delegation/outputs/gemini-20260518-121439-w2gzy1.log` (Domain B)

---

## Problem Statement

The harness has Python/R scientific stack foundations (numpy, scipy, matplotlib available in nixpkgs) but lacks:
- Reproducibility infrastructure (Snakemake pipelines, seed/version/provenance defaults)
- Literature-search and citation-ingestion pipelines
- Notebook-to-report workflow (Jupyter → PDF via Pandoc/LaTeX)
- Scientific project scaffold templates
- AIDB namespace for research methodology, reproducibility guardrails, and HPC bridge patterns

Without a formal domain, scientific work uses no shared reproducibility contract, stores no institutional knowledge in AIDB, and has no routing preference for the fundamentally different query types (hypothesis synthesis vs data transformation).

---

## Goal

Establish `scientific-research` as a first-class capability domain. Initial activation covers:

1. Registering the domain (proposed state)
2. Declaring routing preference and AIDB namespace
3. Authoring the agent instruction surface
4. Wiring a baseline validation hook

Implementation note (2026-05-18): `nix develop .#scientific` is implemented with NumPy/SciPy/Pandas/Matplotlib/JupyterLab/Snakemake/Biopython, Pandoc, TeX Live, and R. DOI ingestion, scaffold generation, and AIDB seeding remain follow-on work before validation/promotion.

**First follow-on slice (per Gemini research):** Reproducible Research Scaffold Generator — CLI tool to initialize a domain-compliant research directory with Snakemake, Jupyter, and a `.gitignore` tailored for large datasets.

---

## Kernel Objects Touched

| Kernel object | How this domain touches it |
|---|---|
| `intent` | Adds `scientific-research` intent class → `remote-reasoning` for hypothesis synthesis; `local-tool-calling` for data transformation |
| `memory-evidence` | Reproducibility contract, methodology guardrails, citation schemas → AIDB namespace `scientific-research-patterns` |
| `workflow-session` | Scientific pipelines (Snakemake DAGs) map to WorkflowExecutor pattern; checkpoint/retry semantics apply |

---

## Routing Profile(s)

| Use case | Profile | Notes (Gemini research) |
|---|---|---|
| Hypothesis synthesis & literature review | `remote-reasoning` | Deep semantic linking and synthesis |
| Data transformation & plotting | `local-tool-calling` | Deterministic Python/Pandas work |
| Formula & constant lookup | `default` | Standard scientific knowledge; Qwen adequate |

---

## AIDB Namespace

**Namespace:** `scientific-research-patterns`

Seed content per Gemini research:
- `scientific_reproducibility_contract` — Project rules for seeds, version pinning, provenance metadata
- `citation_metadata_schemas` — BibTeX/CSL mappings and DOI resolution patterns
- `statistical_methodology_guardrails` — p-value interpretation, uncertainty quantification, bias detection guidelines
- `data_sovereignty_policies` — Local-first rules for sensitive research data (GDPR/HIPAA basics); do not send to remote endpoints without authorization
- `hpc_nix_patterns` — Bridging local Nix shells to remote SLURM/MPI clusters

---

## Tool Preferences

### Recommended Nix packages (from Gemini research)

| Package | nixpkgs attribute | Purpose |
|---|---|---|
| Jupyter | `pkgs.python3Packages.jupyter` | Interactive exploration + visualization |
| Snakemake | `pkgs.snakemake` | Reproducible, auditable scientific pipelines |
| LaTeX (minimal) | `pkgs.texlive.combined.scheme-small` | Report/paper generation |
| Pandoc | `pkgs.pandoc` | Notebook-to-paper universal converter |
| NumPy | `pkgs.python3Packages.numpy` | N-dimensional array computing foundation |

### Tool order

1. `nix develop .#scientific` — domain dev shell (provision in scientific-research.1)
2. `snakemake --cores all` — pipeline execution (reproducible, auditable)
3. `jupyter nbconvert --to pdf` — notebook → report
4. `pandoc notebook.md -o report.pdf` — markdown → PDF via Pandoc/LaTeX
5. `python3 -c "import numpy, scipy, matplotlib"` — stack health check
6. `scripts/governance/tier0-validation-gate.sh --pre-commit` — always before commit

### Reproducibility rules (mandatory for all agents in this domain)

- Set `random.seed(N)` / `numpy.random.seed(N)` explicitly — never use unseeded randomness
- Pin all Python package versions in `requirements.txt` or `pyproject.toml`
- Record provenance metadata (dataset source, version, retrieval date) before AIDB write
- Two runs of the same notebook with the same seed MUST produce identical numerical outputs — validate before commit

### Forbidden

- DURC (Dual-Use Research of Concern) workflows: biological, chemical, or radiological synthesis logic
- De-anonymization algorithms for human subject data without institutional authorization
- Hardcoded data paths (use env vars or config files; data is never committed to git)
- `pip install` in Nix context (NixOS-first: Nix dev shell only)
- Sending sensitive research data to remote endpoints without explicit user authorization

---

## Security and Safety Considerations

Per Gemini research — key dual-use concerns:

1. **DURC**: Biological, chemical, or radiological research logic that could be repurposed for hazardous synthesis. Forbidden without explicit institutional authorization and ethics documentation.
2. **Data de-anonymization**: Algorithms that re-identify anonymized human subjects — treat as approval-gated; Gemini review gate required.
3. **Data sovereignty**: Research data may be sensitive; local-first storage only; no external AIDB endpoints without authorization.

---

## Acceptance Criteria

Per Gemini research:
1. `config/capability-lifecycle-registry.json` contains `scientific-research` at state ≥ `proposed`.
2. `.agent/SCIENTIFIC-RESEARCH-INSTRUCTIONS.md` exists with domain tag, reproducibility rules, tool order.
3. `scientific-research-health` validation check exits 0.
4. At `implemented`: the scientific shell provides the declared reproducibility toolchain.
5. Before `validated`: a Snakemake pipeline executes to PDF from raw CSV, DOI ingestion yields validated BibTeX, two identical runs produce identical numerical outputs, `scientific-research-patterns` is seeded, Gemini review-gate PASS is recorded on a reproducibility workflow, and there are no P0/P1 regressions.

---

## Rollback Procedure

1. Set `scientific-research` registry state to `blocked`.
2. Remove `scientific-research` intent class from `config/intent-routing-map.json` if added.
3. Disable `scientific-research-health` check (`"enabled": false`).
4. Archive `scientific-research-patterns` AIDB namespace content.
5. Remove `.#scientific` dev shell from `flake.nix` if added.

---

## Open Items

| Item | Slice |
|---|---|
| Provision jupyter, snakemake, texlive, pandoc, numpy in `nix develop .#scientific` | scientific-research.1 |
| Reproducible Research Scaffold Generator CLI | scientific-research.2 |
| DOI → BibTeX ingestion pipeline | scientific-research.3 |
| Seed `scientific-research-patterns` AIDB namespace | scientific-research.4 |
| Notebook-to-PDF pipeline + aq-qa check | scientific-research.5 (→ validated) |

---

## Related Docs

- `docs/architecture/domain-activation-template.md`
- `docs/architecture/gemini-review-gate.md`
- `docs/architecture/routing-profile-inventory.md`
- `.agents/delegation/outputs/gemini-20260518-121439-w2gzy1.log` (Gemini research — Domain B)
