# PRSI Research Index (March 2026)

Last updated: 2026-03-04
Purpose: canonical research corpus for pessimistic recursive self-improvement (PRSI) in this harness.

## Core Agentic Methods

1. ReAct (reason + act)
- Link: https://arxiv.org/abs/2210.03629
- Harness use: tool-selection traces and action-grounded reasoning loops.

2. Toolformer (self-supervised tool use)
- Link: https://arxiv.org/abs/2302.04761
- Harness use: selective tool-use heuristics and invocation utility scoring.

3. Reflexion (verbal reinforcement)
- Link: https://arxiv.org/abs/2303.11366
- Harness use: post-cycle reflection and error taxonomy updates.

4. Self-Refine (iterative self-feedback)
- Link: https://arxiv.org/abs/2303.17651
- Harness use: one-change iterative patching with verifier checkpoints.

5. Voyager (lifelong skill acquisition)
- Link: https://arxiv.org/abs/2305.16291
- Harness use: persistent skill/profile accumulation across cycles.

6. Constitutional AI
- Link: https://arxiv.org/abs/2212.08073
- Harness use: policy-constrained behavior and safety-first ranking.

## Evaluation and Reliability

1. OpenAI Evaluation Best Practices
- Link: https://platform.openai.com/docs/guides/evaluation-best-practices
- Harness use: stable eval protocols, representative suites, and traceable quality metrics.

2. SWE-agent Documentation
- Link: https://swe-agent.com/0.7/
- Harness use: practical patterns for coding-agent loops and reproducible workflows.

3. SWE-bench contamination and evaluation-risk studies
- Link: https://arxiv.org/abs/2506.12286
- Link: https://arxiv.org/abs/2512.10218
- Link: https://arxiv.org/abs/2510.08996
- Harness use: contamination-aware gating and anti-overfit penalties.

## PRSI Adoption Requirements in this Repo

- All PRSI cycles must be one logical mutating change with a rollback path.
- Gains must survive pessimistic gates: syntax/lint, runtime contracts, security checks, focused eval/smoke, and regression checks.
- Any result with contamination risk, low confidence, or missing evidence is treated as non-improvement.
- Cycle artifacts are required and must include counterfactual analysis before promotion.
