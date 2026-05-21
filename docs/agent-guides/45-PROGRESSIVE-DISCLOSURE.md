# Progressive Disclosure System

**Version:** 2.0.0
**Status:** Active (Phase 58+)
**Last Updated:** 2026-05-20
**Owner:** AI Stack Maintainers

## Overview

The Progressive Disclosure system provides domain-aware, token-efficient context loading for AI agents. Instead of loading all available tools, hints, and skills for every query, it detects the work domain and loads only relevant context at the appropriate disclosure level. This approach achieves up to a **90% reduction in discovery overhead** while ensuring agents have the necessary signal for complex tasks.

## Core Philosophy

1.  **Start Minimal**: Provide only the baseline repository contract and basic system info.
2.  **Expand on Demand**: Escalate to higher disclosure levels only when a concrete gap is identified.
3.  **Domain-Centric**: Load specialized tools and rules only for the relevant work domain (e.g., NixOS, Security).
4.  **Token Budgeting**: Enforce strict token limits for each disclosure level to prevent context bloat.

## Work Domains

The system recognizes 7 primary domains based on query triggers:

| Domain | Triggers | Description |
|--------|----------|-------------|
| `nixos-dev` | nix, nixos, flake, module, systemd | NixOS system configuration and modules |
| `web-dev` | react, api, frontend, typescript | Web application development and APIs |
| `ai-harness` | mcp, agent, rag, workflow, hints | AI infrastructure and agent development |
| `data-engineering` | scrape, data, csv, parse | Data scraping, ETL, and analysis |
| `devops` | deploy, ci, docker, monitoring | System operations and infrastructure |
| `security` | cve, vulnerability, harden, audit | Security hardening and audits |
| `documentation` | doc, readme, guide, tutorial | Technical writing and documentation |

## Disclosure Levels

| Level | Token Budget | Use Case |
|-------|--------------|----------|
| `minimal` | ~500 | Quick lookups, simple inquiries, baseline orientation |
| `standard` | ~1500 | Implementation tasks, standard feature development |
| `full` | ~4000 | Architecture redesign, complex debugging, security audits |

## Primary Operator Tools (`aq-*`)

The system is controlled and queried via the following CLI tools:

| Tool | Purpose | Typical Usage |
|------|---------|---------------|
| `aq-prime` | **Onboarding Entrypoint**. Primes the agent with context. | `aq-prime` |
| `aq-hints` | **Workflow Guidance**. Retrieves ranked hints for a task. | `aq-hints "task description"` |
| `aq-context-bootstrap` | **Task Classification**. Suggests domain and level. | `aq-context-bootstrap --task "..."` |
| `aq-context-card` | **Layered Context**. Generates specific context "cards". | `aq-context-card --card repo-baseline` |
| `aq-qa --layer <N>` | **Layered Validation**. Checks health at specific layers. | `aq-qa --layer 0` (Core Services) |

## Usage Patterns

### 1. Initial Onboarding (Step 1 of Canonical Workflow)
For any new task, the agent should start with minimal disclosure:
```bash
aq-prime                                # Load baseline context
aq-hints "Configure a NixOS module"     # Get domain-specific workflow hints
```

### 2. Task Classification & Escalation
If the task is complex, use bootstrap to determine the correct level:
```bash
aq-context-bootstrap --task "Audit the AppArmor policy for the coordinator"
# System suggests: Domain: security | Level: standard or full
```

### 3. Direct Capability Discovery
Agents can discover available system capabilities via the Discovery API (Port 8003):
```bash
# List standard capabilities
curl -sS http://127.0.0.1:8003/discovery/capabilities?level=standard

# Check system status and domain disclosure
curl -sS http://127.0.0.1:8003/control/ai-coordinator/status | jq '.domain_disclosure'
```

### 4. Layered Health Checks (Phase 58+)
Progressive disclosure extends to system validation. Use `aq-qa` with layers to focus on specific subsystems:
- **Layer 0**: Core Services (llama, redis, postgres)
- **Layer 1**: Data Stores (qdrant, aidb)
- **Layer 2**: Orchestration (coordinator, ralph)
- **Layer 3**: Agent Runtime (switchboard, terminal)

## Configuration

Domain mapping and disclosure content are managed in `config/progressive-disclosure-domains.json`.

```json
{
  "domains": {
    "nixos-dev": {
      "disclosure": {
        "minimal": { "tools": ["nix-build", "nixos-rebuild"], "hints": ["Keep changes declarative"] },
        "standard": { "extends": "minimal", "skills": ["nixos-deployment"] }
      }
    }
  }
}
```

## Integration Points

| Component | Integration Detail |
|-----------|--------------------|
| **Hybrid Coordinator** | Main logic for domain detection and context assembly. |
| **AIDB** | Source for capability schemas and tool discovery. |
| **Hints Engine** | Injects `domain_context` into all ranked workflow responses. |
| **Dashboard** | Visualizes "Layered Health" status and token savings. |

## Files & Resources

- **Config**: `config/progressive-disclosure-domains.json`
- **Logic**: `ai-stack/mcp-servers/hybrid-coordinator/knowledge/progressive_disclosure.py`
- **Endpoints**: `ai-stack/mcp-servers/hybrid-coordinator/server.py`
- **CLI Sources**: `scripts/ai/aq-prime`, `scripts/ai/aq-hints`, etc.

## Validation

```bash
# Verify domain detection for a query
aq-hints "Build a React frontend for the dashboard" --format=json | jq '.domain_context'

# Verify layered health (Phase 58 baseline)
aq-qa 0
```
