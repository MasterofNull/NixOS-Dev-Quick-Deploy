# Harness-First Task Evidence

Date: 2026-10-09
Task ID: HF-20261009-020

## Objective
- Plan item ci-5 (honest claims). The capability audit flagged 12 STALE-CLAIM entries ("integrated"/"production" with no use in 30 days). Each was verified against the logs, not changed wholesale.
  - Corrected to available-unused: aq-eval-harness, aq-inference-bench, tooling-manifest, workflow-blueprints, local-surface-research.
  - Corrected to partial: osint-research-store (its collection holds 0 points).
  - Corrected to enabled-unmeasured: identity-kernel-service.
  - Kept, with the reason recorded: t3mp3st-intake (scope-gated by design), aidb-rag-stores (an audit false positive; 23k searches), affective-engine-module (in-process, invisible to tool logs).
  - understand-anything is handled in its own slice.
- Each entry carries `usage_evidence` and `maturity_prior`, and the reference doc is regenerated.

## Workflow/Session IDs
- Session ID: c30f6c3c-e25f-4e8e-8ce5-b4faa7687d3f

## Delegation Decision
- The orchestrator did this directly: it is judgement work over audit evidence, with small JSON edits.

## Commands Executed
```bash
rg -c <name> tool-audit.jsonl / hybrid-events.jsonl   # 0 for all except osint (hits on an empty collection)
scripts/ai/aq-capability-catalog validate     # PASS 19
scripts/ai/aq-capability-catalog check-doc    # PASS
```

## Validation Evidence
- The catalog is valid and the reference doc is up to date. The prior maturity is preserved per entry for reversal.

## Rollback Plan
- Revert the commit.

## Residual Risk
- The audit's catalog mapping produces false positives for in-process modules and data stores; improving it is follow-up work.

## Hint Feedback
- None.
