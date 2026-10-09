# Harness-First Task Evidence

Date: 2026-10-09
Task ID: HF-20261009-080

## Objective
- Plan item ci-7, batch 1: put available-but-unused capabilities on real workflow paths.
  - aq-inference-bench runs as a post-switch hook after aq-model-switch (as the invoking user; bounded; JSON teed to telemetry).
  - aq-eval's static suites run as WARN-class phase-0 check 0.10.60 (both harnesses; about 5s; no inference).
  - aq-prime lists the workflow_blueprints and tooling_manifest MCP tools.
  - Hint rules point at workflow_blueprints and tooling_manifest.
  - The understand-anything refresh limit now lives in one place (config/understand-anything.json, read by capability_audit).
  - aq-graph-query is on the local-agent runtime allowlist, with per-subcommand argument validation (shell metacharacters rejected).
- Root-cause fix found on the way: the static hint matcher tested `kw in token_set`, so every multi-word keyword (14 across the rules, e.g. "new script", "hash mismatch") could never match, and those rules fired far less than intended. Multi-word keywords now match as consecutive query tokens.

## Workflow/Session IDs
- Session ID: c30f6c3c-e25f-4e8e-8ce5-b4faa7687d3f

## Delegation Decision
- Sonnet implementer. The orchestrator resolved the stack conflict with #447 (kept the stricter LIVE_CLAIM_MATURITY) and fixed the multi-word matcher at its producer.

## Commands Executed
```bash
python3 scripts/testing/test-hints-multiword-keywords.py   # PASS; FAILS (fires nothing) on the original matcher
test-capability-integration-wiring PASS; test_local_agent_runtime 15 passed; test-capability-audit OK; test-capability-index PASS; test-rsi-sweep OK; test-graph-query PASS; hints route/runtime/lessons suites PASS
```

## Validation Evidence
- Each wiring has a trigger point and a test. Inference-bench is not run here (the DB backfill is in progress); it runs at the next model switch.

## Rollback Plan
- Revert the commit.

## Residual Risk
- The new hint rules and the matcher fix need a hybrid-coordinator restart (rebuild) to go live. Phase-0 check 0.10.60 adds about 5s per QA run.

## Hint Feedback
- The multi-word keyword bug affected every static rule. It is fixed at the matcher.
