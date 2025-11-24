# AI-Optimizer (AIDB) Integration

Optional hooks let NixOS-Dev-Quick-Deploy collaborate with the AI-Optimizer
AIDB MCP stack for model-assisted configuration, documentation search, and
system checks. This guide summarizes the workflow and the supporting tooling.

---

## Prerequisites

1. **AI-Optimizer repository**
   ```bash
   git clone ~/Documents/AI-Optimizer
   cd ~/Documents/AI-Optimizer
   ```

2. **AIDB stack running**
   ```bash
   # Example: compose deployment (see AI-Optimizer docs for alternatives)
   docker compose -f docker-compose.new.yml up -d

   # Verify health
   curl http://localhost:8091/health
   ```

3. **Environment variables**
   - `AI_ENABLED=auto|true|false`
   - `AIDB_BASE_URL=http://localhost:8091`
   - `AIDB_PROJECT_NAME=NixOS-Dev-Quick-Deploy`
   - `AIDB_API_KEY=<token>` (optional, adds Authorization header for doc sync)

   Set them in your shell (or export before invoking the deployer) to override
   the defaults defined in `config/variables.sh`.

---

## NixOS Integration Module

The AI-Optimizer repository ships a reusable NixOS module for the MCP service:

```nix
# flake.nix (excerpt)
{
  inputs.ai-optimizer.url = "path:/home/<user>/Documents/AI-Optimizer";

  outputs = { self, nixpkgs, ai-optimizer, ... }:
  let system = "x86_64-linux";
  in {
    nixosConfigurations.devhost = nixpkgs.lib.nixosSystem {
      inherit system;
      modules = [
        ./configuration.nix
        ai-optimizer.nixos/modules/aidb-mcp.nix
      ];
    };
  };
}
```

Combine the module with `sops-nix` secrets for `services.aidb-mcp.envFile`
so that credentials never enter the Nix store. See
`~/Documents/AI-Optimizer/docs/nixos-integration.md` for the full walkthrough.

---

## Documentation Sync Workflow

`scripts/sync_docs_to_ai.sh` pushes Markdown documentation into AIDB so that
semantic search and MCP tools have the full context.

```bash
# Sync all docs (defaults to ./docs and localhost AIDB)
./scripts/sync_docs_to_ai.sh

# Use a custom docs directory / project name
DOCS_DIR=./archive/docs ./scripts/sync_docs_to_ai.sh --project "NixOS-Dev"
```

- Requires `curl` + `jq`
- Aborts if `AIDB_BASE_URL/health` is unreachable
- Sends file contents, checksums, and relative paths for deduplication

Run this script after updating docs or before kicking off large MCP-assisted
tasks so the AI agent sees the latest instructions.

---

## Smart Configuration Generator

`scripts/smart_config_gen.sh` exposes the `lib/ai-optimizer.sh` helpers as a
CLI utility to request configurations or reviews directly from the MCP server.

Examples:

```bash
# Generate configuration from scratch
./scripts/smart_config_gen.sh \
  --description "Enable Docker with NVIDIA GPU support" \
  --output docker-with-gpu.nix

# Use an existing file as context and request a review
./scripts/smart_config_gen.sh \
  --description "Harden SSH + enable WireGuard" \
  --template ./templates/configuration.nix \
  --review
```

The script verifies AI availability, forwards context/description to
`/vllm/nix`, and optionally calls `/vllm/review` on the generated output.

---

## Deployment Flow Enhancements

- `lib/ai-optimizer.sh` exposes `ai_generate_nix_config`, `ai_review_config`,
  `ai_explain_code`, model selection helpers, and AIDB deployment utilities.
- `phases/phase-09-*` uses the hooks to prepare the OS for AI-Optimizer
  without forcing deployment of private assets.
- Environment variables in `config/variables.sh` keep behavior consistent
  across scripts and phases.

---

## Troubleshooting

| Symptom                                      | Resolution |
|----------------------------------------------|------------|
| `AI-Optimizer not available...`              | Ensure `curl $AIDB_BASE_URL/health` succeeds (start containers or update URL). |
| `jq: command not found`                      | Install `jq` (`sudo nix-env -iA nixpkgs.jq` or via `nix-shell`). |
| `Permission denied` when syncing docs        | Ensure the repo is readable and not inside `/root`. |
| Systemd service for aidb-mcp fails to start  | Re-run `nixos-rebuild` with the module snippet above and confirm secrets exist. |

Review additional troubleshooting steps in:
- `docs/HAND-IN-GLOVE-INTEGRATION.md`
- `docs/AI-OPTIMIZER-INTEGRATION-COMPLETE.md`
- `~/Documents/AI-Optimizer/docs/nixos-integration.md`

---

## Next Steps

1. Keep AI-Optimizer images updated (`docker compose pull`).
2. Schedule `scripts/sync_docs_to_ai.sh` after major documentation updates.
3. Experiment with MCP skills (OpenSkills, custom automation) using the synced
   content and smart configuration helper.
4. When ready for declarative MCP deployment, import
   `ai-optimizer.nixos/modules/aidb-mcp.nix` into your flake outputs.

For users who do not have access to the private AI-Optimizer repository (or who
want an isolated testbed), see `docs/LOCAL-AI-STARTER.md` and run
`./scripts/local-ai-starter.sh` to deploy the trimmed stack (TimescaleDB, Redis,
vLLM) plus OpenSkills and MCP templates with public resources only.
