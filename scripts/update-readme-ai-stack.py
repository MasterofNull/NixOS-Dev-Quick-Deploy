#!/usr/bin/env python3
"""
Apply AI Stack integration updates to README.md for v6.0.0
"""

import sys
from pathlib import Path

def main():
    readme_path = Path(__file__).parent.parent / "README.md"

    if not readme_path.exists():
        print(f"Error: README.md not found at {readme_path}", file=sys.stderr)
        sys.exit(1)

    # Read current README line by line
    lines = readme_path.read_text().splitlines(keepends=True)

    # Track modifications
    new_lines = []
    skip_until_marker = None
    i = 0

    while i < len(lines):
        line = lines[i]

        # 1. Replace old glove reference with new AI stack section
        if '> The private AI-Optimizer ("glove")' in line:
            # Skip the entire paragraph
            while i < len(lines) and not lines[i].strip().startswith('**'):
                i += 1
            # Insert new section
            new_lines.extend([
                '\n',
                '## ✨ NEW in v6.0.0: Fully Integrated AI Stack\n',
                '\n',
                'The AI stack is now a **first-class, public component** of this repository!\n',
                '\n',
                '### Quick AI Stack Deployment\n',
                '\n',
                '```bash\n',
                '# Deploy NixOS + complete AI development environment\n',
                './nixos-quick-deploy.sh --with-ai-stack\n',
                '```\n',
                '\n',
                'This single command gives you:\n',
                '- ✅ **AIDB MCP Server** - PostgreSQL + TimescaleDB + Qdrant vector database\n',
                '- ✅ **llama.cpp vLLM** - Local model inference (Qwen, DeepSeek, Phi, CodeLlama)\n',
                '- ✅ **29 Agent Skills** - Specialized AI agents for code, deployment, testing, design\n',
                '- ✅ **MCP Servers** - Model Context Protocol servers for AIDB, NixOS, GitHub\n',
                '- ✅ **Shared Data** - Persistent data that survives reinstalls (`~/.local/share/nixos-ai-stack`)\n',
                '\n',
                'See [`ai-stack/README.md`](ai-stack/README.md) and [`docs/AI-STACK-FULL-INTEGRATION.md`](docs/AI-STACK-FULL-INTEGRATION.md) for complete documentation.\n',
                '\n',
                '---\n',
                '\n',
            ])
            continue

        # 2. Update table title
        if line.strip() == '### AI Development Stack':
            new_lines.append('### Integrated AI Development Stack\n')
            new_lines.append('\n')
            new_lines.append('**Fully Integrated Components (v6.0.0):**\n')
            new_lines.append('\n')
            new_lines.append('| Component | Location | Purpose |\n')
            new_lines.append('|-----------|----------|---------||\n')
            new_lines.append('| **AIDB MCP Server** | `ai-stack/mcp-servers/aidb/` | PostgreSQL + TimescaleDB + Qdrant vector DB + FastAPI MCP server |\n')
            new_lines.append('| **llama.cpp vLLM** | `ai-stack/compose/` | Local OpenAI-compatible inference (Qwen, DeepSeek, Phi, CodeLlama) |\n')
            new_lines.append('| **29 Agent Skills** | `ai-stack/agents/skills/` | nixos-deployment, webapp-testing, code-review, canvas-design, and more |\n')
            new_lines.append('| **MCP Servers** | `ai-stack/mcp-servers/` | Model Context Protocol servers for AIDB, NixOS, GitHub |\n')
            new_lines.append('| **Model Registry** | `ai-stack/models/registry.json` | Model catalog with 6 AI models (metadata, VRAM, speed, quality scores) |\n')
            new_lines.append('| **Vector Database** | PostgreSQL + Qdrant | Semantic search and document embeddings |\n')
            new_lines.append('| **Redis Cache** | Redis + Redis Insight | High-performance caching layer |\n')
            new_lines.append('\n')
            new_lines.append('**AI Development Tools:**\n')
            new_lines.append('\n')
            # Skip old table, keep until next section
            i += 1
            while i < len(lines) and not lines[i].startswith('###'):
                if '| Tool |' in lines[i] or '|---' in lines[i]:
                    new_lines.append(lines[i])
                elif lines[i].startswith('|'):
                    # Modify existing tool lines if needed
                    if 'GPT CLI' in lines[i]:
                        new_lines.append('| **GPT CLI** | Command-line tool | Query OpenAI-compatible endpoints (local llama.cpp or remote) |\n')
                    elif 'Ollama' in lines[i] or 'Open WebUI' in lines[i] or 'Hugging Face TGI' in lines[i]:
                        pass  # Skip these old entries
                    else:
                        new_lines.append(lines[i])
                else:
                    new_lines.append(lines[i])
                i += 1
            # Add quick start
            new_lines.append('\n')
            new_lines.append('**Quick Start:**\n')
            new_lines.append('```bash\n')
            new_lines.append('./nixos-quick-deploy.sh --with-ai-stack  # Deploy everything\n')
            new_lines.append('./scripts/ai-stack-manage.sh up         # Start AI services\n')
            new_lines.append('./scripts/ai-stack-manage.sh health     # Check health\n')
            new_lines.append('```\n')
            new_lines.append('\n')
            continue

        # 3. Update Podman Storage title
        if '### Podman Storage: Btrfs Recommended for AI-Optimizer' in line:
            new_lines.append('### Podman Storage: Btrfs Recommended for AI Stack\n')
            i += 1
            # Update next line if it mentions AI-Optimizer
            if i < len(lines) and 'AI-Optimizer workloads' in lines[i]:
                new_lines.append('\nThe deployer will prompt for the Podman storage driver. For AI stack workloads, use **Btrfs** when possible for fast snapshots and deduplication.\n')
                i += 1
            continue

        # 4. Add AI Stack docs after "### This Repository"
        if line.strip() == '### This Repository':
            new_lines.append(line)
            i += 1
            # Add AI Stack documentation section
            new_lines.extend([
                '### AI Stack Documentation (NEW in v6.0.0)\n',
                '- [AI Stack Integration Guide](docs/AI-STACK-FULL-INTEGRATION.md) - Complete architecture and migration\n',
                '- [AI Stack README](ai-stack/README.md) - AI stack overview and quick start\n',
                '- [AIDB MCP Server](ai-stack/mcp-servers/aidb/README.md) - AIDB server documentation\n',
                '- [Agent Skills](ai-stack/agents/README.md) - 29 specialized AI agent skills\n',
                '- [AI Stack Architecture](ai-stack/docs/ARCHITECTURE.md) - Technical architecture details\n',
                '- [Agent Workflows](docs/AGENTS.md) - AI agent integration and skill development\n',
                '- [MCP Servers Guide](docs/MCP_SERVERS.md) - Model Context Protocol server docs\n',
                '\n',
            ])
            continue

        # Default: keep line
        new_lines.append(line)
        i += 1

    # Write updated README
    readme_path.write_text(''.join(new_lines))

    print("✅ README.md updated successfully!")
    print("\nKey changes:")
    print("  1. ✅ Added v6.0.0 AI stack announcement")
    print("  2. ✅ Updated AI Development Stack table")
    print("  3. ✅ Updated Podman storage references")
    print("  4. ✅ Added AI Stack documentation section")
    print("\nReview with: git diff README.md")

if __name__ == "__main__":
    main()
