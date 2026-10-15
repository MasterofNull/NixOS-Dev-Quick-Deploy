# Evidence: Coordinator Host/Origin/Content-Type Guard (AUTH-S0)

## Objective
Close DNS-rebinding and CSRF against the hybrid-coordinator. Loopback requests on "loopback-agent" prefixes were trusted with no key, no Host check, no Origin check, and `request.json()` accepted `text/plain`. Verified live pre-fix: `Host: evil.example.com` + `Origin: http://evil.example.com` to `/hints` returned 200. New middleware `middleware/http_guard.py` (wired in `router.py` after request-id, before rate limit) enforces: Host allowlist on every request (loopback names/addresses, own port or no port, plus `AQ_COORD_ALLOWED_HOSTS`) -> 421; Origin, when present, must be the coordinator's own loopback origin or in `AQ_COORD_ALLOWED_ORIGINS` -> 403; state-changing methods with a body must be `application/json` (or `+json`) -> 415; `Sec-Fetch-Site: cross-site` on state-changing methods -> 403. Rejection body: `{error, hint}`. Mode `AQ_COORD_HTTP_GUARD=enforce|shadow|off` (default enforce; unknown value fails closed to enforce), wired through `mySystem.mcpServers.hybridHttpGuard.{mode,extraAllowedHosts,extraAllowedOrigins}` in `nix/modules/core/options.nix` and the coordinator unit env in `nix/modules/services/mcp-servers.nix`; documented in `config/env-contract.yaml`.

## Workflow/Session IDs
Orchestrator session eb012479-4564-462f-8e6f-4824d5a77754. Slice AUTH-S0 (design: agent-auth-DESIGN.md AUTH-S1 row). Branch `fix/coordinator-host-origin-guard`, worktree `.agents/delegation/worktrees/auth-s0`. Implementer: Claude Sonnet 5.5. Changes left staged, not committed.

## Delegation Decision
Urgent bounded security slice delegated by the orchestrator to a Sonnet implementer (Rule 17). Needs independent review before commit. No tier0 run by the implementer.

## Commands Executed
- `git worktree add -b fix/coordinator-host-origin-guard .agents/delegation/worktrees/auth-s0 origin/main`
- `python3 -m pytest tests/test_http_guard.py -v` (from `ai-stack/mcp-servers/hybrid-coordinator`)
- `nix-instantiate --parse` on options.nix and mcp-servers.nix (syntax only)
- Caller inventory via `rg` over scripts/, lib/, dashboard/, ai-stack/, nix/, `.mcp.json`, `.claude/settings.json`.

## Validation Evidence
`tests/test_http_guard.py`: 28 passed (after security-review follow-ups). Also covers non-canonical Hosts (`localhost.`, `127.0.0.1.`, `[::ffff:127.0.0.1]`, `127.1`, `2130706433`) rejected, `localhost:` allowed, chunked text/plain, non-canonical Origin (case/trailing slash), ambiguous Content-Types, websocket foreign Origin -> 403, cross-site GET -> 403, startup warning in shadow/off, and startup failure when no port is configured. Base coverage evil Host -> 421 with `{error,hint}`; loopback hosts (127.0.0.1, localhost, [::1], with/without port) accepted; loopback name on wrong port rejected; extra host via env; evil/`null` Origin on POST and GET -> 403; own loopback Origin allowed; no-Origin JSON POST allowed; bodyless POST allowed; `text/plain` and form POST -> 415; `Sec-Fetch-Site: cross-site` POST -> 403 (GET unaffected); shadow logs `would_reject` and allows; enforce logs `rejected reason=... method= path= host= origin=`; off allows all; invalid mode fails closed.

Caller inventory (no breakage found by static review):
- MCP bridge `scripts/ai/mcp-bridge-hybrid.py`, `scripts/ai/lib/dispatch.py`, `aqos_ai_propose.py`: urllib with explicit `Content-Type: application/json`, Host 127.0.0.1:8003, no Origin. OK.
- Shell callers (`scripts/ai/_aq-qa-bash`, `scripts/automation/post-deploy-converge.sh`, `scripts/ai/local-orchestrator`, `scripts/data/seed-tool-audit-traffic.sh`, `scripts/testing/chaos-harness-smoke.sh`, `nixos-quick-deploy.sh`, `scripts/ai/aqd`): all use `http://127.0.0.1:8003` / `localhost:8003`. The orchestrator verified the curl callers set `-H "Content-Type: application/json"` via header arrays (`nixos-quick-deploy.sh` ~1066-1072 curl_args, `scripts/automation/post-deploy-converge.sh` ~86 and ~103, `scripts/ai/local-orchestrator` ~275, `scripts/data/seed-tool-audit-traffic.sh` ~19-20), as does `scripts/ai/_aq-qa-bash`, so they are compatible with the content-type check. `scripts/testing/chaos-harness-smoke.sh` was checked directly: its `headers=(-H 'Content-Type: application/json')` array is passed to every curl POST, so it is compatible. `scripts/ai/aqd` was not inspected for POST calls.
- Dashboard: `dashboard.html`/`assets/dashboard.js` reference :8003 only as labels; the backend (`dashboard/backend/api/routes/*`) calls the coordinator server-side, so no browser Origin reaches it. Switchboard, aidb, ralph call server-side with loopback Host.
- Python clients using aiohttp/requests with `data=<str>` instead of `json=` would send `text/plain`/form; none found in the paths grepped, but a full audit of every repo client was not completed.
- Exceptions to JSON-only: none needed; no coordinator handler uses `request.post()`/multipart/raw text.
- Host: only `127.0.0.1`, `localhost` seen for real callers (`coordinator.example.internal:8003` appears only in a test fixture). Remote/LAN access by name needs `extraAllowedHosts`.
- Requires `MCP_SERVER_PORT`/`PORT` to equal the listening port (Nix sets both to `hybridPort`; server.py already requires `MCP_SERVER_PORT`). If both are unset the guard raises at startup (unless mode `off`); it never guesses or hardcodes a port. A non-enforce mode logs a startup warning.
- GET-mutator inventory (follow-up scan): ~157 `add_get` registrations; filtered by mutating-sounding names and spot-inspected handlers (`/control/cache/warm`, `/workflow/run/{id}/replay`, `/runtime/isolation/workspace/{id}`, execute/status). No state-changing GET found. Not exhaustive; `/hints` GET may write usage telemetry (low impact). Follow-up: a full handler-level audit of GETs.
- Metrics: counter `hybrid_http_guard_rejections_total{reason,mode}` defined inside the guard module (prometheus_client default registry, scraped via existing `/metrics`); not added to `core/metrics.py` to avoid import coupling.

Not verified: live service behaviour (no rebuild by implementer), `router.create_app()` end-to-end import (needs QDRANT_URL etc.; only syntax-checked), nix eval of the full config, tier0.

## Rollback Plan
Runtime: set `mySystem.mcpServers.hybridHttpGuard.mode = "shadow"` (log only) or `"off"` (kill switch) and rebuild; or add `AQ_COORD_HTTP_GUARD=shadow` via the optimizer `overrides.env` EnvironmentFile and restart the coordinator. Code: revert the commit (new file + 3 small edits + tests).

## Residual Risk
Activation requires an owner rebuild and restart: `sudo nixos-rebuild switch --flake .#hyperd-ai-dev` then `sudo systemctl restart ai-hybrid-coordinator` (unit name per mcp-servers.nix; confirm with `systemctl list-units 'ai-hybrid*'`). After activation verify: `curl -s -o /dev/null -w '%{http_code}\n' -H 'Host: evil.example.com' http://127.0.0.1:8003/hints` returns 421, and a normal `curl http://127.0.0.1:8003/hints` returns 200. Switchboard, aidb, ralph, dashboard backend and other services have the same exposure and are tracked separately (AUTH-S1 shared module / AUTH-S9). A local process can still forge Host/Origin (the guard targets browsers, not local malware); the loopback-trusts-everything model remains until AUTH-S2+. Requests with no Host header are allowed. `extensions/federation_sync.py` runs a separate aiohttp app/TCPSite without this guard (bypass surface if federation is enabled): follow-up.

## Hint Feedback
Design doc AUTH-S0 row describes different work (constant-time compare etc.); the task brief matched the AUTH-S1 row. Hints/design naming mismatch worth reconciling in the plan tracker.
