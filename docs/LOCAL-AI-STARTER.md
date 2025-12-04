# Local AI Starter Toolkit

This toolkit helps users who do **not** have access to your private AI-Optimizer
repository set up their own locally hosted AI agents, OpenSkills workflows, and
MCP server scaffolds. Everything runs under the current user (rootless Podman or
Docker) so it will not interfere with the primary system.

---

## Script Overview

Run the helper from the repository root:

```bash
cd ~/Documents/NixOS-Dev-Quick-Deploy
./scripts/local-ai-starter.sh
```

The menu exposes four independent actions:

1. **Prepare shared directories and prerequisites**  
   Calls the same hooks used in Phase 9 to create
   `~/.local/share/ai-optimizer`, checks Podman/Docker availability, detects
   port conflicts, and records integration status.

2. **Scaffold the `local-ai-stack` compose project**  
   Copies `templates/local-ai-stack/docker-compose.yml` into
   `~/Documents/local-ai-stack/`, creates a matching `.env`, and (optionally)
   launches the stack via Docker Compose or Podman Compose. The trimmed stack
   mirrors the AI-Optimizer architecture while remaining self-contained:
   - `local-ai-postgres` (TimescaleDB + pgvector)
   - `local-ai-redis` and `local-ai-redisinsight`
   - `local-ai-lemonade` (OpenAI-compatible inference server)

3. **Install OpenSkills CLI**  
   Installs the npm package globally and runs `openskills init` in the selected
   workspace so users immediately get `.skills/`, `.openskills.json`, and an
   updated `AGENTS.md`.

4. **Scaffold an MCP server template**  
   Prompts for language (TypeScript/Deno or Python) and target directory, then
   copies the corresponding template from `templates/mcp-server-template.*`. It
   also generates a minimal README and environment file so users can run the
   sample server instantly.

Each option can be executed independently; nothing requires the private
AI-Optimizer repo.

> **Stack Components:** Postgres (TimescaleDB + pgvector), Redis (with
> RedisInsight), and the Lemonade OpenAI-compatible inference server. This mirrors
> the trimmed AI-Optimizer stack—legacy containers such as Ollama, Qdrant, and
> Open WebUI were removed to keep things lean and focused.

---

## Directory Layout After Running the Toolkit

```
~/.local/share/ai-optimizer/         # Shared data roots created by option 1
~/.local/share/ai-stack/             # Data directory for postgres/redis/lemonade volumes
~/Documents/local-ai-stack/          # docker-compose.yml + .env for local agents
~/Documents/skills-project/.skills/  # Generated when running OpenSkills init
~/Documents/mcp-sample/              # Scaffolding for the MCP server template
```

All generated files live in the user's home directory. Removing the stack is as
easy as deleting `~/Documents/local-ai-stack/` and stopping the containers.

---

## Requirements

- Podman or Docker (rootless is recommended)
- `npm` for the OpenSkills CLI
- `curl`, `jq`, and `ss` (already provided by the deployment scripts)
- Optional: `deno` (for the TypeScript MCP template) or Python 3 (for the Python template)

If a dependency is missing, the script reports the exact package to install.

---

## Next Steps for Users

1. Start the local AI stack: `cd ~/Documents/local-ai-stack && docker compose up -d`
2. Install skills with `openskills add <skill-name>`
3. Customize the MCP server template and run it against their local database
4. Point IDEs (Claude Code, Continue, Cline, etc.) at the new MCP server

This workflow keeps your private repositories and services isolated while giving
other users a reproducible way to deploy local agents and tooling on their own
machines.

### Keeping AI-Optimizer Separate (but Connected)

- The compose project created here never clones or mounts the private AI-Optimizer repository.
- Shared data roots (`~/.local/share/ai-stack/` for public stacks and `~/.local/share/ai-optimizer/` for the glove) let `lib/ai-optimizer-hooks.sh` detect when the glove shows up later.
- When you are ready to deploy the private stack, follow `docs/HAND-IN-GLOVE-INTEGRATION.md` so Phase 9 can hand off cleanly without reconfiguring NixOS.
