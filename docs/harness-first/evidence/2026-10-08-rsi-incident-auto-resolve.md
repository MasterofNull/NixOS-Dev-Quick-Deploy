# Harness-First Task Evidence

Date: 2026-10-08
Task ID: HF-20261008-rsi-incident-auto-resolve

## Objective
- RSI incidents never resolved except code-scanning, so transient or fixed conditions stayed open forever. The sweep now resolves an open incident when its source positively re-observes the condition cleared (aq-qa both sources, failed-units, service-error-rate, delegation-outcomes), via the existing rsi_lifecycle.resolve. Unknown never resolves. Delegation log-marker classes never resolve for a lane with an unreadable log.

## Workflow/Session IDs
- Session ID: c30f6c3c-e25f-4e8e-8ce5-b4faa7687d3f

## Delegation Decision
- Sonnet implementer (state-machine semantics). The orchestrator's review caught false resolves of codex:blocked/quota (logs resolved against the worktree, so a missing log looked clean) and returned it for hardening (DELEGATION_LOG_ROOT, unreadable-log guard).

## Commands Executed
```bash
python3 scripts/testing/test-rsi-sweep.py (34 OK); test-rsi-lifecycle (11 OK); test-aq-rsi (9 OK); test-rsi-adapters (OK)
aq-rsi sweep --dry-run --json with DELEGATION_LOG_ROOT=<main repo> on a temp ledger copy
```

## Validation Evidence
- Live dry run: resolves only aq-qa 0.10.22 (passing in the 03:59Z monitor run); codex:blocked and codex:quota stay open; no delegation incident resolves while still observed.

## Rollback Plan
- Revert the commit.

## Residual Risk
- Records with no output_file are not counted as unreadable. Payload-audit has no resolve path yet.

## Hint Feedback
- None.
