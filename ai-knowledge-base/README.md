# AI Knowledge Base

This directory contains curated knowledge, documentation, and resources for AI agents working with the NixOS-Dev-Quick-Deploy stack.

## Directory Structure

```
ai-knowledge-base/
├── README.md                           # This file
├── mcp-servers/                        # MCP Server configurations and catalogs
│   ├── nixos-development.json         # NixOS/Nix-specific MCP servers
│   ├── ai-llm-development.json        # AI/LLM development MCP servers
│   ├── vm-qemu-development.json       # QEMU/VM development MCP servers
│   ├── coding-agents.json             # Coding agent MCP servers
│   └── knowledge-databases.json       # Vector DB and knowledge MCP servers
├── skills/                             # Agent skills and capabilities
│   ├── nixos-skills.md                # NixOS-specific skills
│   ├── ai-development-skills.md       # AI/LLM development skills
│   ├── vm-management-skills.md        # VM/QEMU management skills
│   └── agentic-workflow-skills.md     # Agentic workflow skills
├── workflows/                          # Common agentic workflows
│   ├── nixos-deployment.md            # NixOS deployment workflows
│   ├── ai-model-deployment.md         # AI model deployment workflows
│   ├── vm-provisioning.md             # VM provisioning workflows
│   └── development-environment.md     # Development environment setup
├── reference/                          # Reference documentation
│   ├── lemonade-api.md                # Lemonade AI server API reference
│   ├── ollama-api.md                  # Ollama API reference
│   ├── qdrant-api.md                  # Qdrant vector DB API reference
│   └── podman-commands.md             # Podman/Docker commands reference
└── datasets/                           # Curated datasets for RAG
    ├── nix-packages.json              # NixOS package metadata
    ├── common-errors.json             # Common errors and solutions
    └── best-practices.json            # Best practices and patterns
```

## Purpose

This knowledge base serves multiple purposes:

1. **Agent Onboarding**: Quick reference for new AI agents joining the development workflow
2. **Context Augmentation**: Additional context for LLM queries via RAG (Retrieval Augmented Generation)
3. **Workflow Templates**: Pre-defined workflows for common tasks
4. **MCP Server Discovery**: Catalog of available MCP servers for specific use cases
5. **Skill Documentation**: Documented capabilities and how to leverage them

## Usage

### For AI Agents

AI agents should:
1. Read the relevant knowledge files based on the task at hand
2. Use MCP server catalogs to discover available tools
3. Follow documented workflows for complex tasks
4. Reference API documentation for integration tasks

### For Developers

Developers should:
1. Keep this knowledge base updated as new tools are added
2. Document new workflows as they're developed
3. Add MCP servers to the appropriate catalog files
4. Contribute common error solutions to datasets

## Integration Points

This knowledge base integrates with:

- **Lemonade AI Server**: Provides context for LLM inference
- **Qdrant Vector DB**: Stores embeddings for semantic search
- **AIDB MCP Server**: Accesses knowledge via MCP protocol
- **Claude Code**: Provides context for development tasks
- **Open WebUI**: Displays knowledge in chat interfaces

## Maintenance

- **Update Frequency**: Weekly or when significant changes occur
- **Ownership**: Maintained by the development team and AI agents
- **Validation**: All entries should be tested and verified before inclusion
