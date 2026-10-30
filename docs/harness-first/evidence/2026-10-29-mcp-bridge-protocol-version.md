# MCP bridge protocol version fallback (2026-10-29)

## Objective
Restore the Claude Code connection to hybrid-coordinator by making `scripts/ai/mcp-bridge-hybrid.py` negotiate an MCP protocol version the client accepts (details under Symptom, Root cause and Fix below).

## Workflow/Session IDs
- Branch: `fix/mcp-bridge-protocol-version`
- Builds on the version negotiation added in #640.
- No review run id recorded in this doc at time of writing.

## Delegation Decision
Implemented by Claude Sonnet (Rule 17 cheapest eligible), orchestrated by Claude Opus; review by local Qwen.

## Commands Executed
- `python3 scripts/testing/test-mcp-bridge-protocol-negotiation.py`
- Stdio smoke: `initialize` with `2025-06-18` and with `2099-01-01` against the bridge.

## Symptom
Claude Code failed to connect to hybrid-coordinator: `Server's protocol version is not supported: 2026-07-28`
(~/.cache/claude-cli-nodejs/<project>/mcp-logs-hybrid-coordinator/2026-10-30T03-37-23-937Z.jsonl; repeats back to 2026-10-28). Coordinator HTTP API healthy.

## Root cause
`scripts/ai/mcp-bridge-hybrid.py` (negotiation added in #640) echoed the requested version only if listed, otherwise answered with its newest
version, `2026-07-28`, which this client rejects. The client's requested version is not recorded in its MCP logs, so it is undetermined;
the failure implies it sent a version absent from the old list (likely 2025-11-25). `server/discover` also hardcoded `2026-07-28`.

## Fix
- Added `2025-11-25` to supported versions; unsupported/missing request now falls back to `FALLBACK_PROTOCOL_VERSION = "2025-06-18"`.
- `2026-07-28` is only returned when the client explicitly requests it.
- `server/discover` uses the negotiated version (cache hints only for >= 2026-07-28); no literal protocolVersion remains.

## Validation Evidence
`python3 scripts/testing/test-mcp-bridge-protocol-negotiation.py`
```
.....
Ran 5 tests in 3.273s
OK
```
Stdio smoke: initialize with `2025-06-18` -> `"protocolVersion": "2025-06-18"`; with `2099-01-01` -> `"2025-06-18"`.
Live reconnect from Claude Code still needs verification after merge (/mcp reconnect).

## Rollback Plan
Revert the commit that changes `scripts/ai/mcp-bridge-hybrid.py` and its test; the bridge returns to the #640 negotiation behavior.

## Residual Risk
- The client's requested protocol version is not recorded in its MCP logs, so the root cause (likely `2025-11-25`) is inferred, not observed.
- Live reconnect from Claude Code (`/mcp` reconnect) is not yet verified; it needs a check after merge.

## Hint Feedback
No aq-hints used for this slice.
