# Front-Door Routing

Last updated: 2026-04-25

## Purpose

The AI harness exposes a stable human-facing front door so prompts can enter the system through a small set of intent-oriented route aliases instead of requiring callers to know internal switchboard profile names.

Current front door surfaces:

- `POST /v1/orchestrate` on the hybrid coordinator
- `scripts/ai/local-orchestrator`
- Continue/editor traffic routed through switchboard with the `continue-local` lane
- command-center routing posture and recent decision feeds:
  - `GET /api/aistack/routing/summary`
  - `GET /api/aistack/routing/decisions?limit=25`

Example CLI usage:

```bash
scripts/ai/local-orchestrator --route Explore "summarize the current harness posture"
scripts/ai/local-orchestrator --route Reasoning "compare two workflow integration options"
```

## Route Alias Contract

Alias mappings are defined in [config/route-aliases.json](/home/hyperd/Documents/NixOS-Dev-Quick-Deploy/config/route-aliases.json:1) and resolved by [route_aliases.py](/home/hyperd/Documents/NixOS-Dev-Quick-Deploy/ai-stack/mcp-servers/hybrid-coordinator/route_aliases.py:1).

Current canonical mappings:

| Alias | Resolved profile |
|-------|------------------|
| `default` | `default` |
| `Explore` | `default` |
| `Plan` | `default` |
| `Implementation` | `local-tool-calling` |
| `Reasoning` | `local-tool-calling` |
| `ToolCalling` | `local-tool-calling` |
| `Continuation` | `default` |

Explicit remote aliases remain available when the task really needs them:

| Alias | Resolved profile |
|-------|------------------|
| `RemoteCoding` | `remote-coding` |
| `RemoteReasoning` | `remote-reasoning` |
| `RemoteFree` | `remote-free` |
| `RemoteGemini` | `remote-gemini` |

Unknown aliases fall back to `default`.

## Routing Path Priority Rule

There are two routing paths into the coordinator. The priority rule is:

1. **Explicit `route` field in request body** → alias path (`route_aliases.resolve_route_alias()` → canonical profile). The caller's stated intent takes precedence.
2. **No `route` field** → intent classification path (`IntentClassifier` classifies query text → `config/intent-routing-map.json` lookup → canonical profile).

The two paths must not conflict: if both would apply, the explicit `route` field wins. The intent classification path may target profiles (e.g. `local`) not present in route-aliases.json `allowed_profiles`; this is a known drift item (D-1 in `docs/architecture/routing-profile-inventory.md`) and will be resolved in a follow-up cleanup slice.

## Request Flow

1. Caller submits a prompt to `/v1/orchestrate` or `local-orchestrator`.
2. If a `route` field is present, the alias is resolved to a canonical profile (alias path).
3. If no `route` field, the intent classifier resolves a canonical profile (intent path).
4. The coordinator injects routing metadata into query context:
   - `routed_profile`
   - `route_alias`
5. The request is forwarded into the normal coordinator query path.
6. Downstream routing, hints, memory recall, and switchboard policy still apply.

The `/v1/orchestrate` handler lives in [http_server.py](/home/hyperd/Documents/NixOS-Dev-Quick-Deploy/ai-stack/mcp-servers/hybrid-coordinator/http_server.py:6381).

## Operator Validation

Use these checks when validating front-door routing after repo changes or deploys:

```bash
scripts/ai/aq-qa 0
python3 -m pytest ai-stack/mcp-servers/hybrid-coordinator/tests/test_route_aliases.py
python3 -m pytest ai-stack/mcp-servers/hybrid-coordinator/tests/test_orchestrate_routing.py
python3 scripts/testing/test-dashboard-routing-posture-ui.py
curl -sS -X POST http://127.0.0.1:8003/v1/orchestrate \
  -H "Content-Type: application/json" \
  -H "X-API-Key: $(tr -d '\n' < /run/secrets/hybrid_coordinator_api_key)" \
  -d '{"prompt":"what is nixos","route":"Explore"}' | jq
curl -sS http://127.0.0.1:8889/api/aistack/routing/summary | jq
curl -sS "http://127.0.0.1:8889/api/aistack/routing/decisions?limit=10" | jq
```

## Local Orchestrator Notes

The local orchestrator exposes environment overrides for alias-to-profile mapping:

- `AI_LOCAL_FRONTDOOR_DEFAULT_PROFILE`
- `AI_LOCAL_FRONTDOOR_EXPLORE_PROFILE`
- `AI_LOCAL_FRONTDOOR_PLAN_PROFILE`
- `AI_LOCAL_FRONTDOOR_IMPLEMENTATION_PROFILE`
- `AI_LOCAL_FRONTDOOR_REASONING_PROFILE`
- `AI_LOCAL_FRONTDOOR_TOOL_CALLING_PROFILE`
- `AI_LOCAL_FRONTDOOR_CONTINUATION_PROFILE`

These are compatibility knobs for the CLI surface. The coordinator-side JSON
config remains the source of truth for `/v1/orchestrate`, while the env vars
act as local wrapper overrides for `local-orchestrator`.

## Rollback

If a routing change regresses ingress behavior:

1. Revert the route-alias config or handler commit.
2. Re-run `scripts/ai/aq-qa 0`.
3. If a Nix-managed switchboard or coordinator change was deployed, run:

```bash
sudo nixos-rebuild switch --rollback
```
