# Paused work checkpoint — 2026-09-17

Disposition: ACTIVATION_BLOCKED. Preservation commit only; no feature acceptance,
runtime enablement, production restore, or prompt-evaluation claim.

Branch: checkpoint/paused-work-20260917
Assembly worktree: /tmp/aq-checkpoint-20260917.QWqMf6 (disposable)
Base: c63469354d0dea372405e6475b8c6a3b87602b39
Owner: hyperd. Integrator: Codex. Implementers of retained source: previous agents.
The durable branch and synchronized Git objects preserve this checkpoint; the
assembly directory is not the long-term storage authority.

## Retained implementation and exact file SHA-256 values

- config/env-contract.yaml: f36bf407e53e15d004970939a23aa111df1bbe50b36bad1c0f08f31aba9a0abe
- ai-stack/prompts/registry.yaml: 50524478fd43d80640c46bf668d9cdbbd5fbe7feae5eba7366dd2e36ed2f8730
- scripts/ai/aq-factory-restore: d40180928f0c901fb7b0d1f6518ad6d38b81c31b878b1b0e7fdf2ca59d36948e
- scripts/testing/test-aq-factory-restore.py: 97de2ddfffb136843266138d3a86d019b7520c5e3e25985a9128ea4280685bf6
- .agents/plans/factory-state-packaging/TOOL-SPEC.md: 27c7d9cf69fcfece7a5f30ebbba6d183294f801a72f6c86c1b59f99b76060cee

The prompt registry changes dates only and has no corresponding evaluation
receipt; it remains unverified metadata. The restore tool has unresolved
check/use races against a hostile concurrent writer and incomplete SQL trust,
VM roundtrip, UI QA and cancellation/rollback validation. Do not integrate or
activate these sources from the presence of this commit.

The prior holding branch still retains aabd0ac9/e5644ace. Its temporary Git
metadata is missing. The prior full Tier-0 gate reported 51 PASS/2 FAIL for ignored
runtime prerequisites; private agent settings were not copied to manufacture PASS.

## Advisory evidence

Retain the FT-1 and FT-4 Antigravity reports, generation receipts, and exact
archived task bytes. They are late advisory contributions, not replacement
acceptance of the original implementation or a new runtime authorization.
The inactive archived tasks are retained without recreating active watched tasks.
Both the tracked origin versions and the later claimed versions are retained:
their output metadata differed. No version was overwritten or discarded.

## Current checkpoint validation

`python3 scripts/testing/test-aq-factory-restore.py`: 2 PASS in 15.244 seconds.
Fresh `scripts/governance/tier0-validation-gate.sh --pre-commit`: 51 PASS/2 FAIL.
Failures: missing ignored `.agent/qa` in provider-probe lock setup, and missing
ignored `.claude/settings.json` in enabled-MCP candidate regression. These are
recorded prerequisites, not waived release gates. No private configuration or
credentials were copied into the assembly worktree. Normal commit hooks remain
enabled; no final independent feature acceptance is claimed.

## Resume and next gates

Inspect the branch, verify these file hashes and the committed diff, then read
the existing factory-state-packaging plan. Continue only the bounded outstanding
restore validation/hardening slice after its criteria and authority are confirmed.
Use existing tracker/task/event records to project pause state; do not hand-edit
completion percentages or add a competing lifecycle registry.

Active next development remains CS-3 integration fencing and separately authorized
local producer timing. This checkpoint preserves the paused restore work while
those slices proceed. Run syntax/focused checks, full Tier-0 and normal hooks;
record actual results in the commit body, including non-passing prerequisites.
