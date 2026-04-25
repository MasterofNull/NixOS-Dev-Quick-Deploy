# Front-Door Routing

Last updated: 2026-04-25

## Purpose

The AI harness exposes a stable human-facing front door so prompts can enter the system through a small set of intent-oriented route aliases instead of requiring callers to know internal switchboard profile names.

Current front door surfaces:

- `POST /v1/orchestrate` on the hybrid coordinator
- `scripts/ai/local-orchestrator`
- Continue/editor traffic routed through switchboard with the `continue-local` lane

## Route Alias Contract

Alias mappings are defined in [config/route-aliases.json](/home/hyperd/Documents/NixOS-Dev-Quick-Deploy/config/route-aliases.json:1) and resolved by [route_aliases.py](/home/hyperd/Documents/NixOS-Dev-Quick-Deploy/ai-stack/mcp-servers/hybrid-coordinator/route_aliases.py:1).

Current canonical mappings:

| Alias | Resolved profile |
|-------|------------------|
| `default` | `default` |
| `Explore` | `default` |
| `Plan` | `default` |
| `Implementation` | `remote-coding` |
| `Reasoning` | `remote-reasoning` |
| `ToolCalling` | `local-tool-calling` |
| `Continuation` | `default` |

Unknown aliases fall back to `default`.

## Request Flow

1. Caller submits a prompt to `/v1/orchestrate` or `local-orchestrator`.
2. The requested route alias is normalized and resolved to a harness profile.
3. The coordinator injects routing metadata into query context:
   - `routed_profile`
   - `route_alias`
4. The request is forwarded into the normal coordinator query path.
5. Downstream routing, hints, memory recall, and switchboard policy still apply.

The `/v1/orchestrate` handler lives in [http_server.py](/home/hyperd/Documents/NixOS-Dev-Quick-Deploy/ai-stack/mcp-servers/hybrid-coordinator/http_server.py:6381).

## Operator Validation

Use these checks when validating front-door routing after repo changes or deploys:

```bash
scripts/ai/aq-qa 0
python3 -m pytest ai-stack/mcp-servers/hybrid-coordinator/tests/test_route_aliases.py
python3 -m pytest ai-stack/mcp-servers/hybrid-coordinator/tests/test_orchestrate_routing.py
curl -sS -X POST http://127.0.0.1:8003/v1/orchestrate \
  -H "Content-Type: application/json" \
  -H "X-API-Key: $(tr -d '\n' < /run/secrets/hybrid_coordinator_api_key)" \
  -d '{"prompt":"what is nixos","route":"Explore"}' | jq
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

These are compatibility knobs for the CLI surface. The coordinator-side JSON config remains the source of truth for `/v1/orchestrate`.

## Rollback

If a routing change regresses ingress behavior:

1. Revert the route-alias config or handler commit.
2. Re-run `scripts/ai/aq-qa 0`.
3. If a Nix-managed switchboard or coordinator change was deployed, run:

```bash
sudo nixos-rebuild switch --rollback
```
