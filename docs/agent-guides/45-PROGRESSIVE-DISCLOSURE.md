# Progressive Disclosure System

**Version:** 1.0.0
**Status:** Active
**Last Updated:** 2026-03-14

## Overview

The Progressive Disclosure system provides domain-aware, token-efficient context loading for AI agents. Instead of loading all available tools, hints, and skills for every query, it detects the work domain and loads only relevant context at the appropriate disclosure level.

## Work Domains

| Domain | Triggers | Description |
|--------|----------|-------------|
| `nixos-dev` | nix, nixos, flake, module, systemd | NixOS system configuration and modules |
| `web-dev` | react, vue, api, frontend, typescript | Web application development |
| `ai-harness` | mcp, agent, rag, workflow, hints | AI infrastructure and agent development |
| `data-engineering` | scrape, data, csv, visualization | Data scraping and analysis |
| `devops` | deploy, docker, ci, monitoring | DevOps and infrastructure |
| `security` | cve, vulnerability, harden, audit | Security and hardening |
| `documentation` | doc, readme, guide, tutorial | Documentation writing |

## Disclosure Levels

| Level | Token Budget | Use Case |
|-------|--------------|----------|
| `minimal` | ~500 | Quick lookups, simple tasks |
| `standard` | ~1500 | Implementation tasks |
| `full` | ~4000 | Complex multi-step tasks |

## Usage

### In Hints Engine

Domain context is automatically included in hint responses:

```json
{
  "hints": [...],
  "domain_context": {
    "available": true,
    "primary_domain": {
      "id": "nixos-dev",
      "name": "NixOS Development",
      "level": "standard",
      "context": "NixOS declarative system. Prefer module changes over scripts.",
      "tools": ["nix-build", "nixos-rebuild", "nix-shell"],
      "skills": ["nixos-deployment"],
      "token_estimate": 45
    },
    "compact_injection": "[NixOS Development] NixOS declarative system... | Tools: nix-build, nixos-rebuild | Skills: nixos-deployment"
  }
}
```

### Direct API Usage

```python
from progressive_disclosure import get_domain_loader, get_domain_context

# Get context for a query
contexts = get_domain_context("Help me configure a NixOS module for postgresql")

# Access domain loader directly
loader = get_domain_loader()
domains = loader.list_domains()
matches = loader.detect_domains("Build a React component")
```

### In Status Endpoint

The `/control/ai-coordinator/status` endpoint includes domain disclosure info:

```bash
curl -sS http://127.0.0.1:8003/control/ai-coordinator/status | jq '.domain_disclosure'
```

## Configuration

The domain configuration is stored in `config/progressive-disclosure-domains.json`:

```json
{
  "domains": {
    "nixos-dev": {
      "name": "NixOS Development",
      "triggers": ["nix", "nixos", "flake", ...],
      "disclosure": {
        "minimal": {
          "context": "...",
          "tools": [...],
          "hints": [...]
        },
        "standard": {
          "extends": "minimal",
          "tools": [...],
          "mcp_endpoints": [...],
          "skills": [...]
        },
        "full": {
          "extends": "standard",
          "research_packs": [...],
          "memory_recall": [...]
        }
      }
    }
  }
}
```

## Level Inheritance

Disclosure levels inherit from lower levels via `extends`:
- `minimal` → Base context
- `standard` → `minimal` + more tools, MCP endpoints, skills
- `full` → `standard` + research packs, memory recall keywords

## Auto-Detection

The disclosure level is auto-detected based on query complexity:

| Indicator | Level |
|-----------|-------|
| Simple lookups | `minimal` |
| "implement", "create", "build" | `standard` |
| "complex", "architecture", "security" | `full` |

## Token Efficiency

The system optimizes token usage by:

1. **Domain detection** - Only load context for matched domains
2. **Level escalation** - Start minimal, escalate as needed
3. **Compact injection** - One-line context strings for hints
4. **Capped lists** - Tools/skills capped at 5/3 items in responses

## Integration Points

| Component | Integration |
|-----------|-------------|
| Hints Engine | `domain_context` field in hint responses |
| Status Endpoint | `domain_disclosure` summary |
| MCP Handlers | Domain-aware tool suggestions |
| Memory Recall | Domain-specific recall keywords |

## Environment Variables

| Variable | Default | Description |
|----------|---------|-------------|
| `PROGRESSIVE_DISCLOSURE_CONFIG` | `config/progressive-disclosure-domains.json` | Config file path |

## Files

| Path | Purpose |
|------|---------|
| `config/progressive-disclosure-domains.json` | Domain configuration |
| `ai-stack/mcp-servers/hybrid-coordinator/progressive_disclosure.py` | Loader implementation |
| `ai-stack/mcp-servers/hybrid-coordinator/hints_engine.py` | Hints integration |

## Validation

```bash
# Test domain detection
curl -sS -X POST http://127.0.0.1:8003/hints \
  -H "Content-Type: application/json" \
  -d '{"query": "Configure NixOS module for nginx"}' | jq '.domain_context'

# Check available domains
curl -sS http://127.0.0.1:8003/control/ai-coordinator/status | jq '.domain_disclosure'
```
