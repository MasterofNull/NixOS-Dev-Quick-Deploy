# Integrity Scan Debt PRD

Updated: 2026-05-24T20:21:33Z

## Objective

Turn the orphan/technical-debt scanner into a bounded, machine-readable validation primitive so agents can safely use it to remediate registration, documentation, and logical orphan debt.

## Problem

`scripts/ai/aq-integrity-scan` advertised `--json` but did not implement it, and its logical orphan scan used an expensive all-modules by all-files regex strategy. In practice, piping it through `head` did not return promptly, which made it unsafe for workflow validation and agent handoff.

## Scope

- Add JSON output and summary metadata.
- Add runtime/file-count bounds and explicit truncation reporting.
- Optimize logical orphan scanning to parse import references once per file.
- Add a focused regression test and path-gated validation.
- Record lessons for agent workflow checks.
- Fix sparse operational SLO validation that blocks unrelated commits on low-sample historical incidents.

## Out Of Scope

- Resolving every orphan handler in this slice.
- Deciding whether each logical orphan is dead code or an entrypoint.

## Acceptance

- `aq-integrity-scan --json --max-logical-files ...` returns valid JSON.
- Scan output reports elapsed time, truncation, and finding counts.
- Focused CI runs the scanner contract when scanner/test/registry changes.
- Delegate success-rate QA skips when the 24h sample is below the enforcement threshold.
- Tier0 passes.
