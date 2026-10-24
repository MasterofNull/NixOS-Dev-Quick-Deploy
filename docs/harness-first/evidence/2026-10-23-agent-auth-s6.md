# Agent-auth AUTH-S6 research.fetch SSRF Hardening (2026-10-23)

## Objective

Harden the outbound HTTP research primitives against Server-Side Request Forgery (SSRF) and DNS rebinding attacks:
1. Pinned-IP connect via `resolve_pinned`: DNS resolution is performed once asynchronously, requiring all returned addresses to be safe, globally routable IPs (rejecting loopback, RFC1918, link-local, cloud metadata 169.254.169.254, NAT64, 6to4, and CGNAT). Outbound connections are bound to the validated IP literal while preserving the original host in the `Host` header and TLS SNI extension.
2. Per-hop redirect validation: Every redirect is re-validated against scheme and IP pinning before the hop is executed.
3. Tighten-only configuration: When `AQ_AGENT_AUTH_MODE` is in `enforce` or `lockdown`, private egress blocking cannot be disabled via environment variables.
4. Scope separation: `/research/web/browser-fetch` is separated into dedicated scope `research.browser` (not granted by default to any class), isolating plain text web research (`research.fetch`) from headless browser capabilities.
5. Explicit test seam: Unit tests with mock transports require explicit `AQ_TEST_MODE=1` rather than silently disabling SSRF checks in production.

## Workflow/Session IDs

- Branch: `feat/wave14-agent-auth-s6-ssrf`
- Plan File: `.agents/plans/agent-auth/tracker.json` (AUTH-S6 -> SHIPPED, 64% complete)
- Policy File: `config/agent-auth-policy.json`

## Delegation Decision

Implemented directly by Antigravity under Orchestrator oversight with hermetic unit tests.

## Commands Executed

```bash
# Unit test suite
PYTHONPATH=ai-stack/mcp-servers:ai-stack/mcp-servers/shared python3 -m unittest ai-stack/tests/unit/test_ssrf_hardening_s6.py

# Web research integration test
python3 scripts/testing/test-web-research-lane.py

# Browser research integration test
python3 scripts/testing/test-browser-research.py

# Policy engine and shadow authorization suite
PYTHONPATH=ai-stack/mcp-servers/hybrid-coordinator:ai-stack/mcp-servers AI_STRICT_ENV=0 python3 ai-stack/mcp-servers/hybrid-coordinator/tests/test_authz_shadow.py
```

## Validation Evidence

- `test_ssrf_hardening_s6.py`: 8/8 tests passed covering literal IP rejections (127.0.0.1, ::1, 0.0.0.0, 169.254.169.254, RFC1918, CGNAT, NAT64, 6to4, IPv4-mapped IPv6), mixed DNS answer rejection, tighten-only switches, and `trust_env=False`.
- `test-web-research-lane.py`: PASS — robots-aware pacing and extraction limits preserved.
- `test-browser-research.py`: PASS — browser research lane bounded and robots-aware.
- `test_authz_shadow.py`: 19/19 tests passed verifying policy loading and shadow mode execution.

## Rollback Plan

Revert commit on `feat/wave14-agent-auth-s6-ssrf`.

## Residual Risk

External sites with non-standard TLS configurations or SNI handling may reject IP literal requests if SNI extension is unsupported by their web server. Mitigated by standard `extensions={"sni_hostname": host}` support in `httpx`.

## Commit subject and detection

- `feat(agent-auth): implement AUTH-S6 research.fetch SSRF hardening`
- Detection: `commit_match: ["feat\\(agent-auth\\): .*AUTH-S6"]`

## Hint Feedback

No hint changes required; `GET /hints` reflects current `agent-auth` status.

## Owner activation command

None required. Operates declaratively within the running python service environment.
