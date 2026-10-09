# Harness-First Task Evidence

Date: 2026-10-08
Task ID: HF-20261008-250

## Objective
- Owner: no implementation may be derelict, unused, stale, dead or unavailable. This adds a deterministic, repeatable `aq-capability-audit` (no LLM). It inventories catalog entries, scripts/ai, skills, MCP tools, nix units/timers and artifacts, and classifies each from telemetry, delegation, wiring, discovery and test evidence: ACTIVE / UNUSED-AVAILABLE / UNDISCOVERABLE / STALE-CLAIM / DEAD-CANDIDATE / BROKEN, each with a next_action.

## Workflow/Session IDs
- Session ID: c30f6c3c-e25f-4e8e-8ce5-b4faa7687d3f

## Delegation Decision
- Sonnet implementer. The orchestrator reviewed the classification and blind spots.

## Commands Executed
```bash
python3 scripts/testing/test-capability-audit.py   # 12 OK
aq-capability-audit --live-root <repo> --json --out .agents/reports/capability-audit-20261008.json   # 461 caps, 7.6s
```

## Validation Evidence
- Live baseline (30d): ACTIVE 172, UNUSED-AVAILABLE 96, UNDISCOVERABLE 112, STALE-CLAIM 12, DEAD-CANDIDATE 69, BROKEN 0.

## Rollback Plan
- Revert. The tool is read-only.

## Residual Risk
- Script usage is inferred (aq-usage.jsonl is dead since July). Wiring and discovery are name matches. Units absent on this host appear dead. DEAD-CANDIDATE is advisory; archiving is a separate, reviewed step (Rule 12).

## Hint Feedback
- None.
