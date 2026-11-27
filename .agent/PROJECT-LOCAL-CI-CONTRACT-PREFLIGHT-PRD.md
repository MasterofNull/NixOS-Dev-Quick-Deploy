# Local CI contract preflight recovery

Scope frozen: register the existing usage-hook, plan-classification, and tier0 mutation-coverage tests with the existing focused pre-commit runner. Add negative regression coverage proving the original errors fail locally, and register that regression in config/ci-checks.json for hosted CI and test ownership. Reuse existing runner and tests; no dependencies, runtime services, gate bypasses, or policy changes.

Root cause: required hosted contract tests were absent from the local path-triggered validation registry. #877 omitted mutation-test ownership; #878 omitted a usage hook and plan classification.

Acceptance: correct relevant path selection; each original invalid fixture fails through real contract tests; valid fixtures pass; focused tests and tier0 wrapper pass, or exact unrelated blockers are recorded honestly. Independent review precedes PR publication.

Design scrutiny: architecture reuses one existing runner; failure modes include missed triggers and test recursion; developer experience preserves actionable diagnostics; security preserves hooks and clean Git environment. A bounded implementer checks these assumptions before edits.

Separate limitations: factory preflight currently rejects this repository’s existing hook manager without implemented composition verification; do not bypass it. Review artifact publication is repaired separately.
