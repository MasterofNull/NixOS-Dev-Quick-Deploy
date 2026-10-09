# Harness-First Task Evidence

Date: 2026-10-08
Task ID: HF-20261008-210

## Objective
- Live incident at 22:09: ai-rsi-sweep crashed with EROFS. rsi_lifecycle.resolve() closed the backlog line with a temp file plus rename in .agent/memory, but the unit can write only the backlog FILE. The exception aborted the whole sweep after resolving 0.10.50 in the ledger, leaving 0.10.22 and the other sources unprocessed. In-place rewrites also broke the nrs preflight, which tolerates only pure appends to the live backlog.
- Fix:
  - Closure appends `[DONE] rsi-<id> — resolved <date>: <evidence> — ledger status=resolved` (idempotent, no temp file).
  - The sweep isolates per-incident resolve and record errors into resolve_errors and still exits non-zero.
  - discovery_agent treats a later non-active line for the same scope as superseding.

## Workflow/Session IDs
- Session ID: c30f6c3c-e25f-4e8e-8ce5-b4faa7687d3f

## Delegation Decision
- Sonnet implementer (ledger to backlog contract plus the local discovery parser). The orchestrator diagnosed the crash from the unit journal and verified the tests.

## Commands Executed
```bash
python3 scripts/testing/test-rsi-sweep.py (35 OK); test-rsi-lifecycle (13 OK); test-aq-rsi (9 OK); test-rsi-adapters (OK); test-discovery-agent-opportunities (PASS)
aq-rsi sweep --json on temp copies, with the backlog dir 0555 and file 0644
```

## Validation Evidence
- Live-shaped run: exit 0, resolve_errors [], 0.10.22 resolved, the backlog diff is a pure append (startswith check, 634 bytes). A test proves resolve works with a read-only directory and a writable file.

## Rollback Plan
- Revert the commit.

## Residual Risk
- Older backlog lines closed in place before this change keep their [DONE <date>] form; the idempotence check accepts both forms.

## Hint Feedback
- None.
