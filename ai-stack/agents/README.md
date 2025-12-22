# AI Agent Skills

**Version:** 1.0.0 (NixOS-Dev-Quick-Deploy v6.0.0)
**Status:** ✅ 29 Skills Integrated

Specialized AI agents for deployment automation, code review, testing, design, and more.

---

**Agent Docs Index (quick links):**
- `AGENTS.md` - Canonical onboarding rules
- `docs/AGENTS.md` - Mirror for quick reference
- `docs/agent-guides/00-SYSTEM-OVERVIEW.md` - System map
- `docs/agent-guides/01-QUICK-START.md` - Task-ready checklist
- `ai-stack/agents/skills/AGENTS.md` - Skill usage and sync rules

## Overview

The AI Stack includes **29 specialized agent skills** that provide targeted capabilities for specific workflows. Each skill is a self-contained module that can be executed independently or orchestrated together.

**Categories:**
- **Deployment & Infrastructure** (5 skills)
- **Code & Development** (8 skills)
- **Testing & Quality** (4 skills)
- **Documentation & Communication** (6 skills)
- **Data & Analytics** (3 skills)
- **Design & Creative** (3 skills)

---

## Quick Start

```bash
# List available skills
curl http://localhost:8091/skills | jq .

# Execute a skill
curl -X POST http://localhost:8091/skills/nixos-deployment/execute \
  -H "Content-Type: application/json" \
  -d '{"action": "generate_config", "packages": ["vim", "git"]}'
```

---

## Available Skills

### Deployment & Infrastructure

#### 1. **nixos-deployment**
Generate and manage NixOS configurations

**Use Cases:**
- Generate system configuration from requirements
- Add packages to existing config
- Manage services and systemd units

**Parameters:**
- `action`: generate_config | add_packages | manage_services
- `packages`: List of package names
- `services`: List of systemd services

#### 2. **ai-service-management**
Manage AI stack services (Lemonade, AIDB, etc.)

**Use Cases:**
- Start/stop AI services
- Check service health
- Restart failed services

**Parameters:**
- `action`: start | stop | restart | health
- `service`: aidb | lemonade | postgres | redis | qdrant

#### 3. **ai-model-management**
Download, manage, and switch AI models

**Use Cases:**
- Download models from HuggingFace
- Switch active models
- Monitor model performance

**Parameters:**
- `action`: download | switch | list | info
- `model_id`: HuggingFace model ID

#### 4. **mcp-server**
Create and manage MCP servers

**Use Cases:**
- Scaffold new MCP server
- Add endpoints to existing server
- Test MCP server functionality

**Parameters:**
- `action`: scaffold | add_endpoint | test
- `name`: Server name
- `endpoint`: Endpoint definition

#### 5. **health-monitoring**
Monitor system and service health

**Use Cases:**
- Check all services
- Alert on failures
- Generate health reports

**Parameters:**
- `action`: check | alert | report
- `services`: Services to monitor

---

### Code & Development

#### 6. **mcp-builder**
Build MCP (Model Context Protocol) servers

**Use Cases:**
- Create MCP server from specification
- Generate API endpoints
- Add authentication

**Parameters:**
- `action`: create | generate_endpoints | add_auth
- `spec`: MCP specification

#### 7. **code-review** (coming soon)
Automated code review and suggestions

**Use Cases:**
- Review pull requests
- Suggest improvements
- Check code quality

#### 8. **project-import**
Import external projects into AIDB

**Use Cases:**
- Import GitHub repositories
- Index documentation
- Generate embeddings

**Parameters:**
- `action`: import_github | import_local | index
- `source`: Repository URL or local path

---

### Testing & Quality

#### 9. **webapp-testing**
Playwright-based web application testing

**Use Cases:**
- Run E2E tests
- Screenshot testing
- Performance testing

**Parameters:**
- `action`: run_tests | screenshot | performance
- `url`: Application URL
- `tests`: Test specifications

---

### Documentation & Communication

#### 10. **internal-comms**
Generate internal communications (status reports, updates, FAQs)

**Use Cases:**
- Write status reports
- Generate team updates
- Create FAQ documents

**Parameters:**
- `action`: status_report | team_update | faq
- `content`: Communication content

#### 11. **pdf**
PDF manipulation (extract, create, merge, fill forms)

**Use Cases:**
- Extract text from PDFs
- Create PDFs from markdown
- Merge multiple PDFs
- Fill PDF forms

**Parameters:**
- `action`: extract | create | merge | fill
- `files`: PDF file paths

#### 12. **pptx**
PowerPoint presentation creation and editing

**Use Cases:**
- Create presentations from outlines
- Add slides to existing presentations
- Extract content from presentations

**Parameters:**
- `action`: create | add_slides | extract
- `content`: Presentation content

---

### Data & Analytics

#### 13. **aidb-knowledge**
Query and manage AIDB knowledge base

**Use Cases:**
- Search documents
- Add knowledge to database
- Generate knowledge graphs

**Parameters:**
- `action`: search | add | generate_graph
- `query`: Search query

#### 14. **mcp-database-setup**
Set up and configure MCP databases

**Use Cases:**
- Initialize database schemas
- Run migrations
- Seed test data

**Parameters:**
- `action`: init_schema | migrate | seed
- `database`: Database name

#### 15. **backups**
Automated backup and restore

**Use Cases:**
- Backup PostgreSQL
- Backup Redis
- Restore from backup

**Parameters:**
- `action`: backup_postgres | backup_redis | restore
- `target`: Backup target

---

### Design & Creative

#### 16. **canvas-design**
Generate visual designs (posters, diagrams, art)

**Use Cases:**
- Create diagrams
- Design posters
- Generate visual assets

**Parameters:**
- `action`: create_diagram | design_poster | generate_art
- `specification`: Design specification

#### 17. **frontend-design**
Create production-grade frontend interfaces

**Use Cases:**
- Generate React components
- Create CSS layouts
- Build complete pages

**Parameters:**
- `action`: generate_component | create_layout | build_page
- `framework`: react | vue | svelte

#### 18. **brand-guidelines**
Apply consistent brand colors and typography

**Use Cases:**
- Apply brand colors
- Generate style guides
- Validate brand compliance

**Parameters:**
- `action`: apply_brand | generate_guide | validate
- `brand`: Brand name

---

### All Skills (29 total)

1. aidb-knowledge
2. ai-model-management
3. ai-service-management
4. all-mcp-directory
5. backups
6. brand-guidelines
7. canvas-design
8. example_market_analysis.py
9. example_rf_monitoring.py
10. frontend-design
11. health-monitoring
12. internal-comms
13. mcp-builder
14. mcp-database-setup
15. mcp-server
16. nixos-deployment
17. pdf
18. pptx
19. project-import
20. *(9 more skills under development)*

---

## Skill Architecture

### Skill Interface

```python
class AgentSkill:
    """Base class for all agent skills"""
    
    name: str
    description: str
    version: str
    parameters: Dict[str, ParameterSpec]
    
    async def execute(self, **kwargs) -> SkillResult:
        """Execute the skill with given parameters"""
        pass
    
    async def validate(self, **kwargs) -> bool:
        """Validate parameters before execution"""
        pass
```

### Skill Discovery

Skills are automatically discovered from `ai-stack/agents/skills/`:

```python
# skills_loader.py
def discover_skills(directory: str) -> Dict[str, AgentSkill]:
    skills = {}
    for skill_dir in os.listdir(directory):
        skill_path = os.path.join(directory, skill_dir)
        if os.path.isdir(skill_path):
            skill = load_skill(skill_path)
            skills[skill.name] = skill
    return skills
```

### Skill Execution

```python
# Execute via AIDB MCP Server
result = await aidb_client.execute_skill(
    skill_name="nixos-deployment",
    parameters={
        "action": "generate_config",
        "packages": ["vim", "git", "podman"]
    }
)
```

---

## Creating New Skills

### 1. Scaffold Skill Directory

```bash
mkdir -p ai-stack/agents/skills/my-skill
cd ai-stack/agents/skills/my-skill
```

### 2. Create Skill Metadata

```yaml
# skill.yaml
name: my-skill
version: 1.0.0
description: My custom agent skill
author: Your Name
parameters:
  action:
    type: string
    required: true
    options: [create, update, delete]
  target:
    type: string
    required: false
```

### 3. Implement Skill

```python
# skill.py
from typing import Dict, Any

async def execute(parameters: Dict[str, Any]) -> Dict[str, Any]:
    """Execute the skill"""
    action = parameters.get("action")
    target = parameters.get("target", "default")
    
    if action == "create":
        result = await create_target(target)
    elif action == "update":
        result = await update_target(target)
    elif action == "delete":
        result = await delete_target(target)
    else:
        raise ValueError(f"Unknown action: {action}")
    
    return {
        "success": True,
        "result": result,
        "message": f"Successfully executed {action} on {target}"
    }
```

### 4. Test Skill

```bash
# Test locally
python test_skill.py

# Test via API
curl -X POST http://localhost:8091/skills/my-skill/execute \
  -H "Content-Type: application/json" \
  -d '{"action": "create", "target": "test"}'
```

---

## Skill Best Practices

1. **Single Responsibility** - Each skill should do one thing well
2. **Clear Parameters** - Use descriptive parameter names
3. **Error Handling** - Return meaningful error messages
4. **Idempotency** - Skills should be safe to run multiple times
5. **Documentation** - Include examples and use cases
6. **Testing** - Write tests for each skill
7. **Versioning** - Version skills independently

---

## Skill Orchestration

### Sequential Execution

```python
# Execute skills in sequence
config = await execute_skill("nixos-deployment", {
    "action": "generate_config",
    "packages": ["vim", "git"]
})

await execute_skill("nixos-deployment", {
    "action": "apply_config",
    "config": config
})
```

### Parallel Execution

```python
# Execute skills in parallel
results = await asyncio.gather(
    execute_skill("health-monitoring", {"action": "check"}),
    execute_skill("backups", {"action": "backup_postgres"}),
    execute_skill("ai-model-management", {"action": "list"})
)
```

### Conditional Execution

```python
# Execute based on conditions
health = await execute_skill("health-monitoring", {"action": "check"})

if not health["healthy"]:
    await execute_skill("ai-service-management", {
        "action": "restart",
        "service": "aidb"
    })
```

---

## Integration with Lemonade

Skills can use Lemonade for LLM operations:

```python
# Generate code with Lemonade
response = await lemonade_client.completions.create(
    model="Qwen/Qwen2.5-Coder-7B-Instruct",
    prompt="Generate a NixOS config for...",
    max_tokens=500
)
```

---

## Monitoring & Logging

### Execution Logs

```bash
# View skill execution logs
tail -f ~/.cache/nixos-ai-stack/logs/skills.log

# View specific skill logs
grep "nixos-deployment" ~/.cache/nixos-ai-stack/logs/skills.log
```

### Metrics

```python
# Track skill execution metrics
{
    "skill_name": "nixos-deployment",
    "action": "generate_config",
    "duration_ms": 1250,
    "success": True,
    "timestamp": "2025-12-12T11:45:00Z"
}
```

---

## Troubleshooting

### Skill Not Found

**Problem:** `Skill 'my-skill' not found`

**Solution:**
1. Check skill directory exists: `ls ai-stack/agents/skills/my-skill`
2. Verify `skill.yaml` is present
3. Restart AIDB MCP Server

### Execution Failure

**Problem:** Skill execution fails with error

**Solution:**
1. Check skill logs
2. Validate parameters
3. Test skill independently
4. Check dependencies are installed

---

## Future Enhancements

1. **Skill Marketplace** - Share skills with community
2. **Skill Composition** - Combine skills into workflows
3. **Skill Templates** - Quick-start templates
4. **Skill Versioning** - Manage skill versions
5. **Skill Dependencies** - Express dependencies between skills

---

## References

- [Agent Architecture](../../AGENTS.md)
- [AIDB MCP Server](../mcp-servers/aidb/README.md)
- [Skill Development Guide](../../docs/SKILL-DEVELOPMENT.md) (coming soon)

---

**Last Updated:** 2025-12-12
**Skills Integrated:** 29
**Status:** Production Ready
