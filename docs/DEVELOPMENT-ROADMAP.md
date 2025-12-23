# NixOS-Dev-Quick-Deploy – Development Roadmap & Standards

**Version:** 1.0  
**Date:** 2025-12-05  
**Scope:** Roadmap, code structure, and development rules for improving organization, readability, and maintainability of the NixOS-Dev-Quick-Deploy system.

This document turns the high-level design in `SYSTEM_PROJECT_DESIGN.md` into a concrete, persistent roadmap and reference for day-to-day development.

---

## 1. High-Level Goals

- Keep the system declarative, modular, and hardware-agnostic.
- Make `nixos-quick-deploy.sh` the single orchestration entrypoint, with all behavior flowing through well-defined libraries and phases.
- Ensure the AI-Optimizer stack (“glove”) layers cleanly on top of the NixOS foundation (“hand”) with stable, documented interfaces.
- Maintain a small, predictable set of directories and documents that are easy for humans and agents to navigate.

---

## 2. Roadmap

### Phase 1 – Repo & Documentation Cleanup

- Treat `SYSTEM_PROJECT_DESIGN.md` and `README.md` as the primary design/overview documents.
- Avoid adding new top-level status/fix files unless they are long-lived; prefer `docs/` for new documentation.
- When a status/fix/migration document has been incorporated into stable docs, move it to `archive/` or `docs/archive/`.
- Add or maintain:
  - `docs/ARCHITECTURE.md` – concise mapping of the “hand/glove” design to the actual repo layout.
  - This document, `docs/DEVELOPMENT-ROADMAP.md`, as the single persistent roadmap.

### Phase 2 – Code Structure Hardening

- Enforce a clear boundary between:
  - `nixos-quick-deploy.sh` (entrypoint)
  - `lib/` (shared logic)
  - `phases/` (deployment phases)
  - `scripts/` (user-facing tools)
  - `templates/` (configuration templates)
- Keep configuration data-only under `config/` (no functions).
- Ensure templates under `templates/` are canonical and not duplicated elsewhere.

### Phase 3 – Quality & Testing

- Standardize on `lib/logging.sh` and `lib/error-handling.sh` for all shell components.
- Use `lib/state-management.sh` as the sole authority for tracking phase state.
- Consolidate and document the main validation scripts:
  - `scripts/system-health-check.sh`
  - `scripts/test_services.sh`
  - `scripts/test_real_world_workflows.sh`
- Optionally create `scripts/run-all-checks.sh` to run all of the above in one step.

### Phase 4 – AI-Optimizer Stack Integration

- Treat the AI-Optimizer stack as a separate but tightly integrated layer:
  - AIDB at `localhost:8091`
  - Local LLM runtime (OpenAI-compatible container such as llama.cpp or llama.cpp; vLLM reserved for dedicated servers)
  - MCP servers and skills
- Organize AI-related assets:
  - `templates/local-ai-stack/`
  - `scripts/local-ai-starter.sh`
  - `scripts/sync_docs_to_ai.sh`
  - `scripts/bootstrap_aidb_data.sh`
- Provide a single, documented CLI wrapper (`scripts/ai-stack-manage.sh`) to operate the AI stack.
- Document AI integration details in `docs/AI_OPTIMIZER_STACK.md` (or `AI_INTEGRATION.md` if preferred).
- For laptops and desktops, standardize on an edge-first LLM strategy:
  - Prefer `llama.cpp` with GGUF-format SLMs as the default local runtime.
  - Introduce a logical `ai_profile` concept (`cpu_slim`, `cpu_full`, `off`) separate from Flatpak profiles.
  - Back these profiles with a small model registry file (for example `config/edge-model-registry.json`) that can also be mirrored into AIDB for agent discovery.
 - Use a simple `AI_STACK_PROFILE` switch (`personal`, `guest`, `none`) plus distinct `AIDB_PROJECT_NAME` values so personal stacks and data are cleanly separated from guest/school deployments.

### Phase 5 – Continuous Improvements

- Regularly prune obsolete or duplicated documentation.
- Refine phases and libraries as new workflows emerge, keeping functions focused and reusable.
- Introduce small, targeted improvements rather than large “big bang” refactors.
 - Periodically move time-bound status/fix reports from the repository root into `archive/` or `docs/archive/` once their content is reflected in `README.md`, `SYSTEM_PROJECT_DESIGN.md`, or stable docs, so the root stays clean and aligned with the intent of `AGENTS.md`.

---

## 3. Target Code & Config Structure

### 3.1 Root Layout (Desired State)

- `nixos-quick-deploy.sh` – **single entrypoint** orchestrating the 8-phase deployment.
- `config/` – configuration data:
  - `variables.sh` – global paths, filenames, feature toggles.
  - `defaults.sh` – default values that can be overridden.
- `lib/` – reusable shell libraries:
  - `colors.sh`, `logging.sh`, `error-handling.sh`, `state-management.sh`, `user-interaction.sh`,
    `validation.sh`, `retry.sh`, `backup.sh`, `secrets.sh`, `gpu-detection.sh`, `python.sh`,
    `nixos.sh`, `packages.sh`, `home-manager.sh`, `user.sh`, `config.sh`, `tools.sh`,
    `service-conflict-resolution.sh`, `finalization.sh`, `reporting.sh`, `common.sh`.
- `phases/` – phase scripts:
  - `phase-01-system-initialization.sh`
  - `phase-02-system-backup.sh`
  - `phase-03-configuration-generation.sh`
  - `phase-04-pre-deployment-validation.sh`
  - `phase-05-declarative-deployment.sh`
  - `phase-06-additional-tooling.sh`
  - `phase-07-post-deployment-validation.sh`
  - `phase-08-finalization-and-report.sh`
  - Optional: `phase-09-ai-optimizer-prep.sh`, `phase-09-ai-model-deployment.sh`
- `scripts/` – user-facing helpers:
  - Health checks, AI stack control, MCP setup, troubleshooting helpers.
- `templates/` – Nix and AI templates:
  - `flake.nix`, `flake.lock`, `home.nix`, `configuration.nix`, `python-overrides.nix`
  - `local-ai-stack/`, `nixos-improvements/`, `mcp-server/`, `mcp-db-setup/`.
- `docs/` – stable documentation:
  - Architecture, deployment guides, AI integration, tool inventory.
- `archive/` – time-bound or superseded docs, after they are reflected in `docs/` and `README.md`.

### 3.2 `config/` Rules

- Keep `config/variables.sh` and `config/defaults.sh` **data-only**:
  - Variable assignments, readonly constants, simple derived values.
  - No functions or side effects.
- Group configuration by domain with clear comments:
  - Logging and paths
  - State management
  - Backup and rollback
  - AI stack defaults (AIDB URL, model server URL, default MCP config paths)
- All paths and filenames needed across libraries should be defined here.

### 3.3 `lib/` Rules

- One concern per file:
  - Logging, error handling, state, GPU detection, secrets, backup, NixOS integration, etc.
- All user-visible text should go through `print_*` helpers.
- All logs must use `log` from `lib/logging.sh`.
- No `exit` calls in library functions:
  - Functions should return non-zero on failure; the caller decides whether to abort.
- Cross-phase behaviors (e.g., backup flow, GPU detection, AI prep) belong in `lib/`, not duplicated in multiple phases.

### 3.4 `phases/` Rules

- File naming: `phase-0N-slug.sh` where `slug` matches `get_phase_name` in `nixos-quick-deploy.sh`.
- Each phase script should:
  - Be small and linear, delegating real work to `lib/` functions.
  - Use `log` and `print_*` for messaging.
  - Avoid direct manipulation of state files; use `lib/state-management.sh` helpers (`is_step_complete`, `mark_step_complete`, etc.).
- Optional AI phases:
  - Follow the same conventions and are triggered via CLI flags (`--with-ai-prep`, `--with-ai-model`, `--with-ai-stack`).

### 3.5 `scripts/` Rules

- Scripts in `scripts/` are CLI tools, not libraries:
  - Parse arguments.
  - Call into `lib/` functions or Nix commands.
  - Exit with clear status codes.
- Naming conventions:
  - `system-*` – system operations and checks.
  - `ai-*` – AI stack operations.
  - `mcp-*` – MCP-related tooling.
  - `test-*` – tests and validation.
- For complex behavior, move shared logic to `lib/` and keep the script as a thin wrapper.
- New scripts should use:
  - `#!/usr/bin/env bash`
  - `set -Eeuo pipefail`

### 3.6 `templates/` Rules

- `templates/flake.nix` is the canonical Nix flake template for the base system and development shells.
- `templates/home.nix`, `templates/configuration.nix`, and `templates/python-overrides.nix` should remain focused and composable.
- NixOS improvements:
  - Place focused modules under `templates/nixos-improvements/` with descriptive names (`gpu-tuning.nix`, `ai-services.nix`, etc.).
- AI templates:
  - `templates/local-ai-stack/` contains the Podman compose or Nix definitions for AIDB and the local model server.
  - `templates/mcp-server/`, `templates/mcp-db-setup/` provide starting points for MCPs and databases.

---

## 4. AI-Optimizer Stack (“Glove”) Structure

### 4.1 Components

- **AIDB Knowledge Base**
  - HTTP API at `http://localhost:8091`.
  - Holds project docs, design decisions, tool inventories, and session summaries.
- **Local Model Runtime**
  - Ollama or vLLM, exposed via an OpenAI-compatible HTTP API.
  - Handles parallelizable tasks delegated by higher-level agents.
- **MCP Servers & Skills**
  - `mcp-nixos` for NixOS and Home Manager package search.
  - Planned additions: `postgres-mcp`, `github-mcp`, `SecureMCP`, `vulnicheck`, etc.
  - Skills in `.agent/skills/` (symlinked to `.claude/skills/`).

### 4.2 Files and Scripts

- `templates/local-ai-stack/` – Podman Compose or service templates for:
  - AIDB.
  - Local model server.
  - Supporting services (if any).
- `scripts/local-ai-starter.sh` – scaffolds the AI stack environment.
- `scripts/sync_docs_to_ai.sh` – pushes project docs into AIDB.
- `scripts/bootstrap_aidb_data.sh` – optional script to seed AIDB with initial data.
- Suggested wrapper:
  - `scripts/ai-stack-manage.sh` to expose clear subcommands:
    - `up`, `down`, `sync`, `status`.

### 4.3 Engineering & Design Tooling

- Home Manager provides a rich engineering toolchain via `home.packages` in `templates/home.nix`, including:
  - PCB & electronics: `kicad`, `ngspice`.
  - Mechanical/CAD: `freecad`, `openscad`, `blender`.
  - Digital IC/FPGA: `yosys`, `nextpnr`, `iverilog`, `gtkwave`.
- `templates/flake.nix` exposes dedicated dev shells for these domains:
  - `pcb-design` – KiCad, FreeCAD, OpenSCAD, ngspice.
  - `ic-design` – Yosys, nextpnr, Icarus Verilog, GTKWave, ngspice.
  - `cad-cam` – FreeCAD, OpenSCAD, Blender.
  - `ts-dev` – TypeScript / Node.js 22 tooling (TypeScript, ts-node, TS language server, ESLint) for future Python→TypeScript migration work.
- The **minimal** Flatpak profile selected during Phase 1 maps to a **slim** engineering profile in `home.nix` (omits heavy PCB/CAD/IC packages), while `core` and `ai_workstation` keep the full engineering toolchain enabled. Dev shells remain available in all profiles.

### 4.3 Integration Points

- Agent tools should:
  - Query AIDB for documentation and context.
  - Use MCP servers for structured operations (Nix search, GitHub ops, DB operations).
  - Prefer local models for low-cost, parallel tasks when appropriate.

---

## 5. Concrete Examples

### 5.1 Example: New AI Preparation Phase

`phases/phase-09-ai-optimizer-prep.sh`:

```bash
#!/usr/bin/env bash

phase_09_ai_optimizer_prep() {
    print_section "Phase 9: AI-Optimizer Preparation"
    log INFO "Starting AI-Optimizer preparation phase"

    # Ensure Podman is available and configured
    ensure_podman_ready

    # Scaffold AI stack templates (Podman compose, config files)
    scaffold_ai_stack_templates

    # Sync docs into AIDB
    sync_docs_to_aidb

    log INFO "Phase 9 completed"
    return 0
}
```

All real work (`ensure_podman_ready`, `scaffold_ai_stack_templates`, `sync_docs_to_aidb`) should be implemented in a dedicated `lib/ai-stack.sh`.

### 5.2 Example: AI Nix Module

`templates/nixos-improvements/ai-services.nix`:

```nix
{ config, pkgs, ... }:
{
  services.aidb = {
    enable = true;
    package = pkgs.aidb-server;
    dataDir = "/var/lib/aidb";
  };

  services.local-llm = {
    enable = true;
    package = pkgs.ollama;
  };
}
```

This keeps AI services declarative and aligned with the “glove” concept.

### 5.3 Example: AI Stack CLI Wrapper

`scripts/ai-stack-manage.sh`:

```bash
#!/usr/bin/env bash
set -Eeuo pipefail

COMPOSE_FILE="templates/local-ai-stack/compose.yml"

case "${1:-}" in
  up)
    podman-compose -f "$COMPOSE_FILE" up -d
    ;;
  down)
    podman-compose -f "$COMPOSE_FILE" down
    ;;
  sync)
    scripts/sync_docs_to_ai.sh
    ;;
  *)
    echo "Usage: $0 {up|down|sync}" >&2
    exit 1
    ;;
esac
```

This provides a single, discoverable entrypoint for AI stack operations.

---

## 6. Development Rules (Project-Specific)

### 6.1 Shell Code Rules

- Use Bash strict mode:
  - In libraries and `nixos-quick-deploy.sh`: at minimum `set -o pipefail`.
  - In new standalone scripts: `set -Eeuo pipefail`.
- Never call `exit` from library functions:
  - Return non-zero and let the caller decide.
- Use `log` for logging, `print_*` for user-visible messages.
- Keep functions under ~50 lines where practical; if longer, consider splitting into helpers.
- No debug `echo`, `set -x`, or stray `printf` in committed code.

### 6.2 Nix Code Rules

- One module per logical concern (system services, AI stack, user shells, hardware tweaks).
- Use clear, descriptive option sets and defaults instead of ad-hoc configuration flags.
- Prefer declarative service definitions over imperative scripts for long-running services.
- Keep host-specific customizations in dedicated modules that can be included or excluded explicitly.

### 6.3 Documentation Rules

- Root directory:
  - Keep limited to core docs: `README.md`, `AGENTS.md`, `SYSTEM_PROJECT_DESIGN.md`, and a small number of essential status/system files.
- `docs/`:
  - Use focused, well-named documents (e.g., `ARCHITECTURE.md`, `AI_INTEGRATION.md`, `AVAILABLE_TOOLS.md`).
  - Avoid versioned filenames like `*_V2_FINAL.md`; update the existing document instead.
- `archive/` and `docs/archive/`:
  - Move time-bound or superseded docs here once their content has been integrated into stable docs.

### 6.4 Testing & Validation Rules

- Use the built-in workflows wherever possible:
  - `./nixos-quick-deploy.sh --test-phase N` for phase-level testing.
  - `scripts/system-health-check.sh` for system-wide validation.
  - `scripts/test_real_world_workflows.sh` for end-to-end checks.
- For new phases or significant new `lib/` functions:
  - Add at least a basic smoke test path (e.g., a CLI flag, a test script entry, or test mode).
- Keep tests fast and focused to encourage regular use.

---

## 7. Working With This Roadmap

- Before adding new code:
  - Check existing patterns in `lib/`, `phases/`, `scripts/`, and `templates/`.
  - Ensure your change fits within the structure and rules outlined here.
- When updating behavior:
  - Prefer extending existing libraries or phases rather than adding new entrypoints.
  - Update relevant docs (`README.md`, `docs/ARCHITECTURE.md`, this file) as you go.
- Periodically:
  - Review this roadmap against the actual repo state.
  - Adjust phases and rules as the system evolves, keeping the document as the living source of truth for system organization and development practices.
