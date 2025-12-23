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
   - `AI_PROFILE=cpu_slim|cpu_full|off` (optional, declares the local edge AI profile for this host)
   - `AI_STACK_PROFILE=personal|guest|none` (optional, declares which containerized AI stack layout this host should favor)

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

For local-only stacks created by `scripts/local-ai-starter.sh`, you can also
use the convenience wrapper:

```bash
# From the NixOS-Dev-Quick-Deploy repo root
./scripts/ai-stack-manage.sh up        # Start local AI stack
./scripts/ai-stack-manage.sh status    # Show container status
./scripts/ai-stack-manage.sh sync      # Sync docs/ into AIDB
```

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
`/llama-cpp/nix` (falling back to `/vllm/nix` for older stacks), and optionally
calls `/llama-cpp/review` on the generated output.

---

## Deployment Flow Enhancements

- `lib/ai-optimizer.sh` exposes `ai_generate_nix_config`, `ai_review_config`,
  `ai_explain_code`, model selection helpers, and AIDB deployment utilities.
- `phases/phase-09-*` uses the hooks to prepare the OS for AI-Optimizer
  without forcing deployment of private assets.
- Environment variables in `config/variables.sh` keep behavior consistent
  across scripts and phases.

---

## Edge LLM Runtime Strategy (Laptops and Desktops)

For developer laptops and desktops that host the NixOS-Dev-Quick-Deploy system, the preferred local LLM pattern is:

- **Runtime standard:** Use `llama.cpp` (or a similar OpenAI-compatible runtime such as llama.cpp) as the default on-device runtime for SLMs in GGUF format, targeting CPU-first inference. These runtimes are expected to be provided by separately developed Podman/Docker container stacks (for example those scaffolded by `templates/local-ai-stack/`), not baked into the base NixOS system. Larger GPU-heavy runtimes (such as vLLM) are reserved for future dedicated servers and are not required for day-to-day edge development.
- **AI profiles:** Introduce a logical `ai_profile` concept (separate from Flatpak profiles) with values such as:
  - `cpu_slim` – very small SLMs, aggressively quantized, minimal resource usage.
  - `cpu_full` – a curated set of stronger SLMs suitable for coding assistants and project planning.
  - `off` – local models disabled; AI remains optional or remote-only.
  When implemented, these profiles will be suggested based on detected hardware but always remain user-selectable during Phase 1/3 prompts.
- **Model registry:** Maintain a small, declarative registry of edge-optimized models in `config/edge-model-registry.json`. Each entry should record:
  - Model id, family, and parameter size.
  - Quantization format (e.g., GGUF Q4/Q5) and intended runtime (`llama_cpp`, `llama-cpp`).
  - Primary tasks (chat, code, planning) and the `ai_profile` values it serves well.
  - Storage path under the user’s home directory (for example `~/.local/share/ai-models/...`).
  The registry can be mirrored into AIDB so agents can discover available models and choose sensible defaults per task and device.
- **Quantization and pruning pipelines:** Quantization (SmoothQuant, OmniQuant, AWQ, etc.) and pruning (SparseGPT-style) should be treated as offline pipelines:
  - Start by consuming pre-quantized GGUF models for stability.
  - Gradually add optional scripts under `scripts/` (for example a future `model-prepare` helper) that can take a base model, apply a quantization/pruning backend, and then update the registry and AIDB metadata.

These design rules keep laptops/desktops aligned with industry trends toward small, specialized models while avoiding a hard dependency on any single quantization tool or server runtime.

---

## Personal vs Guest / School Installations

To keep environments clear across personal laptops/desktops and guest or school machines, use separate stack profiles and AIDB projects:

- **Personal machines**
  - Set `AI_STACK_PROFILE=personal` (default) and keep `AIDB_PROJECT_NAME=NixOS-Dev-Quick-Deploy` (or a personal variant).
  - Clone and manage your own AI-Optimizer repo and any private Podman stacks under `~/Documents/` and `~/.local/share/ai-optimizer/`.
  - Use `config/edge-model-registry.json` to describe which models your personal stacks expose for each `AI_PROFILE`.
- **Guest / school machines**
  - Set `AI_STACK_PROFILE=guest` and choose a distinct `AIDB_PROJECT_NAME` such as `NixOS-Dev-Quick-Deploy-Guest`.
  - Use `scripts/local-ai-starter.sh` to scaffold neutral, local Podman stacks (for example `~/Documents/local-ai-stack/`) without cloning your private AI-Optimizer repo or copying personal data.
  - Maintain a separate edge model registry file and data roots so no personal models, documents, or secrets are referenced.
- **No local stack**
  - Set `AI_STACK_PROFILE=none` and leave local stacks disabled; NixOS-Dev remains a clean base system with no containerized AI services attached.

In all cases, the base NixOS-Dev-Quick-Deploy configuration stays the same; only environment variables, AIDB project names, and external Podman stack directories change. This makes it safe to reuse the same repo for personal and shared deployments without leaking private data or creating confusing environments.

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

## Project Kickoff and Goal-Setting Workflow

To make the most of the AI-Optimizer stack and AIDB for software and research projects, use a repeatable kickoff flow:

1. **Start the local AI stack**
   - From this repository:
     - `./scripts/ai-stack-manage.sh up` (or `./scripts/local-ai-starter.sh` for the standalone stack).
   - Verify AIDB is healthy with `curl "$AIDB_BASE_URL/health"` (defaults to `http://localhost:8091/health`).
2. **Sync the latest documentation**
   - Run `./scripts/sync_docs_to_ai.sh --project "NixOS-Dev-Quick-Deploy"` from the repo root.
   - This ensures agents see the current architecture, roadmap, and edge AI strategy (`SYSTEM_PROJECT_DESIGN.md`, `docs/ARCHITECTURE.md`, `docs/DEVELOPMENT-ROADMAP.md`, `docs/ENGINEERING-ENVIRONMENT.md`, and this file).
3. **Capture project goals and constraints**
   - Use an AI-Optimizer skill (for example a “project kickoff” or “requirements gathering” skill) to:
     - Ask the user about goals, target domains (code, CAD/EDA, research), hardware constraints, and latency expectations.
     - Write a structured “project charter” document into AIDB with metadata such as:
       - `type = "project-charter"`
       - `project = "NixOS-Dev-Quick-Deploy"` (or a more specific project name)
       - `tags = ["edge-ai", "llama.cpp", "coding-assistant"]`
4. **Propose AI profiles and models**
   - Based on the charter and the host hardware, an agent can:
     - Suggest an `ai_profile` (`cpu_slim`, `cpu_full`, or `off`) for this host.
     - Select a small set of models from `config/edge-model-registry.json` that fit the profile and tasks (for example, a code-focused SLM plus a planning/coordination SLM).
   - The suggestions should be logged back into AIDB as a “model-selection” document so future agents and sessions can reuse the decision.
5. **Iterate, but keep the registry authoritative**
   - When experimenting with new models or quantization methods, update the registry file and sync a short note into AIDB (for example `type = "model-experiment"`).
   - Agents should treat the registry + AIDB entries as the authoritative view of which models are available and recommended on each device.

This workflow makes it easy for multiple AI agents and tools to coordinate around the same project goals, hardware constraints, and model choices without hard-coding any specific model names into the NixOS-Dev-Quick-Deploy scripts.

---

## Quick Host Summary Helper

To see how a particular host is configured from the AI stack’s perspective:

```bash
cd ~/NixOS-Dev-Quick-Deploy
./scripts/ai-env-summary.sh
```

This prints the current `AI_PROFILE`, `AI_STACK_PROFILE`, AIDB URL/project name, and the status of `config/edge-model-registry.json` so you can quickly confirm whether a machine is acting as a personal, guest, or non‑AI host and how many edge models are declared for it.

---

## Edge Model Registry Validation

To validate and summarize the edge model registry:

```bash
cd ~/NixOS-Dev-Quick-Deploy
./scripts/edge-model-registry-validate.sh          # Uses config/edge-model-registry.json
./scripts/edge-model-registry-validate.sh path/to/registry.json
```

This checks JSON syntax and required fields (`id`, `runtime`, `backend`, `ai_profiles`) for each entry and reports a non-zero exit code when structural issues are found. Use it any time you edit the registry so agents and tools can rely on it as a clean source of truth.

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
