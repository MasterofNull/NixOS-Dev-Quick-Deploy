# Project Design: The Declarative AI-Optimized Development Environment
**Version:** 1.0
**Date:** 2025-12-05
**Author:** Gemini Systems Developer

---

## 1. Executive Summary

This document outlines the architectural design, implementation plan, and theoretical foundations for a world-class, modular, and hardware-agnostic development environment. Built upon the declarative paradigm of NixOS, this system is engineered to host and integrate a sophisticated **AI-Optimizer Stack**.

The primary objective is to create a self-provisioning, self-maintaining ecosystem that dramatically accelerates development workflows across software engineering, integrated circuit (IC) and printed circuit board (PCB) design, and manufacturing. It achieves this by leveraging the existing `NixOS-Dev-Quick-Deploy` framework and augmenting it with a formally defined agentic AI system, inspired by the principles laid out in the project's `AGENTS.md`.

This system is not merely a collection of tools but a cohesive, intelligent environment designed for peak efficiency and seamless human-AI collaboration.

## 2. Influential Research & Leading Experts

This design synthesizes foundational concepts with modern advancements, drawing inspiration from the pioneers and current leaders in their respective fields.

| Domain | Key Influences & Concepts |
| :--- | :--- |
| **Declarative Systems (NixOS)** | The work of **Eelco Dolstra** (creator of Nix) is the cornerstone of this project. We extend his philosophy of reproducibility and reliability by applying it to the entire development lifecycle. The current **NixOS Steering Committee** continues to guide the ecosystem toward stability and innovation, which this project directly leverages. |
| **AI Agentic Systems** | We incorporate principles from the teams at **OpenAI, Google DeepMind, and Anthropic**. The core concept is creating autonomous agents that can reason, delegate, and execute complex tasks. The "AI-Optimizer" is a practical implementation of this research, designed for the specific domain of engineering development. |
| **Virtual Environments** | The philosophy of containerization, popularized by **Docker, Inc.**, and refined in tools like **Podman**, is central to our modularity. We use rootless containers managed declaratively by NixOS to isolate services, ensuring a clean and secure separation between the host system and the AI stack. |
| **CAD/CAM** | We honor the legacy of pioneers like **Ivan Sutherland** (Sketchpad) and **Patrick J. Hanratty** (the "Father of CAD/CAM"). Their vision of interactive, computer-aided design is extended with our AI-Optimizer, which can assist in generating, validating, and refining designs, turning declarative descriptions into physical realities. |
| **IC/PCB Design Automation** | The modern EDA landscape is dominated by firms like **Synopsys, Cadence, and Siemens EDA**. These firms are increasingly using AI for placement and routing. Our system is designed to integrate with and augment these toolchains, using AI agents to manage complex design workflows, run simulations, and analyze results from open-source tools like KiCad. |

## 3. System Architecture

The architecture is a layered, modular system where each component is declaratively defined and independently updatable. It builds directly upon the "hand" and "glove" concept identified in the `README.md`.

![System Architecture Diagram](docs/images/system_architecture.png) 
*(Note: A `canvas-design` skill could be tasked to generate this visual asset).*

### Layer 1: The Foundation (The "Hand")
- **Operating System:** NixOS, providing a reproducible, declarative base.
- **Configuration:** A central `flake.nix` manages the entire system state, including packages, services, and kernel modules. This is derived from the `NixOS-Dev-Quick-Deploy` project.
- **Hardware Abstraction:** NixOS configurations are designed to be hardware-agnostic, with automated detection for GPUs (NVIDIA/AMD), storage drivers (Btrfs/ZFS/VFS), and other peripherals, as already implemented in the deployment scripts.

### Layer 2: Core Services & Environments
- **Virtualization:** Rootless **Podman** is the default container runtime, managed as a NixOS service. It hosts the AI stack's supporting services.
- **Development Environments:** `nix develop` shells are defined in the master `flake.nix`. These provide ephemeral, per-project environments with the exact toolchains required for specific tasks (e.g., `pcb-design`, `rust-dev`, `python-ml`).
- **User Environment:** **Home Manager** declaratively manages user-level packages, dotfiles, and application settings, ensuring perfect consistency across machines.

### Layer 3: The AI-Optimizer Stack (The "Glove")
This is the intelligent core of the system. It is designed to be layered on top of the foundation without requiring modifications to it.

- **Orchestrator Agent:** A primary agent responsible for receiving high-level user goals, decomposing them into sub-tasks, and dispatching them to specialized agents.
- **Skill Library (`.agent/skills/`):** A collection of specialized agents (skills) that perform concrete tasks. Examples:
    - `nixos-deployment`: Interacts with the NixOS configuration.
    - `webapp-testing`: Uses Playwright to validate web UIs.
    - `canvas-design`: Generates diagrams and visual assets.
- **Knowledge Base (AIDB):** A vector database running at `localhost:8091` that serves as the single source of truth for project documentation, past decisions, and scraped knowledge. All agents are trained to query and update the AIDB.
- **Tooling Network (MCPs):** A network of Model Context Protocol servers that provide agents with secure access to external resources and specialized tools (e.g., `mcp-nixos` for package searches, `mcp-github` for repository management).
- **Local Model Runtime:** A local, OpenAI-compatible API server (e.g., Ollama, vLLM as provisioned by `local-ai-starter.sh`) for executing low-cost, parallelizable tasks delegated by the Orchestrator.

## 4. Package & Tooling Manifest

This system integrates a comprehensive suite of tools, all managed declaratively through Nixpkgs and Home Manager. The selection is based on the robust defaults provided by `NixOS-Dev-Quick-Deploy`.

### Core System & Development
- **Languages:** Python 3.13+, Node.js 22, Rust (stable), Go (latest)
- **Editors:** Neovim, VSCodium (with declaratively managed settings and AI extensions)
- **CLI Tools:** `ripgrep`, `fd`, `fzf`, `bat`, `eza`, `jq`, `yq`
- **Nix Ecosystem:** `nix-fast-build`, `statix`, `alejandra`
 - **Dev Shells:** `aidb-dev` (full dev environment), `pcb-design`, `ic-design`, `cad-cam` (engineering shells), and `ts-dev` (TypeScript/Node.js 22 shell geared toward future Python→TypeScript ports).

### AI-Optimizer Stack
- **Containerization:** `podman`, `podman-compose`, `buildah`
- **Local LLMs:** `ollama` (or `vllm`), providing models like Qwen Coder and DeepSeek Coder.
- **Python AI/ML:** `pytorch`, `tensorflow`, `langchain`, `fastapi`, `polars`, `jupyterlab`, `qdrant-client`
- **Agent Tooling:** `aider`, `gpt-cli`, and the rich set of existing agent "skills".

### Engineering & Design
- **IC/PCB Design:** `kicad`, `pcbnew`, `freecad` (for 3D modeling of components and enclosures).
- **CAD/CAM:** `openscad` (for programmatic CAD), `blender` (for general 3D modeling and visualization).
- **Simulation:** `openfoam`, `ngspice` (integrated with KiCad).

## 5. Implementation, Testing & Deployment Plan

The implementation follows the phased approach of the `nixos-quick-deploy.sh` script, which serves as our bootstrap mechanism.

### Phase 1: System Bootstrap
1.  **Execute `nixos-quick-deploy.sh`:** This script provisions the base system (Layer 1) and core services (Layer 2).
2.  **Hardware & Driver Configuration:** The script's existing auto-detection logic for GPUs and storage ensures the NixOS configuration is optimized for the target hardware.
3.  **User Configuration:** Home Manager sets up the user environment, including dotfiles and essential tools.

### Phase 2: AI-Optimizer Stack Deployment
1.  **Scaffold Services:** Execute `scripts/local-ai-starter.sh` to scaffold the Podman Compose project for the AIDB, local model server, and other supporting services.
2.  **Launch Services:** Use `podman-compose up -d` to bring the AI stack online.
3.  **Knowledge Ingestion:** Run `scripts/sync_docs_to_ai.sh` to populate the AIDB with the current project's documentation, creating the initial knowledge base for the agents.

### Phase 3: Testing & Validation
Testing is continuous and automated, adhering to the project's existing best practices.
1.  **System Health Check:** Run `./scripts/system-health-check.sh` to validate that all packages, services, and CLI tools from the base installation are functioning correctly.
2.  **AI Stack Validation:**
    - Query the local model server's health endpoint (`curl http://localhost:8000/health`).
    - Query the AIDB to confirm document ingestion (`curl 'http://localhost:8091/documents?search=deployment'`).
    - Execute a test prompt with an agent skill (e.g., `use the nixos-deployment skill to search for the package 'cowsay'`).
3.  **Workflow Integration Test:** Run `scripts/test_real_world_workflows.sh`. This script will simulate a user request that requires the Orchestrator to delegate tasks to multiple skills, testing the full end-to-end agentic workflow.

### Phase 4: Upgrades & Maintenance
The declarative nature of NixOS makes upgrades atomic and reliable.
- **System & Package Updates:** Run `nix flake update` followed by `sudo nixos-rebuild switch`. If the build fails, the system automatically rolls back to the last known good configuration.
- **AI-Optimizer Updates:** The "glove" (the private AI-Optimizer repository) can be updated independently. Since it communicates with the base system via stable APIs (HTTP for AIDB/LLM, Podman sockets), changes to the agent logic do not require a full system rebuild.

## 6. Language Modernization: Python → TypeScript

The long‑term goal is to evolve this system toward a TypeScript‑first codebase while preserving the existing Python tooling as a “model system” and source of ground truth. The migration will be incremental and agent‑assisted rather than a one‑shot rewrite.

### 6.1 Current Python Surface Area

- Shell‑first architecture with Python as:
  - Embedded helpers in `scripts/system-health-check.sh` and related scripts.
  - AIDB/MCP integration tooling (e.g., `scripts/comprehensive-mcp-search.py`, skill entrypoints).
  - Example skills under `.agent/skills/` that use Python‑based CLIs.
- No monolithic Python service inside this repo – Python is used as a glue/runtime for:
  - Health checks
  - MCP utilities
  - AI/OpenAI client tooling

### 6.2 Target Architecture for TypeScript

- Keep the **NixOS + shell orchestration** as the primary control plane.
- Introduce a **TypeScript service and CLI layer** that mirrors a subset of the Python helpers:
  - A “model module” in Python (well‑factored, typed, and documented).
  - A TypeScript port of that module, sharing:
    - Contract (CLI interface, JSON input/output).
    - Behavior (tested against the same fixtures).
  - Gradual expansion to cover more of the Python utility surface.
- Favor **Node.js 22** + modern TS tooling (ESM, strict mode, eslint, TS server) wired via existing Nix dev shells rather than ad‑hoc `npm install` usage.

### 6.3 Model System Strategy (Python First, Then TS)

1. **Select a reference Python component**  
   - Candidate: the MCP search helper (`scripts/comprehensive-mcp-search.py`) or a small, self‑contained health‑check utility.
   - Criteria:
     - Single responsibility.
     - Pure functions where possible.
     - Clear JSON‑in/JSON‑out interface.
2. **Refine the Python model**  
   - Add type hints and docstrings only where logic is non‑obvious.
   - Ensure it can be driven entirely via CLI arguments and JSON payloads (no hidden globals).
   - Add a minimal test harness (can be a simple `pytest` or `python -m` runner) to lock in behavior.
3. **Define the shared contract**  
   - Document the request/response schema (JSON fields, error shapes) in this repo:
     - Prefer updating an existing doc (e.g., `docs/MCP_SERVERS.md`) with a short “Code Migration APIs” section rather than adding new files.
   - Use that contract as the single source of truth for both Python and TS implementations.
4. **Implement the TypeScript twin (later)**  
   - Create a TS CLI with the same arguments and JSON protocol.
   - Use Node’s ESM + TypeScript with strict type checking.
   - Validate parity by running both implementations against the same fixtures.

### 6.4 MCP & Tooling Integration for Migration

To keep the migration agent‑friendly and reproducible:

- **AIDB + skills**
  - Continue syncing design docs, architecture, and roadmap (including this section) into AIDB so agents can:
    - Discover which Python modules are “migration candidates”.
    - Retrieve contracts and examples for the Python↔TS twin functions.
  - Use the `aidb-knowledge`, `rag-techniques`, and `project-import` skills to:
    - Gather scattered Python usage examples.
    - Track migration decisions and patterns over time.

- **MCP servers**
  - Use existing/planned MCP endpoints as the control plane for migration:
    - `mcp-nixos` – confirm packages, dev shells, and TS tooling are present.
    - `github-mcp` (planned) – manage branches, PRs, and code review comments for migration work.
    - `postgres-mcp` (planned) – store structured migration metadata and audit trails if needed.
  - Define a small set of **migration‑oriented MCP tools** (conceptual for now):
    - `code.search_python_targets` – locate Python functions matching a given contract.
    - `code.summarize_contract` – summarize a Python function’s IO shape into a JSON schema.
    - `code.propose_ts_port` – draft a TS version using the shared contract and examples.
  - These tools can be implemented as thin wrappers over AIDB + local models once we’re ready to code.

### 6.5 Incremental Rollout Plan

- **Phase A – Inventory & Modeling**
  - Inventory Python scripts and inline helpers in this repo.
  - Choose and refactor one “model” Python component to high quality.
  - Document its contract and usage patterns.
- **Phase B – TS Tooling & Dev Shell**
  - Ensure dev environment support for TS:
    - Node.js 22 is already present; TS tooling can be layered in a dedicated dev shell in `templates/flake.nix` (e.g., `ts-dev`) without polluting global `home.packages`.
  - Add brief instructions to `README.md` and `docs/ARCHITECTURE.md` for the TS dev shell once implemented.
- **Phase C – First TS Port**
  - Implement the TS twin of the chosen Python module.
  - Wire it into the orchestration scripts in a feature‑flagged way (e.g., `USE_TS_HELPERS=true`).
  - Keep Python as the fallback until confidence is high.
- **Phase D – Broader Migration**
  - Gradually extend the pattern to additional Python helpers.
  - Keep the system fully functional at every step; no “big bang” rewrite.
  - Use MCP + AIDB to coordinate work across multiple agents and sessions.

This plan keeps the current Python‑based system stable and production‑ready while opening a clear, tool‑assisted path toward a modern TypeScript layer.

### 6.6 Edge‑Optimized Local AI for Laptops and Desktops

For developer laptops and desktops that are used to design edge and embedded systems, the preferred pattern is:

- **Runtime standard:** Treat `llama.cpp` as the default local runtime for on‑device inference, with GGUF‑format SLMs (1–7B class) targeting CPU‑first workloads. Larger models remain opt‑in and are better suited to future server environments.
- **AI profiles:** Introduce a logical `ai_profile` concept, separate from Flatpak profiles, with values such as:
  - `cpu_slim` – very small SLMs, aggressively quantized, minimal disk/RAM footprint.
  - `cpu_full` – a small curated set of stronger SLMs, still CPU‑friendly, for coding and project planning.
  - `off` – disable local models; rely on remote services or keep AI optional.
  These profiles are suggested automatically based on hardware but always remain user‑selectable during the Phase 1/Phase 3 prompts.
- **Model registry:** Back the profiles with a small, declarative model registry (for example `config/edge-model-registry.json`) that records, for each model:
  - An identifier, family, and parameter size.
  - Quantization format (e.g., GGUF Q4/Q5) and intended runtime (`llama_cpp`, `lemonade`).
  - Primary tasks (chat, code, planning) and suitable `ai_profile` values.
  - Expected storage location under the user’s home (for example `~/.local/share/ai-models/...`).
  The registry is mirrored into AIDB so agents can discover available models and choose defaults per task.
- **Quantization and pruning:** Treat quantization and pruning as **offline pipelines** rather than ad‑hoc commands:
  - Start with community‑provided GGUF builds for robustness.
  - Later, add optional pipelines (described in `docs/AI_INTEGRATION.md`) that can apply SmoothQuant/OmniQuant/AWQ and SparseGPT‑style pruning to locally‑stored base models and then update the registry with metadata such as bit‑width and sparsity.
- **Agent‑assisted selection:** Use AIDB + the AI‑Optimizer stack to:
  - Capture project goals and constraints (hardware, latency expectations, domains) in a “project charter” document.
  - Suggest an `ai_profile` and a small set of models from the registry per project.
  - Allow users to override choices and experiment, while agents continue to respect the registry as the single source of truth.

The concrete wiring for `ai_profile` flags, the edge model registry, and containerized inference services lives in the implementation documents and Nix templates (`docs/AI_INTEGRATION.md`, `docs/DEVELOPMENT-ROADMAP.md`, and `templates/local-ai-stack/`). The actual LLM runtimes (such as `llama.cpp` or Lemonade) are developed and maintained as separate Podman/Docker stacks; this project only provides optional scaffolding and integration hooks, not the containers themselves. This section defines the long‑term strategy so that future changes remain aligned with the edge‑optimized, agent‑friendly design.

## 7. Conclusion

This project design formalizes a robust and highly advanced development environment. By combining the declarative power of NixOS with a modular, agentic AI system, we create an ecosystem that is not only reproducible and reliable but also intelligent and proactive.

This system will serve as a force multiplier, empowering developers to tackle complex challenges in software, hardware design, and manufacturing with unprecedented speed and efficiency. It is a living system, designed to evolve alongside the rapid advancements in AI, ensuring it remains at the cutting edge for years to come.
