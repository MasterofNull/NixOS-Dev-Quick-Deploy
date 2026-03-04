# PRSI Research Fallback Notes (March 2026)

Purpose: ensure AIDB contains deterministic references when direct remote fetch/import fails.

## Sources with direct-ingest issues

1. Constitutional AI
- Primary link: https://arxiv.org/abs/2212.08073
- PRSI relevance: policy-guided behavior, bounded autonomous actions, and safety-first critique loops.
- Harness mapping: use policy constraints in `runtime-prsi-policy.json` and require explicit stop conditions.

2. OpenAI Evaluation Best Practices
- Primary link: https://platform.openai.com/docs/guides/evaluation-best-practices
- PRSI relevance: representative evaluation suites, stable protocols, and careful metric interpretation.
- Harness mapping: use holdout evals, contamination-aware penalties, and reproducibility checks before promotion.

## Operational requirement

Even when remote source scraping fails, these references remain mandatory in PRSI cycle design and review.
