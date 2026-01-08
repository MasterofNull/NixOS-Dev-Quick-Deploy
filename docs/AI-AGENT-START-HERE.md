# AI Agent Helper System - START HERE
**Version**: 2.1.0 | **Date**: 2025-12-22 | **Status**: ✅ FULLY OPERATIONAL

---

## 🎯 Single Entry Point for All AI Agents

This is the **ONLY document you need to read first**. Everything else is linked below in priority order.

---

## ⚡ Quickest Start (2 minutes)

**TLS Note:** HTTPS is terminated by nginx on `https://localhost:8443` with a self-signed cert. Prefer `--cacert ai-stack/compose/nginx/certs/localhost.crt` (use `-k` only for troubleshooting).
**Auth Note:** If API keys are enabled, add `-H "X-API-Key: $(cat ai-stack/compose/secrets/stack_api_key)"`.

### For AI Agents (Remote Models: Claude, GPT-4, etc.)

```bash
# Step 1: Check system is running (20 tokens)
curl --cacert ai-stack/compose/nginx/certs/localhost.crt https://localhost:8443/aidb/health \
  -H "X-API-Key: $(cat ai-stack/compose/secrets/stack_api_key)"

# Step 2: Discover what's available (50 tokens)
curl --cacert ai-stack/compose/nginx/certs/localhost.crt https://localhost:8443/aidb/discovery/info \
  -H "X-API-Key: $(cat ai-stack/compose/secrets/stack_api_key)"

# Step 3: Get your quickstart workflow (150 tokens)
curl --cacert ai-stack/compose/nginx/certs/localhost.crt https://localhost:8443/aidb/discovery/quickstart \
  -H "X-API-Key: $(cat ai-stack/compose/secrets/stack_api_key)"

# Total: 220 tokens vs 3000+ without progressive disclosure
```

### For Local Models (Ollama, llama.cpp, etc.)

```bash
# Smart routing - automatically uses local LLM when possible (FREE!)
curl --cacert ai-stack/compose/nginx/certs/localhost.crt -X POST https://localhost:8443/hybrid/query \
  -H "Content-Type: application/json" \
  -H "X-API-Key: $(cat ai-stack/compose/secrets/stack_api_key)" \
  -d '{"query": "How do I configure NixOS?", "context": {}}'
```

---

## 📖 Progressive Documentation (Read in Order)

### Priority 1: Essential (Read First - 15 minutes)

1. **[Quick Start Guide](/docs/00-QUICK-START.md)** (5 min)
   - Get up and running immediately
   - Essential commands
   - Health checks

2. **[System Overview](/docs/01-SYSTEM-OVERVIEW.md)** (10 min)
   - What this system does
   - Architecture overview
   - Key capabilities

### Priority 2: Integration (Next - 20 minutes)

3. **[Agent Integration](/docs/02-AGENT-INTEGRATION.md)** (20 min)
   - 4 integration patterns (Claude Code, Python, Ollama, LangChain)
   - Complete code examples
   - Your agent can be using the system after this

### Priority 3: Advanced Usage (When Ready - 30 minutes)

4. **[Progressive Disclosure Guide](/docs/archive/03-PROGRESSIVE-DISCLOSURE.md)** (15 min)
   - How to minimize token usage (87% reduction)
   - 4 disclosure levels explained
   - Best practices

5. **[Continuous Learning](/docs/04-CONTINUOUS-LEARNING.md)** (15 min)
   - How the system learns from interactions
   - Value scoring (5-factor algorithm)
   - Hybrid routing (local vs remote)

### Priority 4: Reference (As Needed)

6. **[Complete API Reference](/docs/05-API-REFERENCE.md)**
   - All endpoints documented
   - Request/response examples

7. **[Troubleshooting Guide](/docs/06-TROUBLESHOOTING.md)**
   - Common issues and solutions

8. **[Documentation Index](/docs/07-DOCUMENTATION-INDEX.md)**
   - Navigate all 36+ documentation files

---

## 🔧 System Services

| Service | URL | Purpose | Status Check |
|---------|-----|---------|--------------|
| **AIDB MCP** | https://localhost:8443/aidb | Main API, skills, tools | `curl --cacert ai-stack/compose/nginx/certs/localhost.crt https://localhost:8443/aidb/health` |
| **Hybrid Coordinator** | https://localhost:8443/hybrid | Smart routing | `curl --cacert ai-stack/compose/nginx/certs/localhost.crt https://localhost:8443/hybrid/health` |
| **Qdrant** | https://localhost:8443/qdrant | Vector database | `curl --cacert ai-stack/compose/nginx/certs/localhost.crt https://localhost:8443/qdrant/healthz` |
| **llama.cpp** | http://localhost:8080 | Local LLM | `curl http://localhost:8080/health` |

---

## 💡 Key Concepts

### Progressive Disclosure
Start with minimal information (50 tokens), expand only when needed (vs 3000+ tokens upfront).

### Continuous Learning
System learns from every interaction. High-value solutions (score ≥ 0.7) are automatically extracted for future use.

### Hybrid Routing
Queries automatically routed to local LLM (free, fast) or remote API (quality) based on relevance and complexity.

### Token Savings
- Discovery: 87% reduction (220 tokens vs 3000+)
- Ongoing: 70% queries → local LLM (free)
- Monthly: $65-500 saved per 1000 queries

---

## 🎓 Learning Path

```
You Are Here
    ↓
[Read This Document] (5 min)
    ↓
[Read Quick Start] (5 min)
    ↓
[Read System Overview] (10 min)
    ↓
[Try API Calls] (5 min)
    ↓
[Read Agent Integration] (20 min)
    ↓
[Integrate Your Agent] (10 min)
    ↓
Start Using! Monitor effectiveness metrics.
```

**Total Time to Productive**: 55 minutes

---

## 📊 Dashboard

View system status, metrics, and effectiveness:

```bash
# Start dashboard server (runs on http://localhost:8000)
bash scripts/serve-dashboard.sh
```

Then open: **http://localhost:8000**

---

## 🆘 Need Help?

1. **Quick health check**: `curl --cacert ai-stack/compose/nginx/certs/localhost.crt https://localhost:8443/aidb/health`
2. **Service not running?**: `cd ai-stack/compose && podman-compose up -d`
3. **Read troubleshooting**: [docs/06-TROUBLESHOOTING.md](/docs/06-TROUBLESHOOTING.md)
4. **Check logs**: `podman logs local-ai-aidb`

---

## 📁 What's in This System?

- **29 Agent Skills**: Pre-built workflows (code review, testing, deployment, etc.)
- **5 Vector Collections**: Searchable knowledge (codebase, errors, patterns, best practices)
- **2 MCP Servers**: AIDB (main) + Hybrid Coordinator (routing)
- **Local LLM**: Qwen 2.5 Coder 7B (free inference)
- **6 Capability Categories**: Knowledge, Inference, Storage, Learning, Integration, Monitoring

---

## ✅ Success Criteria

After integration, you should see:
- **Effectiveness Score**: 80+ (out of 100)
- **Local Query %**: 70%+
- **Token Savings**: Growing over time
- **Knowledge Base**: 10,000+ vectors

Check metrics:
```bash
bash scripts/collect-ai-metrics.sh
cat ~/.local/share/nixos-system-dashboard/ai_metrics.json | jq .effectiveness
```

---

## 🚀 Next Steps

1. **Read Quick Start**: [docs/00-QUICK-START.md](/docs/00-QUICK-START.md)
2. **Read System Overview**: [docs/01-SYSTEM-OVERVIEW.md](/docs/01-SYSTEM-OVERVIEW.md)
3. **Try API calls** above
4. **Read Integration Guide**: [docs/02-AGENT-INTEGRATION.md](/docs/02-AGENT-INTEGRATION.md)
5. **Start using!**

---

**You're ready to start!** → [docs/00-QUICK-START.md](/docs/00-QUICK-START.md)
