# Harness-First Task Evidence

Date: 2026-10-07
Task ID: HF-20261007-003

## Objective
- PRSI M5: code defaults for PRSI state/purge-audit point at canonical /var/lib/nixos-ai-stack/optimizer/prsi/, ending split-brain runtime-state.json.

## Workflow/Session IDs
- Workflow ID: wf-prsi-legacy-paths-20261007
- Session ID: c30f6c3c-e25f-4e8e-8ce5-b4faa7687d3f

## Delegation Decision
- Implementer: Claude Haiku 4.5. Reviewer: Claude Opus 5.5 + Antigravity queued.

## Commands Executed
```bash
python3 scripts/testing/test-prsi-queue-path-ssot.py
python3 scripts/testing/test-coordinator-prsi-canonical-queue.py
```

## Validation Evidence
- Live evidence: legacy runtime-state.json written 16:26:07Z vs canonical 16:25:37Z, counterfactual_samples 0 vs 2.
- SSOT test PASS (queue/state/purge canonical; no legacy defaults in live code).
- canonical-queue test PASS.

## Rollback Plan
- Revert commit (defaults only).

## Residual Risk
- Legacy dir /var/lib/nixos-ai-stack/prsi/ to be archived (mv, Rule 12) after merge; purge-audit history there must be moved, not dropped.

## Hint Feedback
- No aq-hints consulted for this slice; scope came from live telemetry and code reads.
