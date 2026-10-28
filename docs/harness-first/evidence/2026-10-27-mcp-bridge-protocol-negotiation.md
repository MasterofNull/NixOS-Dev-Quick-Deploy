# Hybrid MCP bridge protocol negotiation (2026-10-27)

Source: retro-review batch E (PR #570). Plan item P1.3 of `.agents/plans/system-integrity-recovery`.

## Defect
- `scripts/ai/mcp-bridge-hybrid.py` answered every `initialize` with `protocolVersion: "2026-07-28"` and never negotiated.
- Claude Code rejected the server at session start: "Server's protocol version is not supported: 2026-07-28", so the hybrid-coordinator MCP server was unavailable in Claude sessions.

## Fix
- `SUPPORTED_PROTOCOL_VERSIONS = 2026-07-28, 2025-06-18, 2025-03-26, 2024-11-05`. `initialize` echoes the client's requested version when supported; otherwise it answers the newest supported version (MCP lifecycle negotiation).
- 2026-07-28-only capability hints (`cacheScope`, `ttlMs`) are sent only when that version is negotiated; `structuredContent` only for 2025-06-18 and later. `server/discover` remains available as an extra method.

## Evidence
- `scripts/testing/test-mcp-bridge-protocol-negotiation.py`: 4 tests OK, driving the stdio bridge as a subprocess for each supported version plus unknown, old, garbage and absent versions.
- `scripts/testing/test-mcp-bridge-compat.py`: 3 tests OK. `scripts/testing/test-aq-mcp-conformance.py`: 2 tests OK. `py_compile` OK.

## Known gap
- Not yet verified against a live Claude Code reconnect; requires merge plus the owner's rebuild/restart of the bridge. Verification step after deploy: start a Claude Code session and confirm `hybrid-coordinator` connects.
