# AI Agent Setup Guide

Complete guide for setting up AI agents, downloading GGUF models, and leveraging the NixOS-Dev-Quick-Deploy AI knowledge base.

> **📊 System Dashboard**: Monitor all services and check deployment status at [ai-stack/dashboard/index.html](ai-stack/dashboard/index.html)

## Quick Start

### 1. Download Lemonade GGUF Models

```bash
# Interactive mode (recommended for first-time setup)
./scripts/download-lemonade-models.sh

# Automated download of all recommended models
./scripts/download-lemonade-models.sh --all

# List downloaded models
./scripts/download-lemonade-models.sh --list
```

### 2. Start Podman AI Stack

```bash
# Navigate to AI stack directory
cd ai-stack/compose/

# Start all services (Lemonade, Ollama, Qdrant, Open WebUI, AIDB MCP)
podman-compose up -d

# Or using Docker
docker-compose up -d

# Monitor startup
podman logs -f lemonade
podman logs -f lemonade-coder
podman logs -f lemonade-deepseek
```

### 3. Verify Services

```bash
# Check Lemonade services
curl http://localhost:8000/health  # General purpose
curl http://localhost:8001/health  # Code generation
curl http://localhost:8003/health  # Code analysis

# Check Qdrant vector database
curl http://localhost:6333/health

# Check Open WebUI
open http://localhost:3000

# Check AIDB MCP Server
curl http://localhost:8091/health
```

## Recommended GGUF Models

The NixOS-Dev-Quick-Deploy stack uses three specialized GGUF models:

### 1. Qwen3-4B-Instruct-2507 (General Purpose)
- **Size**: 2.4 GB
- **Port**: 8000
- **Purpose**: General reasoning and task execution
- **Repository**: `unsloth/Qwen3-4B-Instruct-2507-GGUF`
- **File**: `Qwen3-4B-Instruct-2507-Q4_K_M.gguf`

### 2. Qwen2.5-Coder-7B-Instruct (Code Generation)
- **Size**: 4.3 GB
- **Port**: 8001
- **Purpose**: Advanced code generation and completion
- **Repository**: `Qwen/Qwen2.5-Coder-7B-Instruct-GGUF`
- **File**: `qwen2.5-coder-7b-instruct-q4_k_m.gguf`

### 3. Deepseek-Coder-6.7B-Instruct (Code Analysis)
- **Size**: 3.8 GB
- **Port**: 8003
- **Purpose**: Code analysis and understanding
- **Repository**: `TheBloke/deepseek-coder-6.7B-instruct-GGUF`
- **File**: `deepseek-coder-6.7b-instruct.Q4_K_M.gguf`

**Total Download Size**: ~10.5 GB

## Model Storage Locations

Models are cached to avoid re-downloading:

```
~/.local/share/nixos-ai-stack/lemonade-models/  # User-level storage
~/.cache/huggingface/                           # HuggingFace cache
```

Docker/Podman mounts:
- Container path: `/root/.cache/huggingface`
- Volume name: `lemonade-hf-cache`

## AI Knowledge Base

The AI knowledge base provides structured information for agents:

```
ai-knowledge-base/
├── mcp-servers/
│   ├── nixos-development.json      # NixOS/Nix MCP servers
│   ├── ai-llm-development.json     # AI/LLM MCP servers
│   ├── vm-qemu-development.json    # VM/QEMU MCP servers
│   └── coding-agents.json          # Coding agent MCP servers
├── reference/
│   ├── lemonade-api.md            # Lemonade API reference
│   └── ... (other API docs)
└── README.md
```

## MCP Server Catalogs

### Critical MCP Servers for NixOS Development

1. **filesystem** (builtin) - File operations for Nix configs
2. **git** (builtin) - Version control for configurations
3. **shell-command** (builtin) - Execute nix-* commands
4. **github-mcp-server** (external) - Browse nixpkgs repository

### Critical MCP Servers for AI/LLM Development

1. **aidb** (custom) - Integrated Qdrant + Lemonade + Ollama
2. **composio** - 100+ agent tool integrations
3. **goose** - Extensible AI agent with MCP support
4. **activepieces** - Access to ~400 MCP servers

### Critical MCP Servers for Coding Agents

1. **serena** - Semantic code search and editing
2. **github-mcp-server** - Repository operations
3. **repomix** - Repository context generation
4. **context7** - Live code documentation

### Critical MCP Servers for VM/QEMU Development

1. **shell-command** (builtin) - Execute virsh/qemu commands
2. **filesystem** (builtin) - Manage VM configs and images
3. **vm-automation** (proposed) - Automated VM provisioning

## Integration Points

### Lemonade AI Server

OpenAI-compatible API for local LLM inference:

```python
import httpx

async with httpx.AsyncClient(base_url="http://localhost:8000/api/v1") as client:
    response = await client.post("/chat/completions", json={
        "messages": [{"role": "user", "content": "Explain NixOS modules"}],
        "temperature": 0.7,
        "max_tokens": 500
    })
    print(response.json())
```

### AIDB MCP Server

Unified interface to Qdrant, Lemonade, and Ollama:

```python
from mcp import ClientSession

async with ClientSession() as session:
    # Vector search in codebase
    results = await session.call_tool("qdrant_search", {
        "query": "NixOS module configuration",
        "collection": "codebase"
    })

    # LLM inference with routing
    response = await session.call_tool("llm_inference", {
        "prompt": "Generate a NixOS module for Nginx",
        "task_type": "CODE_GENERATION"  # Routes to lemonade-coder
    })
```

### Qdrant Vector Database

Store and search embeddings:

```bash
# Create collection
curl -X PUT http://localhost:6333/collections/nixos-docs \
  -H "Content-Type: application/json" \
  -d '{
    "vectors": {
      "size": 384,
      "distance": "Cosine"
    }
  }'

# Insert embeddings
curl -X PUT http://localhost:6333/collections/nixos-docs/points \
  -H "Content-Type: application/json" \
  -d '{
    "points": [
      {
        "id": 1,
        "vector": [...],
        "payload": {"doc": "NixOS module for Nginx"}
      }
    ]
  }'

# Search
curl -X POST http://localhost:6333/collections/nixos-docs/points/search \
  -H "Content-Type: application/json" \
  -d '{
    "vector": [...],
    "limit": 5
  }'
```

## Agentic Workflows

### NixOS Configuration Agent

```python
# Workflow: Generate and test NixOS configuration
async def nixos_config_agent(requirement: str):
    # 1. Search existing configurations
    similar = await qdrant_search(requirement)

    # 2. Generate new config using code model
    config = await lemonade_coder.generate(
        f"Create NixOS module for: {requirement}\nSimilar configs: {similar}"
    )

    # 3. Write to file
    await filesystem.write("/tmp/test-module.nix", config)

    # 4. Test in VM
    await shell.execute("vm-create-nixos test-config 4096 2 20")
    await shell.execute("virsh start test-config")

    # 5. Validate
    result = await shell.execute("nixos-rebuild dry-build")

    return {"config": config, "validation": result}
```

### Code Review Agent

```python
# Workflow: Semantic code review
async def code_review_agent(repo_url: str, pr_number: int):
    # 1. Fetch PR changes
    changes = await github.get_pr_diff(repo_url, pr_number)

    # 2. Semantic analysis
    issues = await serena.analyze(changes)

    # 3. LLM-powered review
    review = await lemonade_coder.review(
        changes, context=issues
    )

    # 4. Post review
    await github.create_review(repo_url, pr_number, review)

    return review
```

### VM Provisioning Agent

```python
# Workflow: Automated VM testing
async def vm_testing_agent(nixos_config: str):
    # 1. Create test VM
    vm_name = f"test-{timestamp()}"
    await shell.execute(f"vm-create-nixos {vm_name} 4096 2 20")

    # 2. Copy config
    await filesystem.write(
        f"/tmp/{vm_name}-config.nix", nixos_config
    )

    # 3. Start and configure
    await shell.execute(f"virsh start {vm_name}")
    await shell.execute(
        f"virt-copy-in -d {vm_name} /tmp/{vm_name}-config.nix /etc/nixos/"
    )

    # 4. Rebuild and test
    result = await shell.execute(
        f"virsh console {vm_name} -- nixos-rebuild test"
    )

    # 5. Snapshot if successful
    if result.success:
        await shell.execute(f"vm-snapshot {vm_name} working-config")

    return result
```

## Automated Deployment

### During Initial Install

When running `nixos-quick-deploy.sh`, Phase 9 will:

1. Detect GPU capabilities
2. Recommend suitable models
3. Offer to pre-download GGUF models
4. Configure Lemonade services
5. Start AI stack containers

### Manual Installation

```bash
# 1. Download models
./scripts/download-lemonade-models.sh --all

# 2. Start AI stack
cd ai-stack/compose/
podman-compose up -d

# 3. Wait for models to load
while ! curl -sf http://localhost:8000/health > /dev/null; do
    echo "Waiting for Lemonade..."
    sleep 10
done

echo "Lemonade AI Stack Ready!"
```

## Performance Tuning

### CPU-Only Optimization

```bash
# Use all available cores
export LEMONADE_ARGS="--threads $(nproc) --mlock"

# Enable NUMA for multi-socket systems
export LEMONADE_ARGS="--threads $(nproc) --numa"
```

### Memory Optimization

```bash
# Reduce context window for less RAM usage
export LEMONADE_CTX_SIZE=2048

# Smaller batch size
export LEMONADE_ARGS="--batch-size 256"
```

### GPU Acceleration (if available)

```bash
# Offload all layers to GPU
export LEMONADE_ARGS="--n-gpu-layers 99"
```

## Monitoring and Debugging

### Health Checks

```bash
# Quick health check script
#!/usr/bin/env bash
services=(
    "lemonade:8000"
    "lemonade-coder:8001"
    "lemonade-deepseek:8003"
    "qdrant:6333"
    "ollama:11434"
    "open-webui:3000"
)

for service in "${services[@]}"; do
    name="${service%%:*}"
    port="${service##*:}"
    if curl -sf "http://localhost:$port/health" > /dev/null 2>&1; then
        echo "✓ $name is healthy"
    else
        echo "✗ $name is not responding"
    fi
done
```

### View Logs

```bash
# Lemonade services
podman logs -f lemonade
podman logs -f lemonade-coder
podman logs -f lemonade-deepseek

# AIDB MCP Server
podman logs -f aidb-mcp

# Qdrant vector database
podman logs -f qdrant
```

### Prometheus Metrics

```bash
# Lemonade metrics
curl http://localhost:9100/metrics  # lemonade
curl http://localhost:9101/metrics  # lemonade-coder
curl http://localhost:9102/metrics  # lemonade-deepseek

# Qdrant metrics
curl http://localhost:6333/metrics
```

## Troubleshooting

### Models Not Loading

```bash
# Check if models downloaded
ls -lh ~/.cache/huggingface/hub/

# Manually trigger download
podman exec lemonade python3 -c "from huggingface_hub import hf_hub_download; hf_hub_download(repo_id='unsloth/Qwen3-4B-Instruct-2507-GGUF', filename='Qwen3-4B-Instruct-2507-Q4_K_M.gguf')"
```

### Out of Memory

```bash
# Check memory usage
free -h

# Reduce context size
export LEMONADE_CTX_SIZE=2048

# Stop unused services
podman stop ollama  # If only using Lemonade
```

### Slow Inference

```bash
# Check CPU usage
htop

# Increase threads
export LEMONADE_ARGS="--threads $(nproc)"

# Enable memory locking
export LEMONADE_ARGS="--mlock"
```

## References

- **Model Download Script**: `scripts/download-lemonade-models.sh`
- **AI Knowledge Base**: `ai-knowledge-base/README.md`
- **Lemonade API Reference**: `ai-knowledge-base/reference/lemonade-api.md`
- **Docker Compose Config**: `ai-stack/compose/docker-compose.yml`
- **AIDB MCP Server**: `ai-stack/mcp-servers/aidb/`
- **Phase 9 Deployment**: `phases/phase-09-ai-model-deployment.sh`

## Next Steps

1. **Download Models**: Run `./scripts/download-lemonade-models.sh --all`
2. **Start Services**: `cd ai-stack/compose/ && podman-compose up -d`
3. **Explore MCP Servers**: Review `ai-knowledge-base/mcp-servers/`
4. **Test Integration**: Try example workflows above
5. **Build Custom Agents**: Use MCP servers and Lemonade API

## Contributing

To add new MCP servers or workflows:

1. Add server details to appropriate JSON in `ai-knowledge-base/mcp-servers/`
2. Document API in `ai-knowledge-base/reference/`
3. Create workflow example in `ai-knowledge-base/workflows/`
4. Update this guide with new use cases

---

**Last Updated**: 2025-12-19
**Version**: 1.0.0
**Maintainer**: NixOS-Dev-Quick-Deploy Team
