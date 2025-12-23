#!/usr/bin/env python3
"""
Apply AI Stack integration updates to README.md
This script makes the necessary changes to highlight the integrated AI stack in v6.0.0
"""

import re
import sys
from pathlib import Path

def main():
    readme_path = Path(__file__).parent.parent / "README.md"

    if not readme_path.exists():
        print(f"Error: README.md not found at {readme_path}", file=sys.stderr)
        sys.exit(1)

    # Read current README
    content = readme_path.read_text()

    # 1. Replace old "glove/hand" reference with new AI stack announcement
    old_glove_pattern = r'> The private AI-Optimizer \("glove"\) stack is intentionally NOT bundled.*?without modifying the base system\.'

    new_ai_stack_section = '''## ✨ NEW in v6.0.0: Fully Integrated AI Stack

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

See [`ai-stack/README.md`](ai-stack/README.md) and [`docs/AI-STACK-FULL-INTEGRATION.md`](docs/AI-STACK-FULL-INTEGRATION.md) for complete documentation.

---'''

    content = re.sub(old_glove_pattern, new_ai_stack_section, content, flags=re.DOTALL)

    # 2. Update AI Development Stack table section
    # Find the table between "### AI Development Stack" and the next "###"
    ai_table_pattern = r'(### AI Development Stack\n\|.*?\n\n)(### Pre-Installed Development Tools)'

    new_ai_table = '''### Integrated AI Development Stack

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

'''

    # Replace keeping the next section marker
    content = re.sub(ai_table_pattern, new_ai_table + r'\2', content, flags=re.DOTALL)

    # 3. Update "AI Stack Management" section
    # Replace entire section from "### AI Stack Management" to next "###"
    ai_mgmt_pattern = r'### AI Stack Management.*?\n(?=###[^#])'

    new_ai_mgmt_section = '''### AI Stack Management (Integrated v6.0.0)

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
```

**Agent skills (29 available):**
```bash
# List all skills
curl http://localhost:8091/skills | jq .

# Execute a skill
curl -X POST http://localhost:8091/skills/nixos-deployment/execute \\
  -H "Content-Type: application/json" \\
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

'''

    content = re.sub(ai_mgmt_pattern, new_ai_mgmt_section, content, flags=re.DOTALL)

    # 4. Add AI Stack documentation section
    # Find "### This Repository" and add after it
    doc_pattern = r'(### This Repository\n)'

    new_doc_section = r'''\1### AI Stack Documentation (NEW in v6.0.0)
- [AI Stack Integration Guide](docs/AI-STACK-FULL-INTEGRATION.md) - Complete architecture and migration
- [AI Stack README](ai-stack/README.md) - AI stack overview and quick start
- [AIDB MCP Server](ai-stack/mcp-servers/aidb/README.md) - AIDB server documentation
- [Agent Skills](ai-stack/agents/README.md) - 29 specialized AI agent skills
- [AI Stack Architecture](ai-stack/docs/ARCHITECTURE.md) - Technical architecture details
- [Agent Workflows](docs/AGENTS.md) - AI agent integration and skill development
- [MCP Servers Guide](docs/MCP_SERVERS.md) - Model Context Protocol server docs

'''

    content = re.sub(doc_pattern, new_doc_section, content)

    # 5. Update Podman Storage section title
    content = content.replace(
        '### Podman Storage: Btrfs Recommended for AI-Optimizer',
        '### Podman Storage: Btrfs Recommended for AI Stack'
    )
    content = content.replace(
        'For AI-Optimizer workloads (see `~/Documents/AI-Optimizer`)',
        'For AI stack workloads'
    )

    # Write updated README
    readme_path.write_text(content)

    print("✅ README.md updated successfully!")
    print("\nChanges applied:")
    print("  1. Added v6.0.0 AI stack announcement section")
    print("  2. Updated AI Development Stack table")
    print("  3. Expanded AI Stack Management section")
    print("  4. Added AI Stack documentation links")
    print("  5. Updated Podman storage references")
    print("\nPlease review the changes with: git diff README.md")

if __name__ == "__main__":
    main()
