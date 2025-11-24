# OpenSkills Integration Plan for NixOS-Dev-Quick-Deploy
# Version: 1.0.0
# Date: 2025-11-22

## Executive Summary

This document provides a comprehensive implementation plan for integrating **OpenSkills** into your NixOS development environment to teach AI agents (Claude Code, locally hosted agents, and web-based agents) how to use CLI tools systematically.

**OpenSkills** is a 2025 npm package that brings Claude Code's skills system to all AI development tools (Cursor, Windsurf, Aider, CLI agents) with the same format, structure, and marketplace compatibility.

---

## Table of Contents

1. [Current System Status](#current-system-status)
2. [What is OpenSkills?](#what-is-openskills)
3. [Architecture Overview](#architecture-overview)
4. [Implementation Strategy](#implementation-strategy)
5. [Phase 1: OpenSkills Installation](#phase-1-openskills-installation)
6. [Phase 2: Skills Creation](#phase-2-skills-creation)
7. [Phase 3: MCP Integration](#phase-3-mcp-integration)
8. [Phase 4: Multi-Agent Distribution](#phase-4-multi-agent-distribution)
9. [Best Practices](#best-practices)
10. [Maintenance & Updates](#maintenance--updates)

---

## Current System Status

### Running Services
- ✅ **AIDB MCP Server**: Running in Docker container (ports 8791, 8091)
  - Location: `aidb-mcp` container
  - Process: `/app/mcp_server/server.py`
  - Config: `/app/config/config.yaml`

- ✅ **PostgreSQL**: `mcp-postgres` container (port 5432)
- ✅ **Redis**: `mcp-redis` container (port 6379)
- ✅ **Qdrant**: `local-ai-qdrant` container (ports 6333, 6334)
- ✅ **Ollama**: `local-ai-ollama` container (port 11434)

### Current Deployment Issues
⚠️ **Warning**: The `deploy-aidb-mcp-server.sh` script has conflicts with the running AIDB container. This script needs to be updated to:
1. Detect existing AIDB installations
2. Avoid recreating services that are already running
3. Integrate with the existing Docker-based AIDB deployment

---

## What is OpenSkills?

**OpenSkills** is an open-source CLI tool and framework that:

1. **Brings Claude Code's Skills System to All Agents**
   - Works with Claude Code, Cursor, Windsurf, Aider, and plain CLI agents
   - 100% compatible with Anthropic's skills marketplace
   - Same format, same folder structure, same SKILL.md files

2. **Progressive Disclosure Pattern**
   - Initial context contains only skill name + description
   - Full instructions loaded on-demand via `openskills read <skill>`
   - Token-efficient: Load only what's needed

3. **Universal Skill Management**
   - Install skills globally: `npm i -g openskills`
   - Install from GitHub: `openskills install anthropics/skills`
   - Sync across agents: `openskills sync`
   - Version control: Store skills in your repo

### Key Resources
- **GitHub**: https://github.com/numman-ali/openskills
- **Documentation**: https://github.com/BandarLabs/open-skills
- **Installation**: `npm i -g openskills`

---

## Architecture Overview

### Three-Layer Architecture

```
┌─────────────────────────────────────────────────────────────────┐
│                     Layer 1: AI Agents                          │
│  ┌──────────────┐  ┌──────────────┐  ┌──────────────┐         │
│  │ Claude Code  │  │ Cursor/      │  │ Local LLMs   │         │
│  │              │  │ Windsurf     │  │ (Ollama)     │         │
│  └──────┬───────┘  └──────┬───────┘  └──────┬───────┘         │
└─────────┼──────────────────┼──────────────────┼─────────────────┘
          │                  │                  │
          │   ┌──────────────▼──────────────────▼───────────┐
          │   │        Layer 2: OpenSkills                   │
          │   │                                              │
          └───┤  ┌──────────────────────────────────────┐   │
              │  │ openskills read <skill>              │   │
              │  │ - Loads SKILL.md on demand          │   │
              │  │ - Progressive disclosure             │   │
              │  │ - Token-efficient                    │   │
              │  └──────────────────────────────────────┘   │
              │                                              │
              │  ┌──────────────────────────────────────┐   │
              │  │ Skill Discovery (AGENTS.md)          │   │
              │  │ <available_skills>                   │   │
              │  │   - Name + brief description         │   │
              │  │ </available_skills>                  │   │
              │  └──────────────────────────────────────┘   │
              └──────────────┬───────────────────────────────┘
                             │
          ┌──────────────────▼────────────────────────────────┐
          │        Layer 3: MCP Server Integration            │
          │                                                   │
          │  ┌─────────────────────────────────────────────┐ │
          │  │ AIDB MCP Server (Your Current Setup)        │ │
          │  │ - PostgreSQL (tool registry)                │ │
          │  │ - Redis (caching)                           │ │
          │  │ - Qdrant (semantic search)                  │ │
          │  │ - Tool execution sandboxing                 │ │
          │  └─────────────────────────────────────────────┘ │
          │                                                   │
          │  ┌─────────────────────────────────────────────┐ │
          │  │ CLI Tools & Scripts                         │ │
          │  │ - nixos-quick-deploy.sh                     │ │
          │  │ - ai-servicectl                             │ │
          │  │ - system-health-check.sh                    │ │
          │  │ - ai-model-manager.sh                       │ │
          │  └─────────────────────────────────────────────┘ │
          └───────────────────────────────────────────────────┘
```

### Data Flow

1. **Skill Discovery**
   ```
   AI Agent reads AGENTS.md
   → Sees <available_skills> block
   → Chooses relevant skill
   → Executes: openskills read <skill-name>
   → Receives full SKILL.md instructions
   ```

2. **Tool Execution (via MCP)**
   ```
   AI Agent with skill knowledge
   → Calls MCP tool via JSON-RPC
   → AIDB MCP Server validates request
   → Executes sandboxed CLI command
   → Returns structured result
   ```

3. **Progressive Learning**
   ```
   First request: Load minimal skill list (low tokens)
   Second request: Load specific skill details (on-demand)
   Subsequent requests: Use cached knowledge
   ```

---

## Implementation Strategy

### Overview

We'll implement a **hybrid approach** combining:
1. **OpenSkills** for skill discovery and progressive disclosure
2. **AIDB MCP Server** for tool execution and state management
3. **NixOS declarative configuration** for reproducible deployment

### Benefits

✅ **For Claude Code**
- Native skills system compatibility
- Token-efficient progressive disclosure
- Access to Anthropic skills marketplace

✅ **For Local Agents (Ollama)**
- Same skills interface as Claude Code
- No vendor lock-in
- Runs entirely offline

✅ **For Web Agents (Cursor, Windsurf, etc.)**
- Portable skills across tools
- Consistent development experience
- Community skill sharing

✅ **For Your System**
- All CLI tools documented in skill format
- Agents learn tools systematically
- Version-controlled skill library

---

## Phase 1: OpenSkills Installation

### 1.1 Install OpenSkills Globally

```bash
# Install via npm
npm i -g openskills

# Verify installation
openskills --version

# Check available commands
openskills --help
```

### 1.2 Initialize OpenSkills in Project

```bash
cd ~/Documents/NixOS-Dev-Quick-Deploy

# Initialize OpenSkills
openskills init

# This creates:
# - .skills/ directory
# - AGENTS.md with <available_skills> block
# - .openskills.json config file
```

### 1.3 Add to NixOS Configuration

Update `templates/home.nix` to include OpenSkills:

```nix
# Add to home.packages
home.packages = with pkgs; [
  # ... existing packages ...

  # OpenSkills for AI agent CLI tool training
  nodejs_22
  # (openskills installed via npm -g, managed by home-manager)
];

# Create systemd environment file for OpenSkills
home.file.".config/openskills/config.json".text = builtins.toJSON {
  skills_dir = "${config.home.homeDirectory}/.skills";
  global_skills_dir = "/home/${config.home.username}/.local/share/openskills/skills";
  agents_file = "AGENTS.md";
  auto_sync = true;
};
```

### 1.4 Install Skills from Anthropic Marketplace

```bash
# Install official Anthropic skills
openskills install anthropics/skills

# Install community skills (examples)
openskills install your-org/custom-skills

# List installed skills
openskills list
```

---

## Phase 2: Skills Creation

### 2.1 Create Skills Directory Structure

```bash
cd ~/Documents/NixOS-Dev-Quick-Deploy

# Create skills directory
mkdir -p .skills/nixos-cli-tools

# Skill structure:
# .skills/
# ├── nixos-cli-tools/
# │   ├── SKILL.md                    # Main skill definition
# │   ├── examples/                    # Usage examples
# │   │   ├── basic-deployment.md
# │   │   └── health-check.md
# │   └── assets/                      # Optional diagrams/screenshots
# └── ai-service-management/
#     └── SKILL.md
```

### 2.2 Create SKILL.md Template

Each CLI tool should have a SKILL.md file:

```markdown
# Skill Name: nixos-quick-deploy

## Description
Comprehensive NixOS deployment script with 8 phases for declarative system configuration.

## When to Use
- Setting up new NixOS systems
- Updating existing NixOS configurations
- Migrating from imperative to declarative configuration
- Troubleshooting NixOS deployments

## Prerequisites
- NixOS system
- Root or sudo access
- Git configured

## Usage

### Basic Deployment
\`\`\`bash
cd ~/Documents/NixOS-Dev-Quick-Deploy
./nixos-quick-deploy.sh
\`\`\`

### Resume from Specific Phase
\`\`\`bash
./nixos-quick-deploy.sh --start-from-phase 5
\`\`\`

### Skip Health Check
\`\`\`bash
./nixos-quick-deploy.sh --skip-health-check
\`\`\`

### Reset State (Start Fresh)
\`\`\`bash
./nixos-quick-deploy.sh --reset-state
\`\`\`

## Command-Line Options
- `--start-from-phase N`: Resume from phase N (1-8)
- `--skip-health-check`: Skip post-deployment validation
- `--reset-state`: Clear state and start from beginning
- `--list-phases`: Show all deployment phases
- `--version`: Show script version
- `--help`: Display help message

## Output Interpretation

### Success Indicators
- ✅ Green checkmarks for completed phases
- Phase status in state.json
- Health check passes all tests

### Common Errors
- **Phase X failed**: Check logs in ~/.cache/nixos-quick-deploy/logs/
- **Permission denied**: Run with sudo or as root
- **Flake evaluation failed**: Check flake.nix syntax

## Related Skills
- `ai-servicectl`: Manage AI stack services
- `system-health-check`: Validate system health
- `ai-model-manager`: Manage AI models

## MCP Integration
This skill integrates with the AIDB MCP Server for:
- Tool execution logging
- State persistence
- Error tracking

## Examples

### Example 1: First-Time Setup
\`\`\`bash
# Clone repository
git clone https://github.com/your-org/NixOS-Dev-Quick-Deploy.git
cd NixOS-Dev-Quick-Deploy

# Run deployment
./nixos-quick-deploy.sh

# Follow prompts for:
# - Git identity
# - GPU detection
# - Package selection
\`\`\`

### Example 2: Update After Configuration Changes
\`\`\`bash
# Edit configuration
vim templates/configuration.nix

# Deploy changes
./nixos-quick-deploy.sh --start-from-phase 5
\`\`\`

### Example 3: Troubleshooting
\`\`\`bash
# Check current state
cat ~/.cache/nixos-quick-deploy/state.json

# View logs
tail -f ~/.cache/nixos-quick-deploy/logs/deploy-*.log

# Reset and retry
./nixos-quick-deploy.sh --reset-state
\`\`\`
```

### 2.3 Create Skills for Your CLI Tools

Create SKILL.md files for each major tool:

1. **nixos-quick-deploy.sh** → `.skills/nixos-deployment/SKILL.md`
2. **ai-servicectl** → `.skills/ai-service-management/SKILL.md`
3. **system-health-check.sh** → `.skills/health-monitoring/SKILL.md`
4. **ai-model-manager.sh** → `.skills/ai-model-management/SKILL.md`
5. **setup-mcp-databases.sh** → `.skills/mcp-database-setup/SKILL.md`

### 2.4 Generate AGENTS.md

```bash
# Sync skills to AGENTS.md
openskills sync

# This generates AGENTS.md with:
<available_skills>
- nixos-deployment: Comprehensive NixOS system deployment
- ai-service-management: Control AI stack services (Ollama, Qdrant, etc.)
- health-monitoring: Validate system health and configuration
- ai-model-management: Manage AI models and inference
- mcp-database-setup: Setup PostgreSQL and Redis for MCP server
</available_skills>
```

---

## Phase 3: MCP Integration

### 3.1 Update AIDB MCP Server Configuration

The AIDB MCP server should expose tools that correspond to OpenSkills skills:

```python
# /app/mcp_server/tools/nixos_tools.py

from mcp_server.core import Tool, ToolCategory

class NixOSDeploymentTool(Tool):
    """
    NixOS Quick Deploy tool
    Corresponds to: .skills/nixos-deployment/SKILL.md
    """

    name = "nixos-quick-deploy"
    description = "Deploy NixOS configuration with 8-phase workflow"
    category = ToolCategory.SYSTEM_MANAGEMENT

    input_schema = {
        "type": "object",
        "properties": {
            "start_from_phase": {
                "type": "integer",
                "description": "Phase to start from (1-8)",
                "minimum": 1,
                "maximum": 8
            },
            "skip_health_check": {
                "type": "boolean",
                "description": "Skip post-deployment health check",
                "default": False
            },
            "reset_state": {
                "type": "boolean",
                "description": "Reset state before starting",
                "default": False
            }
        }
    }

    async def execute(self, **kwargs):
        """Execute nixos-quick-deploy.sh with parameters"""
        import subprocess

        cmd = ["/home/hyperd/Documents/NixOS-Dev-Quick-Deploy/nixos-quick-deploy.sh"]

        if kwargs.get("start_from_phase"):
            cmd.extend(["--start-from-phase", str(kwargs["start_from_phase"])])

        if kwargs.get("skip_health_check"):
            cmd.append("--skip-health-check")

        if kwargs.get("reset_state"):
            cmd.append("--reset-state")

        # Execute in sandboxed environment
        result = await self.sandbox_execute(cmd)

        return {
            "stdout": result.stdout,
            "stderr": result.stderr,
            "exit_code": result.returncode,
            "skill_reference": "nixos-deployment"
        }
```

### 3.2 Register Tools with OpenSkills Metadata

```python
# /app/mcp_server/registry.py

TOOL_SKILL_MAPPING = {
    "nixos-quick-deploy": {
        "skill_name": "nixos-deployment",
        "skill_file": ".skills/nixos-deployment/SKILL.md",
        "openskills_command": "openskills read nixos-deployment"
    },
    "ai-servicectl": {
        "skill_name": "ai-service-management",
        "skill_file": ".skills/ai-service-management/SKILL.md",
        "openskills_command": "openskills read ai-service-management"
    },
    # ... other tools
}
```

### 3.3 Create MCP Tool Discovery Endpoint

```python
# /app/mcp_server/api/skills.py

from fastapi import APIRouter
from typing import List, Dict

router = APIRouter(prefix="/api/v1/skills")

@router.get("/list")
async def list_skills() -> List[Dict]:
    """
    List all available skills with OpenSkills references
    """
    return [
        {
            "name": "nixos-deployment",
            "description": "Comprehensive NixOS system deployment",
            "openskills_command": "openskills read nixos-deployment",
            "mcp_tool": "nixos-quick-deploy",
            "category": "system-management"
        },
        # ... other skills
    ]

@router.get("/read/{skill_name}")
async def read_skill(skill_name: str) -> Dict:
    """
    Read full skill definition (mimics openskills read)
    """
    skill_file = f".skills/{skill_name}/SKILL.md"
    with open(skill_file) as f:
        content = f.read()

    return {
        "skill_name": skill_name,
        "content": content,
        "format": "markdown"
    }
```

### 3.4 Update Database Schema

Add skills tracking to PostgreSQL:

```sql
-- Add to existing MCP database

CREATE TABLE IF NOT EXISTS skills (
    id SERIAL PRIMARY KEY,
    name VARCHAR(255) NOT NULL UNIQUE,
    description TEXT,
    skill_file_path TEXT,
    tool_id INTEGER REFERENCES tools(id),
    category VARCHAR(100),
    version VARCHAR(50),
    created_at TIMESTAMP DEFAULT NOW(),
    updated_at TIMESTAMP DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS skill_usage (
    id SERIAL PRIMARY KEY,
    skill_id INTEGER REFERENCES skills(id),
    agent_type VARCHAR(100),  -- 'claude-code', 'ollama', 'cursor', etc.
    session_id VARCHAR(255),
    loaded_at TIMESTAMP DEFAULT NOW(),
    execution_count INTEGER DEFAULT 0
);

CREATE INDEX idx_skills_name ON skills(name);
CREATE INDEX idx_skills_category ON skills(category);
CREATE INDEX idx_skill_usage_skill_id ON skill_usage(skill_id);
CREATE INDEX idx_skill_usage_agent_type ON skill_usage(agent_type);
```

---

## Phase 4: Multi-Agent Distribution

### 4.1 Claude Code Integration

Claude Code automatically reads `AGENTS.md` in your project:

```markdown
<!-- AGENTS.md -->

# Agent Integration Guide

This repository includes skills for AI coding agents.

## Available Skills

<available_skills>
- nixos-deployment: Comprehensive NixOS system deployment with 8-phase workflow
- ai-service-management: Control AI stack services (Ollama, Qdrant, MindsDB, Open WebUI)
- health-monitoring: Validate system health, check services, verify configurations
- ai-model-management: Manage AI models, download from Hugging Face, configure Ollama
- mcp-database-setup: Setup and manage PostgreSQL and Redis for MCP server
</available_skills>

## How to Use Skills

To load a skill, use:
```bash
openskills read <skill-name>
```

Example:
```bash
openskills read nixos-deployment
```

## Skill Categories

### System Management
- nixos-deployment
- health-monitoring

### AI Stack
- ai-service-management
- ai-model-management
- mcp-database-setup

## Progressive Learning

Skills use progressive disclosure:
1. You see the skill list above (low token cost)
2. When you need details, load the specific skill
3. Skills are cached after first load

## MCP Integration

All skills integrate with the AIDB MCP Server for:
- Tool execution
- State management
- Usage tracking
```

### 4.2 Local LLM Integration (Ollama)

For local LLMs via Ollama:

```bash
# Create wrapper script for Ollama agents
cat > ~/.local/bin/ollama-with-skills << 'EOF'
#!/usr/bin/env bash

# Ollama wrapper with OpenSkills support

# Load AGENTS.md as system prompt
AGENTS_CONTENT=$(cat ~/Documents/NixOS-Dev-Quick-Deploy/AGENTS.md)

# Construct system prompt
SYSTEM_PROMPT="You are an AI assistant with access to CLI tools via skills.

${AGENTS_CONTENT}

To learn about a skill, you can ask me to run:
openskills read <skill-name>

Available models via Ollama:
$(ollama list)
"

# Run ollama with skills context
ollama run phi4:latest "${SYSTEM_PROMPT}"
EOF

chmod +x ~/.local/bin/ollama-with-skills
```

### 4.3 Cursor/Windsurf Integration

These editors automatically detect `.skills/` and `AGENTS.md`:

1. **Cursor**: Reads AGENTS.md and exposes skills in the AI panel
2. **Windsurf**: Similar integration, auto-detects skill format
3. **Configuration**: No additional setup required

### 4.4 CLI Agent Integration (Aider)

```bash
# Aider configuration
cat > ~/.aider.conf.yml << 'EOF'
# Aider configuration with OpenSkills

# Load skills context
skills_file: AGENTS.md

# Enable skill discovery
enable_skills: true

# Skills directory
skills_dir: .skills/

# MCP server endpoint
mcp_server_url: http://localhost:8091/api/v1
EOF
```

---

## Best Practices

### Skill Design

1. **Clear, Concise Descriptions**
   - One sentence describing what the skill does
   - Focus on the "why" not the "how"

2. **Comprehensive Usage Section**
   - Common use cases
   - All command-line options
   - Expected output

3. **Error Handling**
   - Common errors and solutions
   - Troubleshooting steps
   - Related skills for debugging

4. **Examples**
   - At least 3 real-world examples
   - Copy-pasteable commands
   - Expected results

### Naming Conventions

- **Skill Names**: kebab-case (e.g., `nixos-deployment`)
- **Skill Files**: `SKILL.md` (uppercase)
- **Categories**: lowercase with hyphens (e.g., `system-management`)

### Version Control

```bash
# .gitignore additions
.openskills.json    # Local config
.skills/**/cache/   # Cached skill data

# .gitattributes for skills
*.md linguist-documentation=true
SKILL.md linguist-language=Markdown
```

### Documentation

Each skill should include:
- Description (1 sentence)
- When to use (scenarios)
- Prerequisites (dependencies)
- Usage (commands and options)
- Output interpretation
- Common errors
- Related skills
- Examples (3+)

---

## Maintenance & Updates

### Updating Skills

```bash
# Pull latest skills from marketplace
openskills update

# Sync local changes to AGENTS.md
openskills sync

# Rebuild skill cache
openskills cache rebuild
```

### Monitoring Skill Usage

Query PostgreSQL for skill analytics:

```sql
-- Most used skills
SELECT
    s.name,
    s.description,
    COUNT(su.id) as usage_count,
    COUNT(DISTINCT su.agent_type) as agent_types
FROM skills s
JOIN skill_usage su ON s.id = su.skill_id
GROUP BY s.id
ORDER BY usage_count DESC
LIMIT 10;

-- Skills by agent type
SELECT
    agent_type,
    COUNT(*) as skill_loads
FROM skill_usage
GROUP BY agent_type;
```

### Adding New CLI Tools

When you add a new CLI tool:

1. Create SKILL.md in `.skills/tool-name/`
2. Document thoroughly
3. Add to MCP server as tool
4. Update TOOL_SKILL_MAPPING
5. Run `openskills sync`
6. Commit to version control

### Skill Testing

```bash
# Test skill loading
openskills read nixos-deployment

# Test MCP integration
curl http://localhost:8091/api/v1/skills/read/nixos-deployment

# Test with Claude Code
# (Use /init command to load AGENTS.md context)
```

---

## Next Steps

### Immediate Actions

1. ✅ Install OpenSkills: `npm i -g openskills`
2. ✅ Initialize in project: `cd ~/Documents/NixOS-Dev-Quick-Deploy && openskills init`
3. ✅ Create first skill: `.skills/nixos-deployment/SKILL.md`
4. ✅ Sync to AGENTS.md: `openskills sync`
5. ✅ Test with Claude Code

### Short-Term Goals

1. Create SKILL.md for all 5 major CLI tools
2. Update AIDB MCP server with skills endpoint
3. Add PostgreSQL skills tracking
4. Test with local LLMs (Ollama)
5. Document in DEPLOYMENT-SUCCESS-V5.md

### Long-Term Vision

1. Publish skills to community marketplace
2. Auto-generate skills from man pages
3. Semantic skill search with Qdrant
4. Multi-language skill translations
5. Integration with CI/CD pipelines

---

## Troubleshooting

### OpenSkills Not Found

```bash
# Verify installation
npm list -g openskills

# Reinstall if needed
npm i -g openskills --force
```

### Skills Not Loading

```bash
# Check AGENTS.md exists
cat AGENTS.md

# Verify skills directory
ls -la .skills/

# Rebuild skill cache
openskills sync --force
```

### MCP Integration Issues

```bash
# Check MCP server logs
podman logs aidb-mcp

# Test API endpoint
curl http://localhost:8091/api/v1/skills/list

# Verify database connection
podman exec mcp-postgres psql -U mcp -d mcp -c "SELECT * FROM skills;"
```

---

## References

### Official Documentation
- [OpenSkills GitHub](https://github.com/numman-ali/openskills)
- [BandarLabs Open Skills](https://github.com/BandarLabs/open-skills)
- [Model Context Protocol](https://modelcontextprotocol.io/)
- [Anthropic Skills Marketplace](https://docs.anthropic.com/en/docs/skills)

### Your Project Documentation
- [MCP Setup Guide](./MCP_SETUP.md)
- [Deployment Success Report](../DEPLOYMENT-SUCCESS-V5.md)
- [System Improvements](../SYSTEM-IMPROVEMENTS-V5.md)
- [Research Report](./NIXOS-COMPREHENSIVE-RESEARCH-REPORT.md)

### External Resources
- [Claude Code Documentation](https://docs.anthropic.com/claude-code)
- [NixOS Manual](https://nixos.org/manual/)
- [Podman Documentation](https://docs.podman.io/)

---

## Appendix A: Complete Skill Template

```markdown
# Skill Name: [tool-name]

## Description
[One sentence describing what this skill does]

## When to Use
- [Use case 1]
- [Use case 2]
- [Use case 3]

## Prerequisites
- [Requirement 1]
- [Requirement 2]

## Usage

### Basic Command
\`\`\`bash
[basic command]
\`\`\`

### Advanced Options
\`\`\`bash
[command with options]
\`\`\`

## Command-Line Options
- `--option1`: [Description]
- `--option2`: [Description]

## Output Interpretation

### Success Indicators
- [Indicator 1]
- [Indicator 2]

### Common Errors
- **Error message**: [Solution]

## Related Skills
- `related-skill-1`: [Relationship]
- `related-skill-2`: [Relationship]

## MCP Integration
[How this skill integrates with AIDB MCP Server]

## Examples

### Example 1: [Scenario]
\`\`\`bash
[command]
\`\`\`
[Expected output]

### Example 2: [Scenario]
\`\`\`bash
[command]
\`\`\`
[Expected output]

### Example 3: [Scenario]
\`\`\`bash
[command]
\`\`\`
[Expected output]
```

---

## Appendix B: MCP Tool Registration Template

```python
# Tool registration template for AIDB MCP Server

from mcp_server.core import Tool, ToolCategory

class YourCliTool(Tool):
    """
    [Tool description]
    Corresponds to: .skills/[skill-name]/SKILL.md
    """

    name = "[tool-name]"
    description = "[Brief description]"
    category = ToolCategory.[CATEGORY]

    input_schema = {
        "type": "object",
        "properties": {
            "param1": {
                "type": "string",
                "description": "[Parameter description]"
            }
        },
        "required": ["param1"]
    }

    async def execute(self, **kwargs):
        """Execute CLI tool with parameters"""
        # Implementation
        pass
```

---

**Generated**: 2025-11-22 17:43
**Version**: 1.0.0
**Status**: ✅ READY FOR IMPLEMENTATION
