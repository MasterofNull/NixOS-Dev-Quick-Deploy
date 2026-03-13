# AI Stack Tooling Exposure
Status: Active
Owner: AI Stack Maintainers
Last Updated: 2026-03-07

This document explains how the AI stack tooling is exposed globally on NixOS
systems for use by **any AI agent** (Claude, GPT, Codex, Qwen, Gemini, Aider,
Continue, etc.) from any directory or project.

## Architecture Overview

The AI stack tooling is exposed through multiple discovery mechanisms:

```
┌─────────────────────────────────────────────────────────────────┐
│                 Agent-Agnostic Tool Discovery                    │
├─────────────────────────────────────────────────────────────────┤
│                                                                  │
│  1. Shell PATH                                                   │
│     └── All CLI tools in /run/current-system/sw/bin/            │
│                                                                  │
│  2. Environment Variables                                        │
│     └── AI_STACK_* variables exported in all shells             │
│                                                                  │
│  3. Discovery Manifest                                           │
│     └── /etc/ai-stack/agent-discovery.json                      │
│                                                                  │
│  4. HTTP Endpoints                                               │
│     └── http://127.0.0.1:8003/* (hints, query, workflow)        │
│                                                                  │
│  5. Agent-Specific Configs (optional)                            │
│     └── ~/.claude/settings.json (MCP)                           │
│     └── ~/.continue/config.json (context providers)             │
│     └── ~/.aider.conf.yml (shell integration)                   │
│                                                                  │
└─────────────────────────────────────────────────────────────────┘
```

## Universal Discovery Mechanisms

### 1. Shell PATH (All Agents)

CLI tools are available system-wide for any agent that can execute shell commands:

| Tool | Description |
|------|-------------|
| `aqd` | Main workflow CLI wrapper |
| `aq-hints` | Get ranked AI workflow hints |
| `aq-report` | AI stack health and metrics |
| `aq-qa` | Run QA workflow |
| `project-init` | Initialize new AI-enabled projects |
| `workflow-primer` | Read-only session priming |
| `workflow-brownfield` | Existing project improvement |
| `harness-rpc` | Node.js harness RPC bridge |

**Any agent** (GPT, Codex, Qwen, Gemini, etc.) can use these:
```bash
# Get hints for a task
aq-hints "how do I configure NixOS services"

# Initialize a new project
project-init --target ./my-project --name my-project --goal "build an app"

# Check available commands
ai_stack_tools
```

### 2. Environment Variables (All Agents)

Standard environment variables are exported for tool discovery:

| Variable | Value | Description |
|----------|-------|-------------|
| `AI_STACK_ROOT` | `/opt/nixos-quick-deploy` | Canonical installation path |
| `AI_STACK_TOOLS_BIN` | `/opt/nixos-quick-deploy/scripts/ai` | CLI tools directory |
| `AI_STACK_HINTS_ENDPOINT` | `http://127.0.0.1:8003/hints` | Hints API endpoint |
| `AI_STACK_HYBRID_ENDPOINT` | `http://127.0.0.1:8003` | Hybrid coordinator |
| `AI_STACK_AIDB_ENDPOINT` | `http://127.0.0.1:8002` | AIDB API |
| `AI_STACK_RALPH_ENDPOINT` | `http://127.0.0.1:8004` | Ralph loop orchestrator |
| `AI_STACK_WORKFLOW_ORCHESTRATE_ENDPOINT` | `http://127.0.0.1:8003/workflow/orchestrate` | Harness loop orchestration |
| `AI_STACK_INFERENCE_ENDPOINT` | `http://127.0.0.1:8080/v1` | LLM inference |

Example usage in any agent:
```bash
# Use environment variables to call APIs
curl -s "$AI_STACK_HINTS_ENDPOINT?query=nix+modules&max=3"
```

### 3. Discovery Manifest (All Agents)

A JSON manifest at `/etc/ai-stack/agent-discovery.json` provides structured
tool discovery for any agent that can read files:

```bash
cat /etc/ai-stack/agent-discovery.json | jq '.tools.cli'
```

### 4. HTTP Endpoints (All Agents)

Any agent with HTTP capabilities can call these endpoints directly:

| Endpoint | Method | Description |
|----------|--------|-------------|
| `/hints` | GET | Get workflow hints |
| `/query` | POST | Hybrid routing query |
| `/workflow/plan` | POST | Create execution plan |
| `/qa/check` | POST | Run bounded `aq-qa` validation via hybrid coordinator |
| `/research/web/fetch` | POST | Bounded polite public-web fetch -> extract lane for explicit URLs |
| `/workflow/orchestrate` | POST | Submit loop-orchestration work via harness |
| `/control/ai-coordinator/status` | GET | List coordinator runtime lanes and remote readiness |
| `/control/ai-coordinator/skills` | GET | List harness-approved shared skill catalog for local and delegated agents |
| `/control/ai-coordinator/delegate` | POST | Delegate a bounded task through the ai-coordinator |
| `/health` | GET | Check service health |

```bash
# Works from any agent that can run curl
curl -sf http://127.0.0.1:8003/hints?query=nixos+services

# Fetch explicit public pages through the bounded web-research lane
curl -s http://127.0.0.1:8003/research/web/fetch \
  -H 'Content-Type: application/json' \
  -d '{"urls":["https://example.com"],"selectors":["h1"],"max_text_chars":300}'

# Queue long-running agentic work through the harness layer
curl -s http://127.0.0.1:8003/workflow/orchestrate \
  -H 'Content-Type: application/json' \
  -d '{"prompt":"orchestrate a multi-agent repo remediation workflow"}'

# Inspect coordinator runtime lanes and delegate a bounded remote task
curl -s http://127.0.0.1:8003/control/ai-coordinator/status
curl -s http://127.0.0.1:8003/control/ai-coordinator/delegate \
  -H 'Content-Type: application/json' \
  -d '{"task":"summarize the tradeoffs for this NixOS routing change","profile":"remote-free"}'
```

### Harness SDKs

The hybrid coordinator SDKs now expose both planning and the coached query path:

- Python: `HarnessClient.plan(...)`, `HarnessClient.query(...)`, `HarnessClient.qa_check(...)`
- TypeScript/JavaScript: `HarnessClient.plan(...)`, `HarnessClient.query(...)`, `HarnessClient.qaCheck(...)`
- Python: `HarnessClient.web_research_fetch(...)` for bounded public-web extraction

That means SDK consumers receive the same `prompt_coaching` and token-discipline guidance that raw `POST /query` returns.

## Bounded Web Research Lane

The web research surface is intentionally narrow:
- explicit URL lists only, no recursive crawling
- SSRF-safe public egress checks
- robots-aware blocking when `robots.txt` is present
- same-host pacing, response-byte caps, text caps, and selector caps
- raw fetch/extract stays separate from model summarization

This keeps Continue/local-model research tasks usable without turning the harness into an unconstrained scraper.

## Planned Shared Skill Registry

Planned next-step surface:
- normalize third-party `SKILL.md` ecosystems, starting with `agentskill.sh`, through one harness-managed registry instead of per-agent manual installs
- store searchable skill metadata in AIDB
- expose approved skill visibility through the hybrid coordinator so local agents and delegated remote agents see the same catalog
- keep discovery separate from installation:
  - discovery/import metadata
  - local approval/risk gate
  - synchronized install/export into supported skill directories only after approval

Design constraints:
- upstream skill discovery or security scores are advisory, not sufficient trust on their own
- no agent should self-install unapproved third-party skills outside the harness approval path
- the approved shared-skill catalog should be consistent across Codex, Claude, Gemini, Continue-facing workflows, and remote delegation lanes

## Agent-Specific Integration

### Claude Code

Uses MCP (Model Context Protocol) servers. Configuration in `~/.claude/settings.json`:

```json
{
  "mcpServers": {
    "hybrid-coordinator": {
      "command": "python3",
      "args": ["/opt/nixos-quick-deploy/scripts/ai/mcp-bridge-hybrid.py"],
      "env": {
        "HYBRID_URL": "http://127.0.0.1:8003",
        "AIDB_URL": "http://127.0.0.1:8002"
      }
    }
  }
}
```

### OpenAI Codex / GPT

Uses shell commands via PATH. No special configuration needed:

```bash
# Codex/GPT can run these directly
aq-hints "implement user authentication"
aqd workflows list
```

### Qwen

Uses shell commands via PATH. No special configuration needed:

```bash
aq-hints "optimize database queries"
project-init --target ./new-api --name api --goal "REST API"
```

### Google Gemini

Uses shell commands via PATH. No special configuration needed:

```bash
aq-report --since 7d --format json
```

### Aider

Can use shell commands and environment variables. Optional config in `~/.aider.conf.yml`:

```yaml
# Aider can read AI_STACK_* environment variables
# and execute shell commands
auto-commits: true
```

Use with Aider:
```bash
aider --message "$(aq-hints 'fix the login bug')"
```

### Continue.dev

Uses HTTP context providers. Configuration managed by NixOS in `~/.continue/config.json`:

```json
{
  "contextProviders": [
    {
      "name": "aq-hints",
      "params": {
        "endpoint": "http://127.0.0.1:8003/hints"
      }
    }
  ]
}
```

## Canonical Paths

All configurations use the canonical symlink:

```
/opt/nixos-quick-deploy -> ${actual repo location}
```

This ensures:
1. Consistent paths across all configurations
2. Works regardless of actual repo location
3. Templates and scaffolding can use fixed paths

## Project Scaffolding

When initializing new projects with `project-init`, agent configurations are created:

```
project/
├── .agent/           # Agent-agnostic workflow artifacts
├── .claude/          # Claude-specific config (MCP)
│   └── settings.json
├── .agents/          # Multi-agent planning
└── CLAUDE.md         # Agent instructions
```

The scaffolded `.claude/settings.json` uses the canonical `/opt/nixos-quick-deploy` path.

## Quick Start by Agent Type

### Claude Code
```bash
# Already configured via ~/.claude/settings.json
# Harness and Ralph loop layers are available for automatic workflow selection.
```

### GPT / Codex / Qwen / Gemini
```bash
# Use CLI tools directly
aq-hints "your task description"
project-init --target ./new-project --name myproject --goal "goal"
```

### Aider
```bash
# Get hints and pass to aider
aider --message "$(aq-hints 'implement feature X')"
```

### Any Agent (via HTTP)
```bash
# Call hints API directly
curl -s "http://127.0.0.1:8003/hints?query=how+to+implement+auth&agent=generic"
```

## Troubleshooting

### Tools not found in PATH

```bash
# Verify tools are installed
which aqd aq-hints project-init

# Check AI stack role is enabled
nix eval .#nixosConfigurations.$(hostname)-ai-dev.config.mySystem.roles.aiStack.enable
```

### Environment variables not set

```bash
# Source the profile script
source /etc/profile.d/aq-path.sh

# Verify variables
env | grep AI_STACK
```

### HTTP endpoints not responding

```bash
# Check services
curl -sf http://127.0.0.1:8003/health
systemctl status ai-hybrid-coordinator ai-aidb
```

### Discovery manifest not found

```bash
# Check symlink
ls -la /opt/nixos-quick-deploy
ls -la /etc/ai-stack/agent-discovery.json
```

## After NixOS Rebuild

```bash
sudo nixos-rebuild switch --flake .#
```

This will:
1. Install CLI tool wrappers to PATH
2. Create `/opt/nixos-quick-deploy` symlink
3. Export `AI_STACK_*` environment variables
4. Install `/etc/ai-stack/agent-discovery.json`
5. Restart affected services
