# AIDB Agent Skills

This directory contains OpenSkills-format skill definitions for AIDB system management and usage.

Operational rule: apply system changes to `nixos-quick-deploy.sh` and templates first, then use runtime patches only for validation without rebuilding.

## Available Skills

### aidb-knowledge
Query and manage the AIDB knowledge base for project context, documentation, and code.

**Use when**: You need to access project documentation, search for code examples, or retrieve architectural decisions.

**Key capabilities**:
- Retrieve project context with filtering
- Full-text and semantic search
- Query hybrid memory system (vector + graph + events)
- Manage Zettelkasten-style agentic notes
- Track agent learning and corrections

### mcp-server
Operate and configure the AIDB Model Context Protocol server for Claude integration.

**Use when**: You need to integrate AIDB with Claude Desktop/Code, debug MCP connections, or manage the server.

**Key capabilities**:
- Start/stop MCP server
- Configure Claude Desktop and Claude Code clients
- Test MCP tools and resources
- Monitor server operations
- Troubleshoot connection issues

### project-import
Import existing project documentation and code into AIDB knowledge base.

**Use when**: Onboarding a new project, importing documentation, or populating the knowledge base.

**Key capabilities**:
- Auto-discover documentation and code files
- Bulk import with automatic tagging
- Organize content by type
- Generate import summaries
- Create document relationships

### all-mcp-directory
Discover MCP servers from allmcpservers.com and ingest them into the federation.

**Use when**: You need new MCP servers/tools/endpoints from the public directory, or to refresh federation discovery.

**Key capabilities**:
- Register the directory as a federated source
- Trigger a crawl to collect server links/metadata
- Prioritize discovered MCP servers for future tasks and skills

## Skill Organization

Skills follow the OpenSkills standard format:

```
skill-name/
└── SKILL.md
    ---
    name: skill-name
    description: What this does
    tags: [relevant, tags]
    version: 1.0.0
    ---
    # Instructions in imperative form
```

## Installation

These skills are already installed in `.agent/skills/`. To use with the `openskills` CLI:

```bash
# List installed skills
openskills list

# Read a skill
openskills read aidb-knowledge

# Sync to AGENTS.md
openskills sync
```

## Integration with Claude Code

These skills can be referenced in prompts to Claude Code:

```
Please use the aidb-knowledge skill to retrieve architecture documentation.
```

Claude Code will automatically load and follow the skill instructions.

## Creating Custom Skills

To create a new skill:

1. Create directory: `.agent/skills/your-skill-name/`
2. Add `SKILL.md` with YAML frontmatter
3. Write instructions in imperative form
4. Run `openskills sync` to update AGENTS.md

Example template:

```markdown
---
name: your-skill
description: Brief description
tags: [tag1, tag2]
version: 1.0.0
author: Your Name
---

# Skill Name

Description of what the skill does.

## Capabilities

- Capability 1
- Capability 2

## When to Use

Use this skill when...

## Instructions

Step-by-step instructions...

## References

- Link 1
- Link 2
```

## Skill Dependencies

Skills can reference each other:

- **project-import** depends on **aidb-knowledge** for verification
- **mcp-server** depends on **aidb-knowledge** for API access
- All skills assume AIDB API is running

## Environment Setup

Skills require these environment variables (from `deployment/podman/.env`):

- `AIDB_API_URL` - API base URL (default: http://localhost:8091)
- `AIDB_API_TOKEN` - Authentication token

## Maintenance

Update skills when:
- AIDB API endpoints change
- New features are added
- Bug fixes are discovered
- Best practices evolve

Version skills using semantic versioning (MAJOR.MINOR.PATCH).

## Contributing

To contribute a skill:

1. Follow the OpenSkills format
2. Test thoroughly
3. Document all capabilities
4. Provide examples
5. Update this AGENTS.md file

## Resources

- [OpenSkills GitHub](https://github.com/numman-ali/openskills)
- [Anthropic Skills](https://github.com/anthropics/skills)
- [AIDB Documentation](../docs/README.md)
- [MCP Specification](https://docs.claude.com/en/docs/mcp)
