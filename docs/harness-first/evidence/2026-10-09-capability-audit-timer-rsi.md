# Harness-First Task Evidence

Date: 2026-10-09
Task ID: HF-20261009-060

## Objective
- Plan item ci-3: the capability audit runs daily (ai-capability-audit service + timer) and regressions reach RSI.
- Dated reports go to .agents/reports/capability-audit/; older ones move to .agents/archive/capability-audit/ (Rule 12, no rm).
- New RSI adapter `capability-audit`:
  - per-capability class regressions, plus thresholds (UNDISCOVERABLE > 10, STALE-CLAIM > 0, BROKEN > 0);
  - cleared() resolves on restoration;
  - the baseline comes only from timer reports with the same audit_version.
- The audit honours the honest catalog maturity values from #445. New classes: ACKNOWLEDGED (documented kept claims) and STALE-ARTIFACT (the stale understand-anything graph, separate from claims).

## Workflow/Session IDs
- Session ID: c30f6c3c-e25f-4e8e-8ce5-b4faa7687d3f

## Delegation Decision
- Sonnet implementer. The orchestrator review caught `rm -f` rotation (Rule 12), cross-tree baseline noise (about 60 false incidents) and kept-claims counting as STALE-CLAIM; all were fixed in a second pass.

## Commands Executed
```bash
test-rsi-sweep (42 OK), test-rsi-lifecycle (13), test-aq-rsi (9), test-rsi-adapters (5), test-capability-audit (15 OK), test-capability-index PASS
aq-capability-audit (live): ACTIVE 150, UNUSED-AVAILABLE 239, UNDISCOVERABLE 6, STALE-CLAIM 0, ACKNOWLEDGED 2, STALE-ARTIFACT 1, DEAD-CANDIDATE 69, BROKEN 0
aq-rsi sweep --dry-run (temp ledger): capability-audit state ok, 0 findings, previous=none
```

## Validation Evidence
- The units evaluate (ExecStart and ReadWritePaths); tmpfiles create both report dirs.

## Rollback Plan
- Revert; the timer stops after rebuild.

## Residual Risk
- The wrapper script's rotation is untested live until the first timer run (verify after nrs: `systemctl start ai-capability-audit`).

## Hint Feedback
- None.
