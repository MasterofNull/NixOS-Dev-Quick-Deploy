# Phase 68 VP Eng / Security Review
# Role: Gemini (VP Eng) — proxy entry by Claude pending async Gemini response
**Status:** Awaiting async Gemini response (dispatched 2026-05-23)
**Date:** 2026-05-23
**PRD:** `.agents/plans/PHASE-68-70-AIOS-CONTINUITY-PRD.md`

---

## Proxy Security Assessment (Claude as VP Eng proxy)

### 68.1 — ReAct Backtracking: blast radius + depth limit

**Security concern:** Unbounded backtracking creates a denial-of-service vector — a carefully crafted
failing workflow step could cause the orchestrator to loop until resource exhaustion.

**Assessment:**
- `max_depth = 3` is the right initial ceiling. Each backtrack re-enqueues from DLQ;
  DLQ already has a configurable TTL (default 24h). Three backtracks = 4 total attempts, matching
  standard retry policy for most cloud service integrations.
- The `backtrack_depth` counter must be stored durably (Postgres step row), not in-process memory —
  coordinator restart must not reset the counter (loop escape vector).
- **Recommended:** add `WORKFLOW_MAX_BACKTRACK_DEPTH` env var (default=3) so ops can tune without rebuild.

**Verdict:** APPROVE WITH CONDITION: backtrack_depth stored in Postgres (not Redis/memory). Env-configurable ceiling.

---

### 68.2 — MCP JSON-RPC 2.0 auth surface

**Security concern:** A new HTTP endpoint at `/mcp/v2` could bypass the S2 auth middleware if
not explicitly registered. The loopback exemption (`_is_loopback_agent_request`) allows intra-service
calls, but external clients should still require X-API-Key.

**Assessment:**
- `/mcp/v2` must be added to the **non-loopback auth-required** route list. It should NOT inherit
  the loopback exemption unless called from `127.0.0.1` — external MCP clients (future integration)
  must present X-API-Key.
- The tool dispatch inside the shim calls the same `dispatch_tool()` path that already enforces
  the `AUTH_PROFILE_TOOL_POLICY` blocklist — so tool-level auth is inherited correctly.
- **Risk:** `tools/list` endpoint could enumerate available tools to unauthenticated callers.
  **Recommend:** require X-API-Key on `GET /mcp/v2/tools` as well (not loopback-exempt).

**Verdict:** APPROVE WITH CONDITION: `/mcp/v2/*` requires X-API-Key for non-loopback callers.
`tools/list` must NOT be publicly enumerable without auth.

---

### AppArmor Complain → Enforce Timeline

**Review of soak data (as of 2026-05-23 rebuild):**
- Profiles deployed in complain mode.
- Soak period: minimum 7 days of production use before switching to enforce.
- Monitor: `journalctl -b --grep apparmor | grep -v audit` should show 0 violations.
- **Verdict:** NOT YET — complete soak first. Schedule Phase 70.2 review for 2026-05-30.

---

### 69.1 — AG-UI WebSocket security

**Concern (pre-emptive, Phase 69):** WebSocket endpoint `/ws/agent-state` must authenticate
the initial HTTP upgrade request. Without auth, any client on the same machine can subscribe
to the agent event stream.

**Recommended:** Check `X-API-Key` header on the upgrade request, OR restrict to loopback only
(127.0.0.1 connections only, reject from non-loopback origins).

**Verdict (Phase 69 guidance):** APPROVE IF loopback-only OR X-API-Key on upgrade.

---

## Verdicts Summary

| Item | Verdict | Condition |
|------|---------|-----------|
| 68.1 backtrack depth=3 | APPROVE | Depth in Postgres; env-configurable ceiling |
| 68.2 JSON-RPC 2.0 auth | APPROVE | X-API-Key required for non-loopback on /mcp/v2/* |
| tools/list public enum | DENY | Auth-required; not loopback-exempt |
| AppArmor enforce | NOT YET | 7-day soak required; schedule 2026-05-30 |
| 69.1 WebSocket auth | APPROVE IF | Loopback-only or X-API-Key on upgrade |

---

*Note: Proxy assessment by Claude in VP Eng / Gemini role. Gemini async response will supersede.*
