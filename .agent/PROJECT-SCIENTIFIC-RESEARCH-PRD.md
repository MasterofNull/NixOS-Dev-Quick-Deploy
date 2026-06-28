# PRD - Scientific Research Domain Activation

**Domain tag:** `scientific-research`
**Status:** Active foundation, high-risk biosecurity and DURC work forbidden
**Last updated:** 2026-06-28

## Objective

Provide agents with reproducible scientific-computing workflows for pipeline review, notebooks, statistical methodology, citation/DOI handling, and report generation.

## Current Scope

- Snakemake-style reproducible pipeline guidance.
- Jupyter/notebook review and deterministic data summaries.
- LaTeX/Pandoc report-generation support.
- Citation, DOI, and methodology checks.
- Retrieval namespace: `scientific-research-patterns`.

## Safety Boundary

- DURC, harmful wet-lab enablement, pathogen optimization, and unsafe biomedical protocols are out of scope.
- Agents must preserve data provenance and distinguish source evidence from inference.

## Acceptance Criteria

- `scientific-research` exists in `config/capability-lifecycle-registry.json`.
- `.agent/SCIENTIFIC-RESEARCH-INSTRUCTIONS.md` is present.
- Scientific workflow outputs remain reproducible and cite source data or literature.
