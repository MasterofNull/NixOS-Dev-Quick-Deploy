# Quick Start: Vibe Coding System
**Get started in 5 minutes**

## Current Status

✅ **Core Services Running**:
- llama.cpp (8080) - CPU-optimized local LLM
- Qdrant (6333-6334) - Vector database with 6 collections
- PostgreSQL (5432) - Relational database
- Redis (6379) - Cache
- MindsDB (47334-47335) - AI SQL

⚙️ **MCP Servers Building** (check status below)

---

## Check System Status

```bash
# Check all running containers
podman ps --format "table {{.Names}}\t{{.Status}}\t{{.Ports}}"

# Check MCP server deployment progress
tail -f /tmp/mcp-deploy.log

# Test llama.cpp
curl -s http://localhost:8080/health

# Test Qdrant
curl -k -s https://localhost:8443/qdrant/collections | jq '.result.collections[].name'
```

**TLS Note:** AIDB/Hybrid/Qdrant are exposed via nginx at `https://localhost:8443`. Use `-k` for the self-signed cert.
**Auth Note:** If API keys are enabled, add `-H "X-API-Key: $(cat ai-stack/compose/secrets/stack_api_key)"`.

---

## Once MCP Servers Are Ready

### 1. Verify Health
```bash
# AIDB MCP Server
curl -k https://localhost:8443/aidb/health

# Hybrid Coordinator
curl -k https://localhost:8443/hybrid/health

# Ralph Wiggum Loop
curl http://localhost:8098/health
```

### 2. Discover Available Tools
```bash
# Let the system discover all capabilities
curl -k -X POST https://localhost:8443/aidb/api/v1/tools/discover

# Search for tools semantically
curl -k -X POST https://localhost:8443/aidb/api/v1/tools/search \
  -H "Content-Type: application/json" \
  -d '{"query": "search documents", "limit": 5}'
```

### 3. Submit Your First Autonomous Task
```bash
# Submit a simple coding task to Ralph
curl -X POST http://localhost:8098/tasks \
  -H "Content-Type: application/json" \
  -d '{
    "prompt": "Create a Python function that calculates fibonacci numbers",
    "backend": "aider",
    "max_iterations": 10,
    "require_approval": false
  }'

# Save the task_id from response
TASK_ID="<your-task-id>"

# Monitor progress
watch -n 5 "curl -s http://localhost:8098/tasks/$TASK_ID | jq"

# View live logs
podman logs -f local-ai-ralph-wiggum

# Check telemetry
tail -f ~/.local/share/nixos-ai-stack/telemetry/ralph-events.jsonl
```

---

## Test Self-Healing

```bash
# Kill a container
podman stop local-ai-redis

# Wait 30 seconds and check if it restarted
sleep 30
podman ps | grep redis

# View healing history
curl -k https://localhost:8443/aidb/api/v1/healing/statistics
```

---

## View Learning Progress

```bash
# Check how many patterns have been learned
curl -k https://localhost:8443/hybrid/api/v1/learning/statistics

# View the fine-tuning dataset
ls -lh ~/.local/share/nixos-ai-stack/fine-tuning/dataset.jsonl

# Count examples
wc -l ~/.local/share/nixos-ai-stack/fine-tuning/dataset.jsonl
```

---

## Use the Local LLM Directly

```bash
# Code completion
curl -X POST http://localhost:8080/v1/completions \
  -H "Content-Type: application/json" \
  -d '{
    "prompt": "def bubble_sort(arr):",
    "max_tokens": 200,
    "temperature": 0.7
  }' | jq '.choices[0].text'

# Chat completion
curl -X POST http://localhost:8080/v1/chat/completions \
  -H "Content-Type: application/json" \
  -d '{
    "messages": [
      {"role": "system", "content": "You are a helpful coding assistant."},
      {"role": "user", "content": "How do I fix a memory leak in Python?"}
    ],
    "max_tokens": 500
  }' | jq '.choices[0].message.content'

# Generate embeddings
curl -X POST http://localhost:8080/embeddings \
  -H "Content-Type: application/json" \
  -d '{"input": "search documents in database"}' | jq '.embedding | length'
```

---

## Troubleshooting

### MCP Servers Not Starting

```bash
# Check build logs
tail -100 /tmp/mcp-deploy.log

# Check container status
podman ps -a | grep -E "aidb|hybrid|ralph"

# View container logs
podman logs local-ai-aidb
podman logs local-ai-hybrid-coordinator
podman logs local-ai-ralph-wiggum

# Rebuild if needed
cd ~/Documents/try/NixOS-Dev-Quick-Deploy/ai-stack/compose
podman-compose up -d --build aidb hybrid-coordinator ralph-wiggum
```

### Container Unhealthy

```bash
# Let self-healing handle it (wait 30-60 seconds)
# Or manual restart:
podman restart <container-name>
```

### Port Conflicts

```bash
# Check what's using ports
ss -tulpn | grep -E "8091|8092|8098"

# Stop conflicting service or change ports in .env
```

---

## Key Features

### 🔄 Ralph Wiggum Loop
- **Persistent development**: Never gives up on tasks
- **Exit code blocking**: Prevents premature agent exits
- **Git-based recovery**: Can resume after crashes
- **Multi-backend**: Aider, Continue, Goose, AutoGPT, LangChain

### 🔍 Tool Discovery
- **Automatic**: Finds all MCP server capabilities
- **Semantic search**: Find tools by description
- **Real-time updates**: New tools discovered every 5 minutes

### 🏥 Self-Healing
- **6 error patterns**: Port conflicts, OOM, connection issues, etc.
- **Auto-restart**: Failed containers restart automatically
- **Dependency awareness**: Restarts dependencies first
- **Learning**: Successful fixes saved to knowledge base

### 📚 Continuous Learning
- **Pattern extraction**: Learns from successful interactions
- **Quality filtering**: Only high-quality examples
- **Fine-tuning datasets**: OpenAI-compatible JSONL
- **1000+ examples**: Triggers automatic fine-tuning

---

## Performance Optimizations Active

- ✅ **Flash Attention**: 2-4x faster inference
- ✅ **KV Cache Quantization**: 60% less RAM
- ✅ **8K Context**: 2x larger than default
- ✅ **Continuous Batching**: Efficient multi-request handling
- ✅ **4 Parallel Slots**: Handle 4 requests simultaneously
- ✅ **NUMA Distribution**: Optimized for multi-core CPUs

---

## Documentation

- **Architecture**: `docs/VIBE-CODING-SYSTEM-ARCHITECTURE.md`
- **Implementation Summary**: `docs/VIBE-CODING-IMPLEMENTATION-SUMMARY.md`
- **AI Stack Guide**: `docs/AI-STACK-V3-AGENTIC-ERA-GUIDE.md`
- **Ralph Wiggum**: `ai-stack/mcp-servers/ralph-wiggum/README.md`

---

## What's Next?

1. **Test everything** - Run through the testing plan above
2. **Submit real tasks** - Try actual coding projects
3. **Monitor learning** - Watch the dataset grow
4. **Fine-tune model** - When you have 1000+ examples
5. **Scale up** - Deploy to production with security enabled

---

**Need Help?**

- Check logs: `podman logs <container-name>`
- View telemetry: `~/.local/share/nixos-ai-stack/telemetry/*.jsonl`
- System status: `podman ps`
- Health checks: `curl http://localhost:<port>/health`

---

*Vibe Coding System v3.0.0 - Built with Claude Sonnet 4.5*
