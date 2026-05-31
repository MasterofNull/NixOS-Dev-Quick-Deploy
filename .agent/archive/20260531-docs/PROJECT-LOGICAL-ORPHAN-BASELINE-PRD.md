# Logical Orphan Baseline PRD

Updated: 2026-05-25T03:35:00Z

## Objective

Convert logical orphan cleanup from a large one-time audit into a ratcheting validation workflow: existing candidates are inventoried, new candidates fail focused CI, and future remediation can classify or remove debt in small slices.

## Problem

The earlier scanner reported a large count of zero-inbound modules without file paths, ownership, or prevention. That makes the debt hard to act on and easy to grow. Some findings are real dead code, while others are entrypoints, service components, or externally wired modules that static import checks cannot prove.

## Approach

- Report logical orphan candidates with stable file paths and heuristic classifications.
- Store the current candidate set in `config/aq-integrity-logical-orphans.json`.
- Treat the baseline as known debt, not acceptance: every entry still needs `keep`, `wire`, `delete`, or `document-entrypoint`.
- Add a focused CI guard that fails when changed `ai-stack` code introduces a new zero-inbound module not present in the baseline.
- Keep scanner output bounded and machine-readable so agents can automate the cleanup safely.
- Count external operational references from harness scripts, Nix, dashboard backend, config, tests, and skill docs so runtime entrypoints are not misclassified as dead libraries.

## Acceptance

- Current logical orphan baseline is committed and valid JSON.
- `aq-integrity-scan --fail-on-new-logical` passes with the committed baseline.
- Focused CI runs the logical orphan guard for `ai-stack` changes.
- Contract tests cover path-aware findings and baseline/new-candidate separation.
- Workflow notes explain the failure pattern and prevention rule.
- Remediation passes wire confirmed backend gaps and lower the baseline from 115 to 81 candidates.

## Current Status

- 81 candidates remain in the baseline.
- 51 are externally referenced entrypoint candidates that need coverage verification.
- 16 are unreferenced entrypoint-shaped files that need wiring or removal review.
- 14 are skill assets and should remain as skill-owned assets.
- 0 remain pure library candidates.

## Remediation Workflow

For each baseline entry:

1. `delete` if unused and not referenced by docs, Nix service wiring, CLI wrappers, tests, or runtime reflection.
2. `wire` if the module is intended runtime behavior but no route, service, dashboard, timer, or test reaches it.
3. `keep` if it is intentionally external, generated, plugin-loaded, or an entrypoint; document that reason in the baseline.
4. `split` if the file mixes dead helpers with live entrypoint code.

The baseline count must trend down over time. New entries require explicit review in the same change that introduces them.
