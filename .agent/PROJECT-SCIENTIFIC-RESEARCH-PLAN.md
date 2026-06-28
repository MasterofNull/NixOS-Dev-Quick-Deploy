# Plan - Scientific Research

**PRD:** `.agent/PROJECT-SCIENTIFIC-RESEARCH-PRD.md`
**Status:** Baseline implemented
**Last updated:** 2026-06-28

## Scope

Activate reproducible scientific-computing guidance for pipelines, notebooks, reports, citations, and methodology review.

## Implementation Slices

1. Domain instruction anchor
   - Implemented: `.agent/SCIENTIFIC-RESEARCH-INSTRUCTIONS.md`

2. Lifecycle registry entry
   - Implemented: `scientific-research` in `config/capability-lifecycle-registry.json`

3. Evidence and provenance boundary
   - Implemented in PRD and domain instructions: preserve source provenance, separate inference from evidence, and forbid DURC/harmful wet-lab enablement.

## Validation

- Focused CI: `scientific-research domain baseline artifact presence check`
- `AQ_QA_SKIP_REPORT_BACKED_CHECKS=1 scripts/governance/tier0-validation-gate.sh --pre-commit`

## Remaining Work

- Add deterministic fixture tests for pipeline/report generation before introducing long-running scientific workflow automation.
- Add RAG seed verification if the `scientific-research-patterns` collection is refreshed.
