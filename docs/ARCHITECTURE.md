# NixOS-Dev-Quick-Deploy – System Architecture

**Version:** 1.0  
**Date:** 2025-12-05  
**Source Design:** `SYSTEM_PROJECT_DESIGN.md`, `docs/HAND-IN-GLOVE-INTEGRATION.md`, `docs/AI_INTEGRATION.md`

This document is an implementation-focused view of the architecture described in `SYSTEM_PROJECT_DESIGN.md`. It maps the conceptual layers (“hand” and “glove”) to concrete files, directories, and workflows in this repository.

---

## 1. Layered Architecture Overview

The system is organized into three primary layers:

- **Layer 1 – Foundation (“Hand” base):** NixOS host, flake, system services.
- **Layer 2 – Core Services & Dev Environments:** Containers, Home Manager, dev shells.
- **Layer 3 – AI-Optimizer Stack (“Glove”):** AIDB, local models, MCP servers and skills.

The guiding principle: the “hand” is fully functional on its own; the “glove” is an optional, tightly integrated enhancement that never breaks the base.

---

## 2. Layer 1 – Foundation (The “Hand”)

**Purpose:** Provide a reproducible, hardware-agnostic NixOS base and a single entrypoint to configure it.

**Key components**

- Entry script:
  - `nixos-quick-deploy.sh` – 8-phase modular deployment orchestrator.
- Configuration:
  - `config/variables.sh` – global paths, environment flags, state files.
  - `config/defaults.sh` – default values and toggles.
- Nix templates:
  - `templates/flake.nix`, `templates/flake.lock`
  - `templates/configuration.nix`
  - `templates/home.nix`
  - `templates/python-overrides.nix`
- Shell libraries (`lib/`):
  - Core infrastructure:
    - `logging.sh`, `colors.sh`, `error-handling.sh`, `state-management.sh`
    - `user-interaction.sh`, `validation.sh`, `retry.sh`
  - System & deployment logic:
    - `backup.sh`, `secrets.sh`, `gpu-detection.sh`
    - `python.sh`, `nixos.sh`, `packages.sh`, `home-manager.sh`, `user.sh`
    - `config.sh`, `tools.sh`, `service-conflict-resolution.sh`
    - `finalization.sh`, `reporting.sh`, `common.sh`

**Phase-based deployment**

`nixos-quick-deploy.sh` orchestrates the following phases (see `phases/`):

1. **System Initialization** – validate requirements, install temporary tools.
2. **System Backup** – create rollback points and backups.
3. **Configuration Generation** – generate NixOS and Home Manager configs.
4. **Pre-deployment Validation** – check configurations and conflicts.
5. **Declarative Deployment** – apply NixOS and Home Manager configs.
6. **Additional Tooling** – install non-declarative extras (editor tools, etc.).
7. **Post-deployment Validation** – verify services and packages.
8. **Finalization & Report** – summarize results, write reports.

Each phase is implemented as `phases/phase-0N-*.sh` and calls into `lib/` for all non-trivial logic.

---

## 3. Layer 2 – Core Services & Development Environments

**Purpose:** Provide isolated development environments and supporting services on top of the base system.

**Key concepts**

- **Rootless containers** (Podman):
  - Managed by NixOS services (templates for container-based services live under `templates/` and `templates/local-ai-stack/`).
  - Used for AIDB, local LLM runtimes, and other auxiliary services.
- **Development shells** (`nix develop`):
  - Defined in `templates/flake.nix`.
  - Examples:
    - `pcb-design` – KiCad, FreeCAD, OpenSCAD, ngspice.
    - `ic-design` – Yosys, nextpnr, Icarus Verilog, GTKWave, ngspice.
    - `cad-cam` – FreeCAD, OpenSCAD, Blender.
    - `ts-dev` – TypeScript/Node.js 22 tooling (TypeScript, ts-node, ESLint, TS language server).
  - Detailed engineering toolchains and workflows: see `docs/ENGINEERING-ENVIRONMENT.md`.
- **User environment**:
  - Home Manager configuration via `templates/home.nix` and associated modules.
  - Dotfiles, editor configs, and CLI tools managed declaratively.

**Supporting scripts**

- `scripts/system-health-check.sh` – validates packages, services, and system health.
- `scripts/test_services.sh` – focused service checks.
- `scripts/test_real_world_workflows.sh` – end-to-end workflow tests.

These scripts rely on `lib/` for logging, validation, and state where possible.

---

## 4. Layer 3 – AI-Optimizer Stack (The “Glove”)

**Purpose:** Provide intelligent automation, documentation search, and model-assisted configuration on top of Layers 1 and 2, without coupling to private code.

**Core components**

- **AIDB Knowledge Base**
  - Runs as a service (typically in a container).
  - Accessible at `http://localhost:8091`.
  - Stores project docs, decisions, and tool inventories for agent consumption.
- **Local Model Runtime**
  - OpenAI-compatible container runtimes (for example Lemonade or llama.cpp), exposed via HTTP APIs. Heavier GPU-centric runtimes such as vLLM are reserved for dedicated server environments rather than laptop/desktop defaults.
  - Executes code analysis, documentation extraction, and other batch tasks.
- **MCP Servers**
  - `mcp-nixos` – NixOS/Home Manager package and configuration search.
  - Planned additions: `postgres-mcp`, `github-mcp`, `SecureMCP`, `vulnicheck`, etc.
  - Configuration templates:
    - `templates/mcp-config-template.json`
    - `templates/mcp-server-template.py`
    - `templates/mcp-server-template.ts`
    - `templates/mcp-db-setup/`, `templates/mcp-server/`
- **Skills**
  - Stored under `.agent/skills/` (symlinked as `.claude/skills/`).
  - Include `nixos-deployment`, `webapp-testing`, `aidb-knowledge`, `ai-service-management`, etc.

**Integration artifacts**

- Templates:
  - `templates/local-ai-stack/` – Podman compose or service definitions for AIDB and the local model server.
- Scripts:
  - `scripts/local-ai-starter.sh` – scaffolds and/or launches the local AI stack.
  - `scripts/sync_docs_to_ai.sh` – syncs docs into AIDB.
  - `scripts/bootstrap_aidb_data.sh` – initial AIDB seeding.
  - `scripts/smart_config_gen.sh` – AI-assisted configuration helper.
  - MCP helpers under `scripts/mcp-*` where applicable.
- Libraries:
  - `lib/ai-optimizer.sh` – helpers for AI-powered config generation, review, and explanation (where present).

**Hand-in-glove contract**

- Phase 1–8 never depend on private AI-Optimizer code.
- Phase 9 (optional) prepares:
  - Shared directories under `~/.local/share/ai-optimizer` and `~/.config/ai-optimizer`.
  - Container runtime (Podman/Docker) and ports.
  - GPU acceleration support (e.g., NVIDIA container toolkit).
- AI-Optimizer can be installed and updated independently in a private repo, as described in:
  - `docs/HAND-IN-GLOVE-INTEGRATION.md`
  - `docs/AI_INTEGRATION.md`

---

## 5. Directory Map (Concept → Implementation)

| Conceptual Layer | Purpose                             | Directory / Files                       |
|------------------|-------------------------------------|-----------------------------------------|
| Foundation       | OS, flake, entrypoint               | `nixos-quick-deploy.sh`, `config/`, `templates/flake.nix`, `templates/configuration.nix` |
| Libraries        | Reusable logic                      | `lib/`                                  |
| Phases           | Stepwise deployment                 | `phases/phase-0N-*.sh`                  |
| Dev Environments | Toolchains & user setup             | `templates/home.nix`, dev shells via `templates/flake.nix` |
| Services         | System & container services         | NixOS modules in templates (`templates/nixos-improvements/*.nix` including `podman.nix`), `scripts/system-health-check.sh`, `scripts/test_services.sh` |
| AI Stack         | AIDB, local LLM, MCP                | `templates/local-ai-stack/`, `scripts/local-ai-starter.sh`, `scripts/sync_docs_to_ai.sh`, `lib/ai-optimizer.sh`, `config/edge-model-registry.json` |
| MCP & Skills     | Tooling for agents                  | `templates/mcp-*`, `.agent/skills/`     |
| Documentation    | Design, guides, reference           | `README.md`, `SYSTEM_PROJECT_DESIGN.md`, `docs/*.md`, `archive/` |

---

## 6. Extension Points

**Adding a new phase**

- Create `phases/phase-0N-new-slug.sh`.
- Add a mapping for phase N in `get_phase_name`, `get_phase_description`, and `get_phase_dependencies` in `nixos-quick-deploy.sh`.
- Implement behavior by calling `lib/` functions; avoid duplicating logic from other phases.

**Adding a new service or module**

- Add a focused Nix module under `templates/nixos-improvements/` (e.g., `ai-services.nix`, `gpu-tuning.nix`).
- Wire it into `templates/flake.nix` or `templates/configuration.nix` via imports.

**Adding AI/MCP capabilities**

- Extend or add MCP templates under `templates/mcp-*`.
- Add or update skills under `.agent/skills/`.
- Document any new endpoints or workflows in `docs/AI_INTEGRATION.md` or a dedicated AI doc.

---

## 7. How to Use This Document

- When making structural changes:
  - Verify that they fit one of the layers above.
  - Keep the mapping between conceptual layers and directories up to date.
- When onboarding:
  - Read `README.md` → `SYSTEM_PROJECT_DESIGN.md` → this file.
  - Use `docs/DEVELOPMENT-ROADMAP.md` for step-by-step improvements and rules.
- When adding new features:
  - Choose the correct layer and directory.
  - Update this document and the roadmap if the architecture changes in a meaningful way.
