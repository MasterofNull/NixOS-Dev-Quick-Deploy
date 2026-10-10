# Harness-First Task Evidence

Date: 2026-10-09
Task ID: HF-20261009-100

## Objective
- Plan item ci-7 batch 2.
  - UNDISCOVERABLE 5 → 0: a new `external-tool-packs` progressive-disclosure domain names github-mcp-readonly, semgrep-mcp, nixos-static-analysis, osint-research-store and identity-kernel-service.
  - The top 20 UNUSED-AVAILABLE capabilities (ranked by wiring, tests and core relevance) get hint rules with natural trigger phrases: aq-memory, aq-context-bootstrap, aq-context-manage, aq-health-spider, aq-runtime-diagnose/plan, aq-rsi-pending, aq-collab-round, aq-patterns, aq-gaps, aq-report, aq-wiki and others.
  - Their use is logged by the aq-usage hook, so the audit will move them to ACTIVE as agents invoke them.

## Workflow/Session IDs
- Session ID: c30f6c3c-e25f-4e8e-8ce5-b4faa7687d3f

## Delegation Decision
- Sonnet implementer; the orchestrator reviewed.

## Commands Executed
```bash
test-capability-integration-wiring-b2.py PASS (each rule fires on a natural query and names its script); test-capability-integration-wiring PASS; test-capability-audit OK; test-capability-index PASS (440); test-hints-multiword-keywords PASS; test-local-inference-l2b PASS
```

## Validation Evidence
- UNDISCOVERABLE 0. UNUSED-AVAILABLE moves only with real invocations (by design; the audit counts logged use).

## Rollback Plan
- Revert. Hint rules go live after a coordinator rebuild.

## Residual Risk
- Hint rules make capabilities discoverable at the right moment; actual adoption is measured by the next audits.

## Hint Feedback
- None.
