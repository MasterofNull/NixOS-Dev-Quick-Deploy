# Harness-First Task Evidence

Date: 2026-10-10
Task ID: HF-20261010-040

## Objective
- First live capability-audit report after deploy (dashboard: fresh) flagged BROKEN 1 / STALE-CLAIM 2 / UNDISCOVERABLE 1.
  - nvd-sync BROKEN was a transient: it failed during nrs and has since succeeded (root cause fixed in #453).
  - github-mcp-readonly and semgrep-mcp claimed "official" with 0 use in 30d. They are corrected to available-unused with usage_evidence (the ci-5 policy).
  - ai-capability-audit was UNDISCOVERABLE because the index was regenerated from a worktree audit that saw it as dead. The index is now regenerated from a live-usage audit (441 entries).
- Also corrected the sandbox activation guidance: nsjail is service-scoped (NSJAIL_BIN in the coordinator env), not on the user PATH. Confirmed live: nsjail-3.6 present and executable, and NSJAIL_TOOL_PATH declares the coding tools.

## Workflow/Session IDs
- Session ID: c30f6c3c-e25f-4e8e-8ce5-b4faa7687d3f

## Delegation Decision
- Orchestrator, direct (follow-ups from deploy verification).

## Commands Executed
```bash
aq-capability-audit --live-root <main>   # UNDISCOVERABLE=0 STALE-CLAIM=0 DEAD-CANDIDATE=0 BROKEN=0
aq-capability-catalog validate (PASS 19); test-capability-index PASS (441)
systemctl show -p Environment ai-hybrid-coordinator   # NSJAIL_BIN=.../nsjail-3.6/bin/nsjail
```

## Validation Evidence
- All warning classes are 0 on the live audit.

## Rollback Plan
- Revert.

## Residual Risk
- The index-from-worktree pitfall is logged in the backlog.

## Hint Feedback
- None.
