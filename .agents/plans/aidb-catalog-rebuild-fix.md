# AIDB catalog fetch resilience slice

## Objective

Make the catalog-sync producer retry bounded catalog fetches and return a truthful nonzero status when all attempts fail.

## Scope

Modify `scripts/data/sync-aidb-library-catalog.sh` and add a focused regression test.  Keep the existing user service and runtime state unchanged.

## Acceptance

- Each MCP and skills catalog fetch has at most three bounded attempts.
- A transient fetch failure can succeed on a later attempt.
- A permanent failure exits nonzero and reaches no import request.
- The change uses existing shell tools only and introduces no dependency.

## Minimal-code decision

Use Bash control flow with the existing `curl` timeout and the native `timeout` command for the Python lister.  A service-ordering migration is outside this bounded producer fix.

## Tracking

This is a single corrective slice with no pre-existing plan directory or tracker.  Its state is grounded in the focused regression test and `docs/harness-first/evidence/2026-10-16-aidb-catalog-rebuild.md`; activation remains deferred pending PR integration and an owner-run service verification.
