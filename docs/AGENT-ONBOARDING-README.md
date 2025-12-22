# AI Agent Onboarding Package
**Version:** 2.0.0  
**Date:** December 4, 2025  
**Purpose:** Ultra-fast onboarding for fresh AI agents

---

## 🚀 INSTANT ACCESS - Read This First!

**You are joining the NixOS-Dev-Quick-Deploy project.**

### 📍 Critical Locations (Memorize These)

```
Project Root: /home/hyperd/Documents/NixOS-Dev-Quick-Deploy

Skills (Source of Truth): .agent/skills/ (25 skills)
MCP Config: ~/.mcp/config.json
AIDB: http://localhost:8091
Main Onboarding: AGENTS.md (comprehensive guide)
Mirror Guide: docs/AGENTS.md (quick reference)
System Map: docs/agent-guides/00-SYSTEM-OVERVIEW.md
Quick Start: docs/agent-guides/01-QUICK-START.md
```

### ⚡ 30-Second Quickstart

**1. Read the agent guide:**
```bash
cat AGENTS.md | head -200  # First 200 lines = quick start
```

**2. Query AIDB for anything:**
```bash
curl 'http://localhost:8091/documents?search=TOPIC&project=NixOS-Dev-Quick-Deploy'
```

**3. Check available skills:**
```bash
ls .agent/skills/  # All 25 skills listed
```

**4. See installed MCP servers:**
```bash
cat ~/.mcp/config.json  # Current: mcp-nixos
```

---

## ✅ Onboarding Checklist

- [ ] Read this README  
- [ ] Read AGENTS.md quick start (first 200 lines)  
- [ ] Verify skills directory: `ls .agent/skills/`  
- [ ] Test AIDB: `curl http://localhost:8091/documents?search=test`  
- [ ] Run health check: `./scripts/system-health-check.sh`  
- [ ] Ready to contribute!

**Time to First Productive Work: ~30 minutes**

See full details in AGENTS.md
