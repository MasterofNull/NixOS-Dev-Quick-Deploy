# Scientific-Research Domain — Agent Instruction Payload

**Domain tag:** `scientific-research`
**State:** proposed (2026-05-18)
**Upstream authority:** `.agent/PROJECT-SCIENTIFIC-RESEARCH-PRD.md`, `docs/architecture/capability-lifecycle.md`
**Registry ID:** `scientific-research` in `config/capability-lifecycle-registry.json`

---

## Domain Scope

Applies when performing: scientific data analysis, Snakemake pipeline development, Jupyter notebook authoring, LaTeX/Pandoc report generation, DOI/citation ingestion, reproducibility validation, or scientific knowledge retrieval from AIDB (`scientific-research-patterns` namespace).

---

## Eligible Task Classes

| Task class | Eligible agents | Notes |
|---|---|---|
| Formula / constant lookup | Qwen (Tier A) | Pure retrieval; bounded |
| Matplotlib / Pandas data transformation (≤400 lines) | Qwen (Tier B) | Review-gated |
| Snakemake pipeline rule authoring (≤4 rules) | Qwen (Tier B) | Review-gated |
| Hypothesis synthesis / literature review | Claude/Gemini | `remote-reasoning`; Gemini review gate |
| DOI → BibTeX ingestion | Claude | Automated; no gate for standard DOIs |
| DURC workflows | Forbidden (autonomous) | Requires institutional authorization |
| Data de-anonymization algorithms | Human-gated | Approval-gated; ethics documentation required |

---

## Reproducibility Rules (mandatory)

1. Set `random.seed(N)` / `numpy.random.seed(N)` explicitly — never use unseeded randomness
2. Pin all package versions in `requirements.txt` or `pyproject.toml`
3. Record provenance (dataset source, version, retrieval date) before any AIDB write
4. Two runs with identical seed MUST produce identical numerical outputs — validate before commit
5. Never commit raw data to git — use `.gitignore` + external data store reference

---

## Tool Preferences

1. `nix develop .#scientific` — domain dev shell (not yet provisioned; scientific-research.1)
2. `snakemake --cores all` — reproducible pipeline execution
3. `jupyter nbconvert --to pdf` — notebook → report
4. `pandoc notebook.md -o report.pdf` — markdown → PDF
5. `python3 -c "import numpy, scipy, matplotlib; print('ok')"` — stack health check
6. `scripts/governance/tier0-validation-gate.sh --pre-commit` — mandatory before commit

**Forbidden:** DURC workflows; data de-anonymization without authorization; `pip install` in Nix context; hardcoded data paths.

---

## AIDB Namespace Binding

**Namespace:** `scientific-research-patterns`

- Read: query before starting statistical analysis or pipeline design.
- Write: after resolving methodology or adding dataset pattern. Include provenance metadata.

---

## Review Requirements

| Work category | Gate required |
|---|---|
| Hypothesis synthesis / statistical methodology | Gemini review gate |
| Domain dev shell (flake.nix) | Gemini review gate |
| Data de-anonymization (if authorized) | Gemini review gate + user confirm |
| Snakemake pipeline (Qwen Tier B) | Gemini review gate |
| Data transformation / plotting (Qwen Tier B) | Gemini review gate |
| Formula lookup / constant retrieval | No gate required |

---

## Routing Preference

| Query type | Profile |
|---|---|
| Hypothesis synthesis & literature review | `remote-reasoning` |
| Data transformation & plotting | `local-tool-calling` |
| Formula & constant lookup | `default` |
