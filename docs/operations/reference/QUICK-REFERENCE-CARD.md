# AI Agent Quick Reference Card

Status: Active
Owner: AI Stack Maintainers
Last Updated: 2026-03-05

**Version:** 2.0.0
**Date:** December 4, 2025
**Purpose:** Instant access to all tools and resources

---

## 🎯 Critical Locations

```
Project: ~/Documents/NixOS-Dev-Quick-Deploy
Skills: .agent/skills/ (25 skills - SOURCE OF TRUTH)
MCP Config: ~/.mcp/config.json
AIDB: http://localhost:8091
```

---

## ⚡ 30-Second Commands

### Query Anything
```bash
curl 'http://localhost:8091/documents?search=QUERY&project=NixOS-Dev-Quick-Deploy'
```

### List All Skills
```bash
ls .agent/skills/
```

### Check MCP Servers
```bash
cat ~/.mcp/config.json | jq '.mcpServers'
```

### Run Health Check
```bash
./scripts/automation/run-all-checks.sh        # Full validation (health + services + workflows)
./scripts/health/system-health-check.sh   # Core system health check only
./scripts/ai/ai-env-summary.sh        # AI_PROFILE, AI_STACK_PROFILE, AIDB project, registry
```

### Switch AI Environment (per host)
```bash
export AI_PROFILE=cpu_slim           # or cpu_full, off
export AI_STACK_PROFILE=guest        # or personal, none
export AIDB_PROJECT_NAME="NixOS-Dev-Quick-Deploy-Guest"
```

---

## 📦 Available Resources

### 707 MCP Servers
- **File:** `docs/mcp-servers-directory.json`
- **Top Server:** n8n (⭐160,595)
- **Security Tools:** 193 catalogued
- **Red Team Focus:** atomic-red-team (⭐11,354) #1 recommendation

### 25 Skills (All in .agent/skills/)
**Development:** ai-model-management, ai-service-management, nixos-deployment, webapp-testing, mcp-builder, skill-creator

**Data:** aidb-knowledge, xlsx, pdf, pptx

**Design:** frontend-design, canvas-design, brand-guidelines, theme-factory, web-artifacts-builder

**Utilities:** health-monitoring, all-mcp-directory, mcp-server, project-import, rag-techniques, system_bootstrap

**Communication:** internal-comms, slack-gif-creator

**Templates:** template-skill, mcp-database-setup

---

## 🛡️ Top Security Tools

1. **atomic-red-team** (⭐11,354) - MITRE ATT&CK tests
2. **AI-Infra-Guard** (⭐2,484) - AI red team
3. **CISO Assistant** (⭐3,391) - GRC/Compliance
4. **mcp-scan** (⭐1,308) - MCP security scanner
5. **beelzebub** (⭐1,708) - AI honeypot

**Full List:** `docs/RED-TEAM-MCP-SERVERS.md`

---

## 📖 Essential Docs

| Doc | Purpose |
|-----|---------|
| AGENTS.md | Complete onboarding (start here!) |
| docs/AGENT-ONBOARDING-README.md | 30-min quick start |
| docs/mcp-servers-directory.json | All 707 MCP servers |
| docs/RED-TEAM-MCP-SERVERS.md | 193 security tools |
| docs/AGENT-AGNOSTIC-TOOLING-PLAN.md | Architecture |

---

## 🚀 Common Tasks

### Research
```bash
# Find anything in AIDB
curl 'http://localhost:8091/documents?search=deployment'

# Search codebase
grep -r "pattern" .

# Find files
find . -name "*.sh"
```

### Use Skills
```
"use the webapp-testing skill to test http://localhost:3001"
"use the aidb-knowledge skill to search for MCP servers"
"use the xlsx skill to create a deployment report"
```

### Git Operations
```bash
git status
git checkout -b feature/description
git add . && git commit -m "message"
```

---

## 🔧 System Info

### Current Setup
- **OS:** NixOS 25.11 (Xantusia)
- **Skills:** 25 unified (.agent/skills/)
- **MCP Servers:** 707 discovered, 1 installed (mcp-nixos)
- **AIDB:** Running at http://localhost:8091
- **Security Tools:** 193 catalogued

### Installation Status
- ✅ Skills consolidated
- ✅ MCP directory populated (707 servers)
- ✅ AIDB synchronized
- ✅ Onboarding package created
- ✅ atomic-red-team added (#1 red team tool)
- ⏳ Security tools (pending installation)

---

## 💡 Pro Tips

**Speed up onboarding:**
- AIDB queries are instant (<100ms)
- Skills are pre-loaded
- All docs are local

**Reduce token consumption:**
- Query AIDB instead of reading files
- Use grep for targeted searches
- Reference skills by name

**Work efficiently:**
- Keep AGENTS.md open
- Use bash history (↑ arrow)
- Update AIDB with findings

---

## 📞 Getting Help

1. **Query AIDB first:** `curl 'http://localhost:8091/documents?search=TOPIC'`
2. **Check docs:** `ls docs/*.md`
3. **Review sessions:** `ls -lt docs/SESSION-*.md | head -5`
4. **Git history:** `git log --grep="KEYWORD"`

---

## ✅ Onboarding Checklist

- [ ] Read AGENTS.md (first 200 lines)
- [ ] Verify: `ls .agent/skills/` shows 25 skills
- [ ] Test: `curl http://localhost:8091/documents?search=test`
- [ ] Run: `./scripts/health/system-health-check.sh`
- [ ] Ready!

**Time to productivity: ~30 minutes**

---

**Query this card:** `curl 'http://localhost:8091/documents?search=quick reference'`

**Last Updated:** December 4, 2025
**Version:** 2.0.0
