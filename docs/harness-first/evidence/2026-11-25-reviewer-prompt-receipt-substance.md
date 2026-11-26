# Reviewer prompt states the receipt substance requirement

## Objective

Stop PASS reviews from failing at receipt mint: aq-land's reviewer prompt now asks for the format `aq-review-receipt substantive()` accepts.

## Workflow/Session IDs

- Failed mints 2026-11-25: local reviews of 86f5ea453 (aq-qa fix), prompt-eval, e308bf1a (805-byte one-sentence replies).
- Orchestrator Simurg@claude/opus-5.5#d1203103; implementer Claude Sonnet 5.5 sub-agent.

## Delegation Decision

Bounded prompt + test change; Claude Sonnet implementer (Codex reserved as reviewer).

## Commands Executed

- `python3 scripts/testing/test-aq-land.py` (15 tests OK)
- `python3 scripts/testing/test-aq-review-receipt.py` (45 tests OK)
- `scripts/governance/tier0-validation-gate.sh --pre-commit`

## Validation Evidence

The prompt asks for a `## Findings` heading, or `No findings.` plus `Reviewed files:` with repo-relative paths, matching `substantive()`. A new test confirms the instructed no-findings reply and a one-finding reply pass and a one-sentence reply still fails. The mint check is unchanged.

## Rollback Plan

Revert the commit; prompts return to the two closing lines only.

## Residual Risk

The format is advisory to the model; a reviewer that ignores it still fails minting (correctly).

## Hint Feedback

The mint requirement was not visible from the prompt side; prompt and gate now state the same contract.

## Addendum: heading-only bypass closed

Codex review codex-20261125-144106-n1ab6o (REQUEST_CHANGES) found that `substantive()` in `scripts/ai/aq-review-receipt` accepted a bare findings heading, so the new prompt format would let a heading plus a one-sentence approval mint a receipt. The heading now counts only when a path-like token follows it; the no-findings+path and prose branches are unchanged, so the gate is stricter. New tests: heading-only approval fails; heading + finding with a path passes; heading + `No findings.` + `Reviewed files:` passes. `python3 scripts/testing/test-aq-review-receipt.py`: 45 tests OK. Root-level files (e.g. `flake.nix`) are accepted as reviewed paths (codex-20261125-144725-grhfm2).

## Addendum

Redesign (owner 2026-11-25): substance now requires naming a file the reviewed diff changes; regex path heuristics retired for that branch.
