# README.md AI Stack Integration Updates

## Status
These updates transform the README to highlight the integrated AI stack as a first-class feature in v6.0.0.

## Changes Required

### 1. Replace Line 22 (Old "glove/hand" Reference)

**OLD (line 22):**
```
> The private AI-Optimizer ("glove") stack is intentionally NOT bundled with this repository ("hand"). Instead, Phase 9 and the helper scripts simply prepare shared directories and ports so you can layer the glove later without modifying the base system.
```

**NEW:**
Insert this section after line 21, replacing the old line 22:

```markdown
## ✨ NEW in v6.0.0: Fully Integrated AI Stack

The AI stack is now a **first-class, public component** of this repository!

### Quick AI Stack Deployment

```bash
# Deploy NixOS + complete AI development environment
./nixos-quick-deploy.sh --with-ai-stack
```

This single command gives you:
- ✅ **AIDB MCP Server** - PostgreSQL + TimescaleDB + Qdrant vector database
- ✅ **llama.cpp vLLM** - Local model inference (Qwen, DeepSeek, Phi, CodeLlama)
- ✅ **29 Agent Skills** - Specialized AI agents for code, deployment, testing, design
- ✅ **MCP Servers** - Model Context Protocol servers for AIDB, NixOS, GitHub
- ✅ **Shared Data** - Persistent data that survives reinstalls (`~/.local/share/nixos-ai-stack`)

See [`ai-stack/README.md`](/ai-stack/README.md) and [`docs/AI-STACK-FULL-INTEGRATION.md`](/docs/AI-STACK-FULL-INTEGRATION.md) for complete documentation.

---
```

### 2. Update "AI Development Stack" Table (Lines 46-58)

**Replace the existing table starting at line 46 with:**

```markdown
### Integrated AI Development Stack

**Fully Integrated Components (v6.0.0):**

| Component | Location | Purpose |
|-----------|----------|---------|
| **AIDB MCP Server** | `ai-stack/mcp-servers/aidb/` | PostgreSQL + TimescaleDB + Qdrant vector DB + FastAPI MCP server |
| **llama.cpp vLLM** | `ai-stack/compose/` | Local OpenAI-compatible inference (Qwen, DeepSeek, Phi, CodeLlama) |
| **29 Agent Skills** | `ai-stack/agents/skills/` | nixos-deployment, webapp-testing, code-review, canvas-design, and more |
| **MCP Servers** | `ai-stack/mcp-servers/` | Model Context Protocol servers for AIDB, NixOS, GitHub |
| **Model Registry** | `ai-stack/models/registry.json` | Model catalog with 6 AI models (metadata, VRAM, speed, quality scores) |
| **Vector Database** | PostgreSQL + Qdrant | Semantic search and document embeddings |
| **Redis Cache** | Redis + Redis Insight | High-performance caching layer |

**AI Development Tools:**

| Tool | Integration | Purpose |
|------|-------------|---------|
| **Claude Code** | VSCodium extension + CLI wrapper | AI pair programming inside VSCodium |
| **Cursor** | Flatpak + launcher | AI-assisted IDE with GPT-4/Claude |
| **Continue** | VSCodium extension | In-editor AI completions |
| **Codeium** | VSCodium extension | Free AI autocomplete |
| **GPT CLI** | Command-line tool | Query OpenAI-compatible endpoints (local llama.cpp or remote) |
| **Aider** | CLI code assistant | AI pair programming from terminal |
| **LM Studio** | Flatpak app | Desktop LLM manager |

**Quick Start:**
```bash
./nixos-quick-deploy.sh --with-ai-stack  # Deploy everything
./scripts/ai-stack-manage.sh up         # Start AI services
./scripts/ai-stack-manage.sh health     # Check health
```
```

### 3. Add AI Stack Management Section (After line 382 - after "AI Stack Management" section)

**Insert this complete section to replace the existing "AI Stack Management" section (lines 352-382):**

```markdown
### AI Stack Management (Integrated v6.0.0)

**Deploy AI stack:**
```bash
# During initial deployment
./nixos-quick-deploy.sh --with-ai-stack

# Or add to existing system
./nixos-quick-deploy.sh --resume --phase 9
```

**Manage AI services:**
```bash
./scripts/ai-stack-manage.sh up         # Start all AI services
./scripts/ai-stack-manage.sh down       # Stop all AI services
./scripts/ai-stack-manage.sh restart    # Restart AI stack
./scripts/ai-stack-manage.sh status     # Show service status
./scripts/ai-stack-manage.sh logs       # View all logs
./scripts/ai-stack-manage.sh logs aidb  # View specific service logs
./scripts/ai-stack-manage.sh health     # Run health checks
./scripts/ai-stack-manage.sh sync       # Sync documentation to AIDB
```

**Check AI stack health:**
```bash
# Verify all services
./scripts/ai-stack-manage.sh health

# Test individual endpoints
curl http://localhost:8091/health | jq .       # AIDB MCP server
curl http://localhost:8080/health | jq .       # llama.cpp inference
curl http://localhost:6333/collections | jq .  # Qdrant vector DB
curl http://localhost:6379 | redis-cli ping    # Redis
```

**Agent skills (29 available):**
```bash
# List all skills
curl http://localhost:8091/skills | jq .

# Execute a skill
curl -X POST http://localhost:8091/skills/nixos-deployment/execute \
  -H "Content-Type: application/json" \
  -d '{"action": "generate_config", "packages": ["vim", "git"]}'
```

**Data persistence:**
```bash
# All data survives reinstalls
~/.local/share/nixos-ai-stack/
├── postgres/         # PostgreSQL database
├── redis/            # Redis persistence
├── qdrant/           # Vector database
├── llama-cpp-models/  # Downloaded models (auto-cached)
├── imports/          # Document imports
└── exports/          # Exported data

# Configuration
~/.config/nixos-ai-stack/.env  # Active configuration

# Logs
~/.cache/nixos-ai-stack/logs/  # Service logs
```

**Model management:**
```bash
# View available models
cat ai-stack/models/registry.json | jq .

# Download a model (automatic on first use)
# Models are cached in ~/.local/share/nixos-ai-stack/llama-cpp-models/

# Switch models (update .env)
vim ~/.config/nixos-ai-stack/.env
# Change LLAMA_CPP_DEFAULT_MODEL=Qwen/Qwen2.5-Coder-7B-Instruct
./scripts/ai-stack-manage.sh restart
```
```

### 4. Update Documentation Section (Around line 1356)

**Add these to the "### This Repository" subsection:**

```markdown
### AI Stack Documentation (NEW in v6.0.0)
- [AI Stack Integration Guide](/docs/AI-STACK-FULL-INTEGRATION.md) - Complete architecture and migration
- [AI Stack README](/ai-stack/README.md) - AI stack overview and quick start
- [AIDB MCP Server](/ai-stack/mcp-servers/aidb/README.md) - AIDB server documentation
- [Agent Skills](/ai-stack/agents/README.md) - 29 specialized AI agent skills
- [AI Stack Architecture](/ai-stack/docs/ARCHITECTURE.md) - Technical architecture details
- [Agent Workflows](/docs/AGENTS.md) - AI agent integration and skill development
- [MCP Servers Guide](/docs/MCP_SERVERS.md) - Model Context Protocol server docs
```

### 5. Remove/Update "Podman Storage" Section (Lines 209-222)

**The Btrfs recommendation section can stay, but update the context:**

```markdown
### Podman Storage: Btrfs Recommended for AI Stack

The AI stack uses Podman containers for all services. For best performance, use **Btrfs** storage driver.

- **Sizing:** Minimum 150 GiB; **recommended 200–300 GiB** for multiple AI models and vector databases.
```

---

## Summary

These changes transform the README from "base system with optional private AI stack" to "complete AI development environment with integrated public AI stack".

**Key messaging changes:**
1. ✅ AI stack is now **public and integrated** (not private and separate)
2. ✅ Single command deployment (`--with-ai-stack`)
3. ✅ Complete documentation in this repo
4. ✅ Data persistence across reinstalls
5. ✅ 29 agent skills available out of the box
6. ✅ No external dependencies

**Next step:** Apply these changes manually to README.md or use a script to perform the replacements.
