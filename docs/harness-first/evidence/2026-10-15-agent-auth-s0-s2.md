# Agent-auth AUTH-S0 and AUTH-S2 (2026-10-15)

## Objective

Implement the frozen-READY remainder of S0-S2 from `.agents/plans/agent-auth/DESIGN.md` (v2.1) on branch `feat/agent-auth-s0-s2`:

- AUTH-S0 (design 8.1, 5.3, 5.4): `hmac.compare_digest` for every API-key compare in the coordinator and aidb; a required-but-empty key never fails open; the audit hook no longer writes the raw credential; Tempo gRPC bound to loopback.
- AUTH-S2 (design 4.1-4.4, 6.1, 7, 8.1): `config/agent-auth-policy.json`, matcher, shadow engine, `mode`/`shadowUntil` Nix options with an expiry assertion, metrics, `GET /admin/v1/auth/stats|explain`, `X-AQ-Would-Deny`, policy lint (tier0.d), benchmark harness.
- AUTH-S1 is NOT redone: the coordinator Host/Origin/content-type guard landed in PR #524 (commit 7f1f7282, labelled "AUTH-S0" in v1 numbering; it is v2 S1 for the coordinator). Switchboard and dashboard guards remain open under S1.

Out of scope and untouched: S3+ (UDS identity), enforce/lockdown, `/run/aq-coordinator/mode`, dashboard panel, health-spider checks (S8), `aq-agent-auth` CLI (S8).

## Workflow/Session IDs

- Branch/worktree: `feat/agent-auth-s0-s2` at `.agents/delegation/worktrees/auth-next` (from origin/main).
- Design SSOT: `.agents/plans/agent-auth/DESIGN.md`; tracker: `.agents/plans/agent-auth/tracker.json` (items AUTH-S0..S10, editorial only).
- Dispatch: implementer sub-agent (Sonnet 5.5, balanced tier, Rule 17 default) on orchestrator instruction. No commit or push performed; changes are staged for review.

## Delegation Decision

Implementation delegated to the Claude balanced tier per Rule 17. Independent review is required before commit (design 8.1 lists "independent" for S2 and "self + tier0" for S0); the implementer did not review its own work. Full tier0 was deliberately not run (instruction); the tier0.d checks for the new policy and tracker were run directly.

## Commands Executed

```
python3 -m pytest ai-stack/mcp-servers/hybrid-coordinator/tests/test_authz_shadow.py \
  ai-stack/mcp-servers/hybrid-coordinator/tests/test_agent_auth_s0.py \
  ai-stack/mcp-servers/hybrid-coordinator/tests/test_http_guard.py \
  ai-stack/tests/unit/test_agent_auth_aidb.py -q -p no:cacheprovider
python3 scripts/governance/lint-agent-auth-policy.py
python3 scripts/ai/aq-pm-tracker .agents/plans/agent-auth --check
bash scripts/governance/tier0.d/check-pm-tracker.sh --pre-commit
python3 scripts/testing/bench-agent-auth-middleware.py --strict
nix-instantiate --parse <each edited .nix>
nix eval --json .#nixosConfigurations.hyperd-ai-dev.config.systemd.services --apply <filter AQ_AGENT_AUTH|AI_STACK_REQUIRE>
```

## Validation Evidence

- Unit tests: 63 passed (28 existing guard tests, 13 S0 tests, 15 shadow/policy tests, 6 aidb tests, plus subtests).
- Compare: `keys_equal` asserts `hmac.compare_digest` is called; empty, `None` and non-string never match; no `!=` on a key remains in the touched coordinator and aidb sites (static assertion for aidb).
- Empty key: with `AI_STACK_REQUIRE_API_KEY=1`, `resolve_auth_context` returns 503 `api_key_not_provisioned` instead of `no-api-key-configured`; `create_api_key_middleware()` and aidb `startup()` raise at startup; aidb `_require_api_key` returns 503 and `_authenticate` raises. With the variable unset behaviour is unchanged (compat).
- Provisioning check: `nix/modules/services/mcp-servers.nix` asserts `sec.enable` whenever the AI stack role is active, and both units read the key from sops via `lib.optional sec.enable ...API_KEY_FILE`. Nix therefore sets `AI_STACK_REQUIRE_API_KEY=1` on the coordinator and aidb units under the same `sec.enable` condition; the nix eval above confirms both units carry it. Where secrets are disabled the variable is absent and legacy behaviour is retained, so no client loses access.
- Audit: `_audit_caller_identity` returns the auth mode (`api-key`, `loopback-agent`, ...), `credentialed` or `anonymous`; test asserts the secret is absent for `X-API-Key` and `Authorization: Bearer`, and that both former `caller_identity = token` sites are gone. `http_server_impl` cannot be imported in the dev shell (needs `mcp` and the strict service env), so the function is extracted by AST and exec'd; the end-to-end audit row was not exercised live.
- Policy engine: longest-prefix, method match, unknown route to `admin` (denied for non-owner classes), public paths, validation failures (undeclared scope, missing guidance, non-subset `self_service`), shadow header and JSONL row for `/research/web/fetch` from `legacy-loopback`, `off` passthrough, `enforce` treated as shadow, missing policy file degrades to off (no crash), stats and explain endpoints.
- Lint: `PASS: 13 scopes, 43 loopback prefixes covered, 58 static routes default to 'admin' (informational)`. Tracker: `PASS: agent-auth/tracker.json valid + projects`; tier0.d/check-pm-tracker `PASS: 24 plan tracker(s)`.
- Benchmark (in-process, n=5000 per variant, interleaved), two runs: delta p50 36-45 us (gate 50), p95 54-82 us (gate 100), p99 58-66 us (gate 250); all PASS. p50 headroom is thin on a loaded host; the design keeps this WARN in tier0 and a blocker only at S2/S3 acceptance.
- Nix: `.#nixosConfigurations.hyperd-ai-dev` evaluates; coordinator env contains `AQ_AGENT_AUTH_MODE=shadow`, `AQ_AGENT_AUTH_POLICY=<repo>/config/agent-auth-policy.json`, `AQ_AGENT_AUTH_SHADOW_UNTIL=2026-12-15`.
- Not verified: live service behaviour (no rebuild or restart was done), `/admin/v1/auth/stats` against the running coordinator, Tempo restart with the new `grpc_listen_address`, and whether any current client sends traffic that shadow will flag. Policy assignments for prefixes the design does not list (`/cache/`, `/harness/`, `/parity/`, `/operator/`, `/review/`, `/control/review/`, GET reads on memory/learning/feedback) are marked `note` in the policy and are for the shadow soak to confirm.

### Review follow-ups applied (2026-10-15)

- Constant-time compare extended to `extensions/mcp_jsonrpc_adapter.py` (shared helper), `dashboard/backend/api/routes/models.py` (inline `hmac.compare_digest`, two sites), `nixos-docs/server.py` (shared helper; `shared` already on its path) and `embeddings-service/server.py` (inline `hmac.compare_digest`). All were simple swaps; no tracked follow-up needed. Guard: `ai-stack/tests/unit/test_api_key_compare_guard.py` fails on `==`/`!=` between credential-like and API-key-like names across the coordinator, aidb, nixos-docs, embeddings-service and the dashboard models route. It is a regex heuristic, so it will not catch renamed variables.
- Shadow decision block (match, metrics, audit write) is wrapped: any exception increments `agent_auth_shadow_errors_total`, logs at most once a minute, and the request proceeds. Tests: `policy.match` raising, and an unwritable audit path.
- Degrade visibility: gauges `agent_auth_effective_mode{configured,effective}` and `agent_auth_policy_error`; `/admin/v1/auth/stats` also reports `configured_mode`, `shadow_errors`, `policy_error`. S8 health-spider must go RED when configured=shadow and effective=off (recorded in the tracker AUTH-S8 goal).
- `tier0.d/check-sops-sync.sh` now fails when the hybrid or aidb API-key entry has an empty `ENC[AES256_GCM,data:,...]` payload (no decryption). Exercised against a synthetic SOPS file (blank fails, non-empty passes) and the real file (passes). Limits: a whitespace-only or placeholder plaintext still has non-empty ciphertext and is caught only by the service startup assertion; the empty-plaintext-to-empty-`data:` encoding was confirmed from sops format knowledge and the synthetic file, not by encrypting a blank value with sops here.

### Focused-CI import fix

`test-hybrid-auth-profile-policy.py` failed with `No module named 'shared.api_key_auth'`. Root cause: the test only put `hybrid-coordinator` on `sys.path`, so `shared` resolved through the ambient `PYTHONPATH`, which points at the main checkout (that lacks the new module until merge). Production is not affected: the coordinator, aidb and nixos-docs units set `PYTHONPATH` to `${repoMcp}` (the deployed checkout, `ai-stack/mcp-servers`) and already import `shared.*` the same way (`router.py`, `server.py`). The embeddings-service and dashboard changes use inline `hmac.compare_digest` and need no shared path. Fix: the test now prepends `ai-stack/mcp-servers` to `sys.path`, mirroring `PYTHONPATH`. Deployment order matters: pull the checkout before `nrs` (already in the activation command), since the units import from it. Verified: `run-focused-ci-checks.sh --pre-commit` exit 0; import smokes under a worktree-only path resolved `shared.api_key_auth` for the coordinator modules, aidb and nixos-docs (their later imports of `pgvector`/`git` are absent from the dev python, unrelated), and the dashboard models route imports.

## Rollback Plan

- S2: set `mySystem.aiStack.agentAuth.mode = "off"` (or `AQ_AGENT_AUTH_MODE=off`), then `nrs`; the middleware becomes a pass-through. A missing or invalid policy file also degrades to off with an error log.
- S0 required-key: remove the `AI_STACK_REQUIRE_API_KEY` lines in `nix/modules/services/mcp-servers.nix` and rebuild; the code path is inert without the variable.
- Tempo: drop `grpc_listen_address` from `monitoring.nix`.
- Full revert: `git revert` of the slice commit.

## Residual Risk

- Shadow classes are a stub: every TCP caller is `legacy-loopback` until S3, so would-deny counts show what the compat grants do not cover, not real caller identity.
- `AI_STACK_REQUIRE_API_KEY=1` turns a blank sops secret into a service start failure (intended fail-closed); owner should confirm both secret files are non-empty before `nrs`.
- aidb has other unauthenticated paths outside `_require_api_key` (S9 probes them); not addressed here.
- Policy file is read from the repo checkout path; if the owner rebuilds before this branch is merged into the checkout, the coordinator logs an error and runs with shadow off.
- `mode` enum has only `off|shadow`; `enforce`/`lockdown` and removal of `off` after the migration are S5 work.
- Backlog entries (design S0: "log the findings in issues-backlog.md") were not written because the main checkout holds uncommitted edits to that append-only file; the orchestrator should append them.

- The agent-auth audit file lives in the telemetry directory (mode 0770, owner group writable), so the owner uid can tamper with it; it is attribution, not tamper-evident (the audit-sidecar mirror is a cut MVP item).
- aidb `_require_api_key` is defined twice in `aidb/server.py` (the later definition wins); both were patched identically. Recommend deleting the dead first copy in a follow-up and adding a CI job that imports the real aidb module with its dependencies, since the dev shell tests here use source extraction.

## Commit subject and detection

Use one combined subject so both tracker patterns match: `feat(agent-auth): AUTH-S0 credential hygiene and AUTH-S2 shadow policy engine`. Detection: `feat\(agent-auth\): .*AUTH-S0` and `feat\(agent-auth\): .*AUTH-S2` both match it. (Two separate commits, each with its own `AUTH-Sn` in the subject, also work.)

## Hint Feedback

No aq-hints query was run in this delegated slice; the design files and direct source reads were sufficient. Friction noted: `http_server_impl` and the coordinator `Config` cannot be imported under the dev shell (strict env, missing `mcp`), which forced AST-extraction tests and `AI_STRICT_ENV=false` in the lint script; a lightweight import seam for auth helpers would remove this.

## Owner activation command

After review and merge to main (owner acts; pull the checkout first so the policy file exists at the path in the unit):

```
cd /home/hyperd/Documents/NixOS-Dev-Quick-Deploy && git pull --ff-only && sudo nixos-rebuild switch --flake .#hyperd-ai-dev
```

Then verify (the admin routes need the API key):

```
curl -s -H "X-API-Key: $(cat /run/secrets/hybrid_api_key)" http://127.0.0.1:${HYBRID_PORT:-8003}/admin/v1/auth/stats
curl -s -o /dev/null -D - -X POST http://127.0.0.1:${HYBRID_PORT:-8003}/research/web/fetch -H 'Content-Type: application/json' -d '{}' | grep -i x-aq-would-deny
```

Secret file name depends on `mySystem.secrets.names.hybridApiKey`; adjust the path accordingly.
