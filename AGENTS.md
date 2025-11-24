# AI Agents & Tooling Overview

## Design Philosophy

- **Three Pillars (borrowed from Hyper-NixOS)**  
  1. **Ease of Use** – Reduce friction for both the orchestrator (Claude Code / human engineer) and the delegated local agents.  
  2. **Security & Organization** – Keep agent workloads isolated, never ship private repositories, and require explicit opt-in for any privileged action.  
  3. **Learning Ethos** – Every agent workflow is documented so humans can reason about it, reuse it, and extend it. Agents should be able to explain what they did.
- **Hand & Glove Model** – NixOS‑Dev‑Quick‑Deploy (“the hand”) prepares the OS, GPU stack, and shared data directories. AI‑Optimizer or user-hosted stacks (“the glove”) can be layered on later without touching the base system.
- **Delegation Hierarchy (mirrors Hyper‑NixOS intent)**  
  - **Claude Code / human operators** handle complex reasoning, architecture, and cross-module integration.  
  - **AIDB Knowledge Base** provides high-trust context (docs, module maps, decisions).  
  - **Local agents** run deterministic tasks: file search, doc lookup, template generation, validation.
- **Composable Tools** – CLI helpers (ai-model-manager, smart_config_gen, sync_docs_to_ai, local-ai-starter) function independently so users can mix and match workflows.
- **Scope Boundaries** – Locally hosted agents manipulate workspace files, query knowledge bases, or run tests. They do **not** manage credentials, reconfigure the OS, or operate outside the directories explicitly prepared for them (`~/.local/share/ai-stack`, `~/Documents/local-ai-stack`, etc.).

## Agent Stacks Provided

1. **Trimmed Local Stack (public)**  
   - Launch via `./scripts/local-ai-starter.sh` → Option 2.  
   - Services: TimescaleDB/pgvector, Redis (+ RedisInsight), vLLM inference server.  
   - Data root: `~/.local/share/ai-stack/`.  
   - Compose files live in `~/Documents/local-ai-stack/`.

2. **AI-Optimizer Integration (private)**  
   - Prep system with Phase 9 or `scripts/local-ai-starter.sh` option 1.  
   - Deploy AI-Optimizer separately (see `docs/AI-OPTIMIZER-INTEGRATION-COMPLETE.md`).  
   - Shared data: `~/.local/share/ai-optimizer/`, configs in `~/.config/ai-optimizer/`.

## Tooling Guide

| Tool | Location | Purpose |
|------|----------|---------|
| `scripts/local-ai-starter.sh` | repo root | Menu-driven setup for directories, trimmed stack, OpenSkills, MCP templates |
| `scripts/ai-model-manager.sh` (`amm`) | repo root | Manage local model profiles (TGI/vLLM/Ollama) under `~/.config/ai-models/`; inspired by Hyper‑NixOS multi-instance model system |
| `scripts/smart_config_gen.sh` | repo root | Call AIDB MCP `/vllm/*` endpoints for config generation & review |
| `scripts/sync_docs_to_ai.sh` | repo root | Push docs to AI-Optimizer knowledge base |
| `scripts/deploy-aidb-mcp-server.sh` & `scripts/setup-mcp-databases.sh` | repo root | Bootstrap Postgres/Redis + MCP systemd units |
| `docs/LOCAL-AI-STARTER.md` | docs | Reference for running the trimmed stack without private repos |
| `docs/OPENSKILLS-INTEGRATION-PLAN.md` | docs | Process for layering OpenSkills-made skills onto local agents |

## Knowledge & Databases

- **Postgres (Timescale + pgvector)** – Container volume under `~/.local/share/ai-stack/postgres` (public). When AI-Optimizer is used, its data lives in `~/.local/share/ai-optimizer/postgres`.
- **Redis / RedisInsight** – Same directory structure as above (`redis`, `redisinsight`). Exposed on `6379` / `5540`.
- **vLLM Model Cache** – `~/.local/share/ai-stack/vllm-models` for public stack, `~/.local/share/ai-optimizer/vllm-models` for AI-Optimizer.
- **Documentation imports** – Run `scripts/sync_docs_to_ai.sh` to ingest `docs/*.md` into AI-Optimizer.

## Workflow Summary

1. **Prep system** – `./scripts/local-ai-starter.sh` option 1 or run Phase 9 (creates dirs, checks ports).
2. **Launch local stack** – Option 2 in the starter script, or manually `docker compose up -d` inside `~/Documents/local-ai-stack`.
3. **Install agent tooling** – Option 3 (OpenSkills CLI) and Option 4 (MCP template) as needed.
4. **Manage models** – Use `amm` to switch TGI/vLLM profiles, `smart_config_gen.sh` for AI-assisted config, and `sync_docs_to_ai.sh` to keep the knowledge base current.

## Roles, Responsibilities & Constraints (from Hyper-NixOS intent)

- **Lead Orchestrator (Claude / Human)**  
  - Reads/write design decisions, determines when to delegate.  
  - Responsible for “Third Pillar” (teaching/learning) by updating docs when new agent workflows are created.  
  - Maintains final authority on privileged operations (nixos-rebuild, secrets management).

- **Local Agent Tier**  
  - Executes deterministic CLI tasks (search, grep, lint, templating).  
  - Runs inside user namespace; no sudo, no system config changes.  
  - Access limited to project workspace, `~/.local/share/ai-stack`, and optionally `~/.local/share/ai-optimizer`.

- **Knowledge Tier (AIDB)**
  - Acts as source of truth for architecture, module relationships, troubleshooting.  
  - Must be populated before delegating doc lookups (use `scripts/sync_docs_to_ai.sh`).  
  - Stores experiment logs, agent usage outcomes, and skills metadata (OpenSkills).

- **Networking / Security Constraints**  
  - Port usage defined up front (5432, 6379, 5540, 8000, 8091, 8791).  
  - Phase 9 and `service-conflict-resolution.sh` ensure user services do not conflict with system services.  
  - Autologin/agent convenience patterns from Hyper‑NixOS are mirrored: local agents can run commands without passwords, but protected operations always prompt.

- **Scope Management**  
  - Agents can generate or modify repo files only when the orchestrator explicitly asks.  
  - Database migrations, secret rotation, or OS rebuilds remain manual unless the operator signs off.  
  - No long-lived credentials are embedded in scripts; `.env` templates require user input.

## Reference: Design Inspiration from Hyper-NixOS

- **Three Pillars:** Ease of Use, Security & Organization, Learning Ethos (docs/AUTHORS.md; scripts/lib/branding.sh).  
- **Delegation Plan:** Hyper‑NixOS AI Integration Plan (docs/dev/AI_INTEGRATION_PLAN.md) – emphasizes knowledge-first, agent-second workflows.  
- **Security Model:** Autologin convenience balanced by granular sudo rules (docs/SECURITY_MODEL.md). The same approach is applied here: local agents get convenience, but destructive actions require human approval.

## Repository Guidelines

- Prefer POSIX shell syntax in scripts unless the file already relies on Bash-specific features.
- Keep shellcheck compliance in mind when modifying shell scripts; add inline `shellcheck` directives only when unavoidable.
- Maintain descriptive logging for long-running operations and keep user-facing messages actionable.
- Preserve template placeholders (e.g., `VERSIONPLACEHOLDER`, `HASHPLACEHOLDER`) and comments that explain synchronization requirements.
- Update accompanying helper scripts when modifying template logic so behaviour stays consistent between generated files and runtime tooling.
- Use the Python-based placeholder utilities (e.g., `replace_placeholder`) instead of in-place `sed` edits when mutating generated configuration files.
- When adding documentation files like this one, keep the tone concise and future-oriented.
