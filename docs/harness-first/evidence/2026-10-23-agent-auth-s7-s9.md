# Agent-auth AUTH-S7 and AUTH-S9 (2026-10-23)

## Objective

Implement slices `AUTH-S7` (Client migration off X-API-Key with UDS client and TCP fallback) and `AUTH-S9` (Probe and classify unverified services, host/origin enforcement validation, fail-closed empty key validation) under `.agents/plans/agent-auth/DESIGN.md`:
- AUTH-S7: Client migration helper `request_http_or_uds`, transparent UDS URL routing, automatic guided deny parsing, and MCP bridge UDS integration.
- AUTH-S9: In-repo service prober and classifier across standard AI harness ports (:8002, :8003, :8004, :8080, :8085, :8889), fail-closed empty API key verification for AIDB, and Host/Origin guard classification.

## Workflow/Session IDs

- Branch: `feat/wave17-agent-auth-s7-s9`
- Design SSOT: `.agents/plans/agent-auth/DESIGN.md`
- Tracker: `.agents/plans/agent-auth/tracker.json` (items AUTH-S7, AUTH-S9)

## Delegation Decision

Implemented with direct module authoring and independent validation across local test suites and live coordinator endpoints.

## Commands Executed

```bash
python3 scripts/testing/test-agent-auth-s7-s9.py
scripts/governance/tier0-validation-gate.sh --pre-commit
```

## Validation Evidence

- Unit test suite: `scripts/testing/test-agent-auth-s7-s9.py`: 8 passed in 0.064s with zero warnings.
- Real-world integration test: Tested `request_http_or_uds` against live `:8003/health` with transparent TCP fallback when UDS is not yet mounted.
- Verified Host/Origin guard response on `:8003/health` (HTTP 421 Misdirected Request on spoofed Host).
- Verified AIDB fail-closed empty key enforcement.
- Updated `.agents/plans/agent-auth/tracker.json`: marked AUTH-S7 and AUTH-S9 as SHIPPED.

## Rollback Plan

Revert the commit `feat(agent-auth): implement AUTH-S7 client UDS migration and AUTH-S9 service classification`. All changes are backwards-compatible additions to `scripts/ai/lib/` and non-breaking transparent fallbacks in `scripts/ai/mcp-bridge-hybrid.py`.

## Residual Risk

UDS sockets that do not yet exist on disk cleanly fall back to local TCP endpoints until systemd socket activation is turned on in subsequent activation phases.

## Commit subject and detection

`feat(agent-auth): implement AUTH-S7 client UDS migration and AUTH-S9 service classification` (matches `feat(agent-auth): .*AUTH-S7` and `feat(agent-auth): .*AUTH-S9`).

## Hint Feedback

No hints or issues encountered.

## Owner activation command

No privileged owner activation required; repo-only and library enhancement.
