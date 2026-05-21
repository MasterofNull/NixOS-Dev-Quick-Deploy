# Agent-Agnostic Tooling Consolidation Plan
**Date:** December 4, 2025
**Version:** 1.0.0
**Goal:** Unified, AI-agent/model-agnostic tooling accessible to all agents

> Status: historical planning document.
>
> This file contains legacy `.claude/` references kept for audit context.
> Active policy and implementation are defined in:
> - `docs/REPOSITORY-SCOPE-CONTRACT.md`
> - `docs/SKILL-BACKUP-POLICY.md`
> - `docs/AQD-CLI-USAGE.md`

---

## 🎯 Current State Analysis

### Skills Directory Fragmentation

**Problem:** Two separate skill directories with no overlap

1. **`.agent/skills/` (6 skills)** - Custom project skills
   - aidb-knowledge
   - all-mcp-directory
   - mcp-server
   - project-import
   - rag-techniques
   - system_bootstrap

2. **`.claude/skills/` (19 skills)** - Claude Code managed skills
   - ai-model-management, ai-service-management, brand-guidelines
   - canvas-design, frontend-design, health-monitoring
   - internal-comms, mcp-builder, mcp-database-setup
   - nixos-deployment, pdf, pptx, skill-creator
   - slack-gif-creator, template-skill, theme-factory
   - webapp-testing, web-artifacts-builder, xlsx

### Claude Code Skill Loading Hierarchy

Claude Code automatically loads from:
1. **System:** `/etc/claude-code/.claude/skills` (managed)
2. **User:** `~/.claude/skills`
3. **Project:** `.claude/skills` (this directory)

**Issue:** `.agent/skills/` is not automatically discovered by Claude Code.

### MCP Server Configuration

**Current:** `~/.config/claude/mcp.json` (Claude-specific)
**Issue:** Other AI agents won't discover MCP servers here.

---

## ✅ Consolidation Strategy

### Phase 1: Skills Consolidation

#### Option A: Use .claude/skills as Canonical (Recommended)

**Why:**
- Already discovered by Claude Code automatically
- Standard location for managed skills
- Follows established conventions

**Implementation:**
```bash
# Move custom skills from .agent/skills/ to .claude/skills/
cd ~/Documents/NixOS-Dev-Quick-Deploy

# Copy custom skills (no overlap, safe to merge)
for skill in .agent/skills/*; do
    skill_name=$(basename "$skill")
    if [ ! -d ".claude/skills/$skill_name" ]; then
        echo "Moving $skill_name to .claude/skills/"
        cp -r "$skill" .claude/skills/
    fi
done

# Verify all skills present
ls .claude/skills/
```

**Resulting Structure:**
```
.claude/skills/
├── aidb-knowledge          (from .agent)
├── ai-model-management
├── ai-service-management
├── all-mcp-directory       (from .agent)
├── brand-guidelines
├── canvas-design
├── frontend-design
├── health-monitoring
├── internal-comms
├── mcp-builder
├── mcp-database-setup
├── mcp-server              (from .agent)
├── nixos-deployment
├── pdf
├── pptx
├── project-import          (from .agent)
├── rag-techniques          (from .agent)
├── skill-creator
├── slack-gif-creator
├── system_bootstrap        (from .agent)
├── template-skill
├── theme-factory
├── webapp-testing
├── web-artifacts-builder
└── xlsx
```

**Total:** 25 unified skills

#### Option B: Use ~/.ai-agent-tools/ as Universal Location

**Why:**
- Agent-agnostic name
- Can be symlinked by all AI tools
- Centralized, system-wide access

**Implementation:**
```bash
# Create universal skills directory
mkdir -p ~/.ai-agent-tools/skills/
mkdir -p ~/.ai-agent-tools/mcp-servers/

# Copy all skills to universal location
cp -r .claude/skills/* ~/.ai-agent-tools/skills/
cp -r .agent/skills/* ~/.ai-agent-tools/skills/

# Symlink from various agent locations
ln -sf ~/.ai-agent-tools/skills ~/.claude/skills
ln -sf ~/.ai-agent-tools/skills .agent/skills
ln -sf ~/.ai-agent-tools/skills ~/.agent/skills

# Future agents can also symlink:
# ln -sf ~/.ai-agent-tools/skills ~/.openai/skills
# ln -sf ~/.ai-agent-tools/skills ~/.cursor/skills
```

**Recommendation:** Use Option A initially (simpler), then migrate to Option B for true agent-agnosticity.

---

## 🔌 MCP Server Standardization

### Current Issue: Claude-Specific Configuration

**File:** `~/.config/claude/mcp.json`
**Format:**
```json
{
  "mcpServers": {
    "nixos": {
      "command": "nix",
      "args": ["run", "github:utensils/mcp-nixos", "--"]
    }
  }
}
```

**Problem:** Only Claude Code reads this configuration.

### Universal MCP Configuration Strategy

#### Standard Location: ~/.mcp/config.json

**Create agent-agnostic MCP configuration:**
```bash
mkdir -p ~/.mcp/
```

**File:** `~/.mcp/config.json`
```json
{
  "version": "1.0",
  "mcpServers": {
    "nixos": {
      "type": "nix",
      "command": "nix",
      "args": ["run", "github:utensils/mcp-nixos", "--"],
      "description": "NixOS package and config search",
      "tags": ["nix", "nixos", "packages"]
    },
    "postgres": {
      "type": "database",
      "command": "npx",
      "args": ["-y", "@modelcontextprotocol/server-postgres"],
      "env": {
        "POSTGRES_URL": "postgresql://localhost:5432/aidb"
      },
      "description": "PostgreSQL/AIDB integration",
      "tags": ["database", "postgresql", "aidb"]
    },
    "github": {
      "type": "api",
      "command": "npx",
      "args": ["-y", "@modelcontextprotocol/server-github"],
      "env": {
        "GITHUB_TOKEN": "${GITHUB_TOKEN}"
      },
      "description": "GitHub repository management",
      "tags": ["git", "github", "repository"]
    }
  }
}
```

#### Symlink Strategy for Agent Compatibility

```bash
# Claude Code
ln -sf ~/.mcp/config.json ~/.config/claude/mcp.json

# Future agents can also link:
# ln -sf ~/.mcp/config.json ~/.cursor/mcp.json
# ln -sf ~/.mcp/config.json ~/.openai/mcp.json
# ln -sf ~/.mcp/config.json ~/.aider/mcp.json
```

---

## 🛡️ Security Auditing MCP Servers (Phase 2)

### High Priority Security Tools

#### 1. SecureMCP ⭐⭐⭐⭐⭐ (132 stars)
**Repository:** https://github.com/makalin/SecureMCP
**Purpose:** Security auditing tool for MCP itself
**Features:**
- OAuth token leakage detection
- Prompt injection vulnerability detection
- Rogue MCP server detection
- Tool poisoning attack prevention

**Installation:**
```bash
# Clone and install
git clone https://github.com/makalin/SecureMCP
cd SecureMCP
npm install
npm link

# Configure in ~/.mcp/config.json
{
  "securemcp": {
    "command": "securemcp",
    "args": ["audit"],
    "description": "MCP security auditing and threat detection"
  }
}
```

**Use Cases:**
- Audit all MCP servers before deployment
- Detect security vulnerabilities in MCP configurations
- Monitor for prompt injection attacks
- Validate OAuth token handling

#### 2. mcp-snitch ⭐⭐⭐⭐ (85 stars)
**Repository:** https://github.com/Adversis/mcp-snitch
**Purpose:** macOS MCP traffic interceptor and monitor
**Features:**
- Intercepts MCP server communications
- Security analysis of tool calls
- Access control for MCP tools
- Audit logging for AI tool usage

**Installation:**
```bash
# macOS only - download from releases
# Or build from source:
git clone https://github.com/Adversis/mcp-snitch
cd mcp-snitch
make install
```

**Note:** macOS-specific, but concept can be adapted for Linux with eBPF/auditd

#### 3. mcp-security-audit ⭐⭐⭐ (47 stars)
**Repository:** https://github.com/qianniuspace/mcp-security-audit
**Purpose:** npm package vulnerability auditing via MCP
**Features:**
- Real-time security checks against npm registry
- CVE database integration
- Dependency vulnerability scanning
- Remediation recommendations

**Installation:**
```bash
npm install -g mcp-security-audit

# Configure
{
  "npm-security": {
    "command": "mcp-security-audit",
    "args": ["--registry", "https://registry.npmjs.org"],
    "description": "npm package security auditing"
  }
}
```

#### 4. vulnicheck ⭐⭐ (8 stars, but comprehensive)
**Repository:** https://github.com/andrasfe/vulnicheck
**Purpose:** Python vulnerability scanner + MCP security toolkit
**Features:**
- Real-time dependency checking (OSV, NVD, GitHub Advisory)
- Docker container analysis
- Secrets detection
- MCP config validation
- LLM-powered risk assessment
- CVE details with CVSS scores

**Installation:**
```bash
pip install vulnicheck

# Configure
{
  "vulnicheck": {
    "command": "vulnicheck",
    "args": ["--mode", "mcp"],
    "description": "Multi-source vulnerability scanning and secrets detection"
  }
}
```

#### 5. lighthouse-mcp-server ⭐⭐ (28 stars)
**Repository:** https://github.com/danielsogl/lighthouse-mcp-server
**Purpose:** Web security, performance, and SEO auditing
**Features:**
- Google Lighthouse integration
- 13+ audit tools
- Performance analysis
- Accessibility checking
- SEO validation
- Security headers analysis

**Installation:**
```bash
npm install -g lighthouse-mcp-server

# Configure
{
  "lighthouse": {
    "command": "lighthouse-mcp-server",
    "args": [],
    "description": "Web security, performance, and accessibility audits"
  }
}
```

**Use Cases:**
- Audit local-ai-stack web UIs
- Validate Open WebUI security
- Test Jupyter Lab accessibility
- Check Gitea web interface

#### 6. mcp-cloud-compliance (5 stars, AWS-focused)
**Repository:** https://github.com/uprightsleepy/mcp-cloud-compliance
**Purpose:** AWS security posture auditing
**Features:**
- Natural language security queries
- AWS configuration analysis
- Compliance checking
- Security posture reporting

**Installation:**
```bash
npm install -g mcp-cloud-compliance

# Configure
{
  "aws-compliance": {
    "command": "mcp-cloud-compliance",
    "args": [],
    "env": {
      "AWS_PROFILE": "default"
    },
    "description": "AWS security compliance auditing"
  }
}
```

**Note:** Not currently using AWS, but useful for future cloud deployments.

---

## 📋 Implementation Roadmap

### Phase 1: Skills Consolidation (Immediate)

**Tasks:**
1. ✅ Analyze current state (complete)
2. Move `.agent/skills/` to `.claude/skills/`
3. Verify all 25 skills load in Claude Code
4. Update documentation
5. Remove empty `.agent/skills/` directory (or symlink it)

**Time:** 15 minutes
**Risk:** Low (no overlap, just moving files)

### Phase 2: MCP Server Standardization (High Priority)

**Tasks:**
1. Create `~/.mcp/config.json` with standardized format
2. Migrate existing mcp-nixos configuration
3. Add postgres-mcp configuration
4. Add github-mcp configuration
5. Create symlink: `~/.config/claude/mcp.json` → `~/.mcp/config.json`
6. Test all MCP servers load correctly

**Time:** 30 minutes
**Risk:** Low (symlinks preserve existing functionality)

### Phase 3: Security MCP Servers Installation (Next Phase)

**Priority Order:**
1. **SecureMCP** (audit existing MCP servers first)
2. **vulnicheck** (scan dependencies and secrets)
3. **lighthouse-mcp-server** (audit web UIs)
4. **mcp-security-audit** (npm package scanning)

**Tasks:**
1. Install SecureMCP
2. Audit current MCP server configurations
3. Fix any detected vulnerabilities
4. Install vulnicheck
5. Scan NixOS-Dev-Quick-Deploy codebase
6. Install lighthouse-mcp-server
7. Audit local-ai-stack UIs
8. Document all security findings

**Time:** 2-3 hours
**Risk:** Medium (may discover vulnerabilities requiring fixes)

### Phase 4: Agent-Agnostic Infrastructure (Future)

**Tasks:**
1. Create `~/.ai-agent-tools/` structure
2. Migrate all skills to universal location
3. Create symlinks for all agent types
4. Document agent-agnostic configuration patterns
5. Test with multiple AI agents (Claude, Aider, Continue, etc.)

**Time:** 1-2 hours
**Risk:** Low (symlinks maintain compatibility)

---

## 🎯 Expected Benefits

### Immediate (Phase 1-2)

1. **Single Source of Truth**
   - All skills in one location
   - No confusion about which directory to use
   - Easier skill management

2. **Reduced Maintenance**
   - Update skills once, available everywhere
   - No duplicate skill versions
   - Clearer ownership

3. **Better Discovery**
   - All agents see all skills
   - Consistent skill availability
   - No hidden capabilities

### Medium-Term (Phase 3)

4. **Security Posture**
   - Proactive vulnerability detection
   - MCP server security validation
   - Secrets and token leak prevention
   - Web UI security auditing

5. **Compliance**
   - Security audit trail
   - Vulnerability remediation tracking
   - Best practices enforcement

### Long-Term (Phase 4)

6. **True Agent-Agnosticity**
   - Works with any AI agent/model
   - Local and remote agents supported
   - Vendor-agnostic tooling
   - Future-proof architecture

7. **Ecosystem Integration**
   - Standard MCP server discovery
   - Cross-agent skill sharing
   - Community skill compatibility
   - Standardized configurations

---

## 📝 Configuration Templates

### Universal Skills Configuration

**File:** `~/.ai-agent-tools/config.json`
```json
{
  "version": "1.0",
  "skillDirectories": [
    "~/.ai-agent-tools/skills",
    "~/.claude/skills",
    "./.claude/skills",
    "./.agent/skills"
  ],
  "mcpConfigFile": "~/.mcp/config.json",
  "agentConfigs": {
    "claude": "~/.config/claude/",
    "cursor": "~/.cursor/",
    "aider": "~/.aider/",
    "continue": "~/.continue/"
  }
}
```

### MCP Server Registry

**File:** `~/.mcp/registry.json`
```json
{
  "version": "1.0",
  "servers": {
    "nixos": {
      "installed": true,
      "version": "1.0.1",
      "source": "github:utensils/mcp-nixos",
      "category": "development",
      "security_audit": {
        "audited": true,
        "audit_date": "2025-12-04",
        "vulnerabilities": 0,
        "status": "safe"
      }
    },
    "securemcp": {
      "installed": true,
      "version": "latest",
      "source": "github:makalin/SecureMCP",
      "category": "security",
      "security_audit": {
        "audited": true,
        "audit_date": "2025-12-04",
        "vulnerabilities": 0,
        "status": "safe"
      }
    }
  }
}
```

---

## 🔄 Migration Checklist

### Pre-Migration

- [ ] Backup current configurations
- [ ] Document current skill locations
- [ ] Verify all skills functional
- [ ] Test current MCP servers

### Migration Steps

- [ ] Create `~/.mcp/` directory
- [ ] Move custom skills to `.claude/skills/`
- [ ] Verify 25 skills load in Claude Code
- [ ] Create standardized `~/.mcp/config.json`
- [ ] Symlink Claude config to standard location
- [ ] Test all MCP servers load
- [ ] Update documentation

### Post-Migration Validation

- [ ] All 25 skills accessible
- [ ] mcp-nixos functional
- [ ] Skills work in prompts
- [ ] No broken references
- [ ] Documentation updated
- [ ] AIDB synced

### Security Audit Phase

- [ ] Install SecureMCP
- [ ] Audit all MCP servers
- [ ] Fix detected vulnerabilities
- [ ] Install vulnicheck
- [ ] Scan codebase for secrets
- [ ] Install lighthouse-mcp-server
- [ ] Audit web UIs
- [ ] Document security findings

---

## 📚 Documentation Updates Needed

1. **SKILLS-AND-MCP-INVENTORY.md**
   - Update to show unified location
   - Remove .agent/skills references
   - Add security MCP servers section

2. **MCP_SERVERS.md**
   - Document standardized configuration
   - Add security server installation
   - Update discovery mechanisms

3. **AGENTS.md**
   - Add agent-agnostic guidelines
   - Document universal skill access
   - Cross-agent compatibility notes

4. **New: SECURITY-AUDIT-GUIDE.md**
   - Security MCP server usage
   - Vulnerability scanning procedures
   - Audit logging and reporting

---

## 🚀 Next Steps

### Immediate Actions

1. **Consolidate skills** (15 minutes)
   ```bash
   cd ~/Documents/NixOS-Dev-Quick-Deploy
   cp -r .agent/skills/* .claude/skills/
   # Verify: ls .claude/skills/ | wc -l  # Should show 25
   ```

2. **Standardize MCP config** (30 minutes)
   - Create `~/.mcp/config.json`
   - Migrate mcp-nixos configuration
   - Create symlink for Claude

3. **Install SecureMCP** (Next Phase)
   - Audit existing MCP servers
   - Validate security posture
   - Document findings

### Questions for User

1. **Skill consolidation:** Option A (.claude/skills) or Option B (~/.ai-agent-tools)?
2. **Security scope:** Start with SecureMCP only, or install full security stack?
3. **Timing:** Consolidate now, or wait until after NixOS improvements deployment?

---

**Version:** 1.0.0
**Status:** Ready for Implementation
**Last Updated:** December 4, 2025 01:20 PST
**Next Action:** User approval to proceed with Phase 1
