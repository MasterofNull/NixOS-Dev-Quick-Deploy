# OpenSkills and MCP Server Inventory
**Date:** December 4, 2025
**System:** NixOS 25.11 (Xantusia)
**Status:** Comprehensive Inventory

---

## 📦 Installed OpenSkills (via openskills CLI)

**Version:** openskills 1.2.1

### Currently Active (Project-level Skills)

1. **ai-service-management** (project)
   - Status: Installed, no description
   - Location: Project-level

2. **aidb-knowledge** (project)
   - Status: Installed, no description
   - Location: Project-level
   - Purpose: AIDB knowledge base integration

3. **all-mcp-directory** (project)
   - Status: Installed
   - Purpose: Browse community MCP server directory
   - Useful for: Discovering new MCP servers

4. **brand-guidelines** (project)
   - Description: Applies Anthropic's official brand colors and typography
   - Use case: Artifacts requiring Anthropic look-and-feel

5. **canvas-design** (project)
   - Description: Create beautiful visual art in .png and .pdf documents
   - Use case: Posters, art, designs, static pieces

6. **frontend-design** (project)
   - Description: Create distinctive, production-grade frontend interfaces
   - Use case: Web components, pages, applications

7. **health-monitoring** (project)
   - Status: Installed, no description
   - Location: Project-level

8. **internal-comms** (project)
   - Description: Internal communications formatting
   - Use case: Status reports, updates, newsletters, FAQs, incident reports

9. **mcp-builder** (project)
   - Description: Guide for creating high-quality MCP servers
   - Use case: Building MCP servers in Python (FastMCP) or Node/TypeScript

10. **mcp-server** (project)
    - Status: Installed, no description
    - Location: Project-level

11. **nixos-deployment** (project)
    - Status: Installed, no description
    - Location: Project-level
    - Purpose: NixOS deployment automation

12. **pdf** (project)
    - Description: Comprehensive PDF manipulation toolkit
    - Use case: Extract text/tables, create PDFs, merge/split, handle forms

13. **pptx** (project)
    - Description: Presentation creation, editing, and analysis
    - Use case: Working with .pptx files

14. **project-import** (project)
    - Status: Installed, no description
    - Location: Project-level

15. **rag-techniques** (project)
    - Status: Installed, no description
    - Location: Project-level
    - Purpose: RAG (Retrieval-Augmented Generation) techniques

16. **skill-creator** (project)
    - Description: Guide for creating effective skills
    - Use case: Creating new skills or updating existing skills

---

## 📁 Local Skills Available

### In `.agent/skills/` (6 skills)

1. **aidb-knowledge**
   - AIDB knowledge base integration

2. **all-mcp-directory**
   - MCP server directory browser

3. **mcp-server**
   - MCP server templates/tools

4. **project-import**
   - Project import utilities

5. **rag-techniques**
   - RAG implementation patterns

6. **system_bootstrap**
   - System bootstrapping utilities

### In `.claude/skills/` (19 skills)

1. **ai-model-management**
   - AI model lifecycle management

2. **ai-service-management**
   - AI service orchestration

3. **brand-guidelines**
   - Anthropic brand styling

4. **canvas-design**
   - Visual design creation

5. **frontend-design**
   - Frontend interface development

6. **health-monitoring**
   - System health monitoring

7. **internal-comms**
   - Internal communications templates

8. **mcp-builder**
   - MCP server development guide

9. **mcp-database-setup**
   - MCP database configuration

10. **nixos-deployment**
    - NixOS deployment automation

11. **pdf**
    - PDF manipulation

12. **pptx**
    - PowerPoint operations

13. **skill-creator**
    - Skill development framework

14. **slack-gif-creator**
    - Animated GIF creation for Slack

15. **template-skill**
    - Skill template

16. **theme-factory**
    - Theme generation for artifacts

17. **webapp-testing**
    - Web application testing with Playwright

18. **web-artifacts-builder**
    - Complex HTML artifacts with React/Tailwind

19. **xlsx**
    - Spreadsheet operations

---

## 🔌 MCP Servers Available (Community Directory)

**Source:** GitHub search and verification

### ✅ Currently Installed

1. **mcp-nixos** ⭐⭐⭐⭐⭐ INSTALLED
   - **URL:** https://github.com/utensils/mcp-nixos
   - **PyPI:** https://pypi.org/project/mcp-nixos/
   - **Description:** Model Context Protocol Server for NixOS resources
   - **Tags:** nix, nixos, packages, options, home-manager, darwin
   - **Stars:** 354+ (actively maintained, updated Dec 4, 2025)
   - **Status:** ✅ INSTALLED via Nix at ~/.config/claude/mcp.json
   - **Features:**
     - Search 130K+ NixOS packages
     - Query 22K+ configuration options
     - Home Manager settings (4K+ options)
     - nix-darwin configurations (1K+ options)
     - Package version history via NixHub.io
   - **Installation Method:** `nix run github:utensils/mcp-nixos`
   - **Configuration:** Added to Claude Code MCP config

### Currently Documented (Not Installed)

2. **open-webui-tools**
   - **URL:** https://github.com/open-webui/open-webui/tree/main/packages/mcp-server
   - **Description:** Expose Open WebUI automation hooks to MCP clients
   - **Tags:** ops, ui
   - **Relevance:** ⭐⭐⭐ MEDIUM - Useful for AI UI automation

3. **stripe-mcp**
   - **URL:** https://github.com/stripe/mcp-server
   - **Description:** Interact with Stripe test accounts
   - **Tags:** finance, api
   - **Relevance:** ⭐ LOW - Not relevant to current work

4. **timescale-toolkit**
   - **URL:** https://github.com/timescale/toolkit-mcp
   - **Description:** Introspect TimescaleDB hypertables and run diagnostics
   - **Tags:** database, monitoring
   - **Relevance:** ⭐⭐ LOW-MEDIUM - Useful for time-series data

---

## 🎯 Recommended Additions for Current Work

### High Priority MCP Servers

#### 1. ✅ **mcp-nixos** - INSTALLED!
**Status:** Installed and configured in ~/.config/claude/mcp.json

**Available Tools:**
- `nixos_search(query, type, channel)` - Search packages, options, programs
- `nixos_info(name, type, channel)` - Get detailed package/option info
- `nixhub_package_versions(package, limit)` - Get version history with commit hashes
- `home_manager_search(query)` - Search Home Manager options
- `darwin_search(query)` - Search macOS nix-darwin options

**How to Use:**
After restarting Claude Code, the MCP server will be available. You can query NixOS packages, configuration options, and Home Manager settings directly.

#### 2. **PostgreSQL MCP Server**
**Why:** We have PostgreSQL/AIDB in our stack
**Use Cases:**
- Query AIDB directly
- Schema inspection
- Data validation
- Migrations

**Typical Installation:**
```bash
npm install -g @modelcontextprotocol/server-postgres
```

**Benefits:**
- Direct database access from AI agents
- Automated schema documentation
- Query optimization assistance
- Data migration support

#### 3. **GitHub MCP Server**
**Why:** Managing NixOS-Dev-Quick-Deploy repository
**Use Cases:**
- Create issues
- Manage PRs
- Review code
- Track deployment history

**Typical Installation:**
```bash
npm install -g @modelcontextprotocol/server-github
```

**Benefits:**
- Automated issue tracking
- PR creation from sessions
- Code review assistance
- Deployment documentation

#### 4. **Code Migration MCP Toolkit (Planned)**
**Why:** Support the Python → TypeScript modernization plan
**Use Cases (conceptual, to be implemented):**
- Discover Python helpers suitable as “model systems” for TS ports
- Summarize function contracts (inputs/outputs) into JSON schemas
- Propose TypeScript equivalents that match the Python behavior

**Integration Points:**
- Leverage `ts-dev` (`nix develop .#ts-dev`) as the standard TS environment
- Use AIDB + `aidb-knowledge` / `rag-techniques` skills for context and examples
- Coordinate work with `github-mcp` for branches and PRs once the toolkit exists

### High Priority OpenSkills

#### 1. **webapp-testing** (Already Available!)
**Location:** `.claude/skills/webapp-testing`
**Why Activate:** Test local web applications with Playwright
**Use Cases:**
- Test local-ai-stack UI
- Validate Open WebUI functionality
- Test Jupyter Lab interface
- Verify Gitea UI

**How to Activate:**
```bash
# Already in .claude/skills/, just needs to be used
# Reference in prompts: "use webapp-testing skill"
```

#### 2. **health-monitoring** (Already Installed!)
**Location:** `.claude/skills/health-monitoring`
**Why:** Align with new health check system
**Use Cases:**
- Monitor system metrics
- Track deployment health
- Alert on failures
- Performance tracking

#### 3. **ai-model-management** (Already Available!)
**Location:** `.claude/skills/ai-model-management`
**Why:** Manage local AI models
**Use Cases:**
- vLLM model management
- llama.cpp model tracking
- Model version control
- Performance monitoring

#### 4. **xlsx** (Already Available!)
**Location:** `.claude/skills/xlsx`
**Why:** Data analysis and reporting
**Use Cases:**
- System metrics reporting
- Deployment tracking
- Performance benchmarks
- Configuration inventories

**How to Use:**
```bash
# In Claude Code, reference the skill
# "use xlsx skill to create a deployment report"
```

---

## 🚀 Recommended MCP Servers for NixOS Development

### Additional Community Servers (Not Yet Installed)

#### 1. **filesystem-mcp**
**Purpose:** Enhanced file operations
**Why:** Better than raw file I/O
**Use Cases:**
- Template management
- Configuration file editing
- Backup operations
- Log analysis

#### 2. **git-mcp**
**Purpose:** Git operations via MCP
**Why:** Integrated version control
**Use Cases:**
- Automated commits
- Branch management
- Diff generation
- History tracking

#### 3. **docker-mcp / podman-mcp**
**Purpose:** Container management
**Why:** We use Podman extensively
**Use Cases:**
- Container health checks
- Image management
- Stack orchestration
- Log retrieval

**Note:** May need custom development for Podman-specific features

#### 4. **systemd-mcp**
**Purpose:** Systemd service management
**Why:** NixOS uses systemd heavily
**Use Cases:**
- Service status checks
- Journal log access
- Unit file validation
- Dependency analysis

**Note:** Would need custom development

---

## 📊 Skills Gap Analysis

### Skills We Have But Aren't Using Fully

1. **webapp-testing**
   - Available but not leveraged
   - Could test local-ai-stack UI
   - Validate deployment UIs

2. **health-monitoring**
   - Available but minimal documentation
   - Could integrate with system-health-check.sh
   - Automated health reports

3. **ai-model-management**
   - Available for llama.cpp model management
   - Not yet integrated with deployment

4. **mcp-database-setup**
   - Available for AIDB configuration
   - Not leveraged in deployment scripts

5. **xlsx**
   - Available for reporting
   - Could generate deployment reports
   - System metrics dashboards

### MCP Servers We Need

1. **nixpkgs-mcp** ⭐⭐⭐⭐⭐
   - Critical for NixOS work
   - Not installed

2. **postgres-mcp** ⭐⭐⭐⭐
   - Direct AIDB access
   - Not installed

3. **github-mcp** ⭐⭐⭐
   - Repository management
   - Not installed

4. **Custom: podman-mcp** ⭐⭐⭐⭐
   - Container management
   - Needs development

5. **Custom: systemd-mcp** ⭐⭐⭐⭐
   - Service management
   - Needs development

---

## 🎓 How to Activate Skills

### OpenSkills (Already Installed)

Skills are automatically available when using Claude Code. Reference them in prompts:

```
"Use the webapp-testing skill to test the Open WebUI interface"
"Use the xlsx skill to create a deployment metrics spreadsheet"
"Use the health-monitoring skill to check system status"
```

### Installing New MCP Servers

#### General Process

1. **Install via NPM:**
```bash
npm install -g @scope/mcp-server-name
```

2. **Configure MCP Client:**
Create or update `~/.config/claude/mcp.json`:
```json
{
  "mcpServers": {
    "server-name": {
      "command": "mcp-server-name",
      "args": []
    }
  }
}
```

3. **Restart Claude Code** to load new server

#### Example: Installing nixpkgs-mcp

```bash
# Install
npm install -g @nix-community/nixpkgs-mcp

# Configure
cat >> ~/.config/claude/mcp.json <<EOF
{
  "mcpServers": {
    "nixpkgs": {
      "command": "nixpkgs-mcp",
      "args": []
    }
  }
}
EOF

# Restart Claude Code
```

---

## 🔍 Quick Reference

### Check Installed Skills
```bash
openskills list
```

### Check Available Local Skills
```bash
ls ~/.claude/skills/
ls .agent/skills/
```

### Browse MCP Directory
```bash
python .agent/skills/all-mcp-directory/SKILL.md --refresh --limit 50
```

### Check NPM Global Packages
```bash
npm list -g --depth=0 | grep mcp
```

---

## 📝 Next Steps

### Immediate Actions

1. ✅ **Install mcp-nixos** (COMPLETED!)
   - Status: Installed and configured
   - Location: ~/.config/claude/mcp.json
   - Restart Claude Code to activate

2. **Activate webapp-testing skill**
   - Test local AI stack UIs
   - Validate deployments

3. **Install postgres-mcp** (High Priority)
   - Direct AIDB integration
   - Automated queries

4. **Document skill usage patterns**
   - Create examples
   - Integration guides

### Future Development

1. **Custom podman-mcp**
   - Container management
   - Stack orchestration
   - Log access

2. **Custom systemd-mcp**
   - Service management
   - Journal access
   - Unit validation

---

**Version:** 1.1.0
**Last Updated:** December 4, 2025 01:05 PST
**Maintainer:** NixOS-Dev-Quick-Deploy Project
**Status:** mcp-nixos Installed ✅

---

**For Questions:**
- Check `docs/MCP_SERVERS.md` for MCP server guide
- Check `docs/AVAILABLE_TOOLS.md` for complete tool inventory
- Query AIDB: `curl 'http://localhost:8091/documents?search=mcp&project=NixOS-Dev-Quick-Deploy'`
