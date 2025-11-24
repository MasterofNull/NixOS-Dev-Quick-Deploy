# Podman AI Stack - Complete Overview

**Version**: 4.0.0
**Type**: User-level rootless containerized AI development environment
**Management**: Declarative via home-manager + systemd quadlets

---

## Stack Components

The Podman AI Stack consists of **4 containerized services** running in an isolated network:

### 1. Ollama - AI Inference Runtime 🤖
- **Image**: `docker.io/ollama/ollama:latest`
- **Purpose**: Local LLM inference (models like Llama, Mistral, etc.)
- **Port**: 11434
- **Network Alias**: `ollama`
- **Storage**: `~/.local/share/podman-ai-stack/ollama` → `/root/.ollama`
- **Environment**:
  - `OLLAMA_HOST=0.0.0.0` (listen on all interfaces)
- **Auto-Update**: ✅ Enabled (registry)
- **Auto-Start**: ❌ Manual (via `podman-ai-stack` helper)

**Use Cases**:
- Run LLMs locally (Llama 3, Mistral, Phi, etc.)
- Fast inference without cloud dependencies
- Privacy-preserving AI development

---

### 2. Open WebUI - Chat Interface 💬
- **Image**: `ghcr.io/open-webui/open-webui:latest`
- **Purpose**: Web-based chat interface for Ollama models
- **Port**: 8081 (host) → 8080 (container)
- **Network Alias**: `open-webui`
- **Storage**: `~/.local/share/podman-ai-stack/open-webui` → `/app/backend/data`
- **Environment**:
  - `OLLAMA_BASE_URL=http://ollama:11434` (connects to Ollama via network)
  - `OPENAI_API_BASE=<huggingface-tgi-endpoint>/v1`
- **Auto-Update**: ✅ Enabled
- **Auto-Start**: ❌ Manual

**Features**:
- ChatGPT-like interface for local models
- Chat history persistence
- Model management UI
- RAG (Retrieval Augmented Generation) support
- Multi-model switching

**Access**: http://localhost:8081

---

### 3. Qdrant - Vector Database 🔍
- **Image**: `docker.io/qdrant/qdrant:latest`
- **Purpose**: Vector database for embeddings and semantic search
- **Ports**:
  - 6333 (HTTP API)
  - 6334 (gRPC API)
- **Network Alias**: `qdrant`
- **Storage**: `~/.local/share/podman-ai-stack/qdrant` → `/qdrant/storage`
- **Auto-Update**: ✅ Enabled
- **Auto-Start**: ❌ Manual

**Use Cases**:
- Store document embeddings for RAG pipelines
- Semantic search over knowledge bases
- Vector similarity queries
- Integration with LangChain/LlamaIndex

**APIs**:
- HTTP: http://localhost:6333
- gRPC: localhost:6334
- Dashboard: http://localhost:6333/dashboard

---

### 4. MindsDB - AI Orchestration 🧠
- **Image**: `docker.io/mindsdb/mindsdb:latest`
- **Purpose**: SQL-based AI automation and workflow orchestration
- **Ports**:
  - 47334 (API)
  - 7735 (GUI)
- **Network Alias**: `mindsdb`
- **Storage**: `~/.local/share/podman-ai-stack/mindsdb` → `/var/lib/mindsdb`
- **Auto-Update**: ✅ Enabled
- **Auto-Start**: ❌ Manual

**Features**:
- SQL interface to ML models
- Automated ML pipelines
- Integration with Ollama and other AI services
- Time-series forecasting
- Natural language to SQL

**Access**:
- GUI: http://localhost:7735
- API: http://localhost:47334

---

## Network Architecture

### Isolated Network: `local-ai`
- **Type**: Podman CNI network
- **Purpose**: Isolated network for all AI stack containers
- **DNS**: Containers can reach each other by network alias
- **Access**: Containers accessible from host via published ports

### Container Communication

```
┌─────────────────────────────────────────┐
│         Host (localhost)                │
│  ┌───────────────────────────────────┐  │
│  │  Podman Network: "local-ai"       │  │
│  │                                   │  │
│  │  ┌─────────┐    ┌──────────────┐ │  │
│  │  │ Ollama  │◄───│  Open WebUI  │ │  │
│  │  │  :11434 │    │    :8080     │ │  │
│  │  └────┬────┘    └──────┬───────┘ │  │
│  │       │                │         │  │
│  │  ┌────▼────┐    ┌──────▼──────┐  │  │
│  │  │ Qdrant  │    │  MindsDB    │  │  │
│  │  │:6333/34 │    │ :47334/7735 │  │  │
│  │  └─────────┘    └─────────────┘  │  │
│  └───────────────────────────────────┘  │
│           ▲                              │
│  Published Ports (accessible from host) │
│  • 11434 → Ollama                       │
│  • 8081 → Open WebUI                    │
│  • 6333/6334 → Qdrant                   │
│  • 47334/7735 → MindsDB                 │
└─────────────────────────────────────────┘
```

---

## Data Persistence

### Storage Root
```
~/.local/share/podman-ai-stack/
├── ollama/          # Ollama models and configs
├── open-webui/      # Chat history and settings
├── qdrant/          # Vector database storage
└── mindsdb/         # MindsDB data and models
```

### What's Stored

#### Ollama (`ollama/`)
- Downloaded LLM models (can be several GB each)
- Model configurations
- Model cache

#### Open WebUI (`open-webui/`)
- Chat conversations
- User settings
- Uploaded documents
- Custom prompts

#### Qdrant (`qdrant/`)
- Vector collections
- Embeddings indexes
- Collection metadata

#### MindsDB (`mindsdb/`)
- Trained models
- Database connections
- Automation workflows

---

## Management

### Systemd Services (User-Level)

Each container is managed as a systemd user service:

```bash
# Network
systemctl --user status podman-local-ai.network

# Containers
systemctl --user status podman-local-ai-ollama.service
systemctl --user status podman-local-ai-open-webui.service
systemctl --user status podman-local-ai-qdrant.service
systemctl --user status podman-local-ai-mindsdb.service
```

### Stack Helper: `podman-ai-stack`

Convenience script to manage the entire stack:

```bash
# Start all services
podman-ai-stack up

# Stop all services
podman-ai-stack down

# Check status
podman-ai-stack status

# View logs
podman-ai-stack logs [container-name]

# Restart stack
podman-ai-stack restart
```

**Location**: `~/.local/bin/podman-ai-stack`

---

## Configuration

### Enable/Disable

Controlled by the `localAiStackEnabled` flag in home.nix:

```nix
# Enable user-level AI stack (default)
localAiStackEnabled = true;

# Disable user-level AI stack
localAiStackEnabled = false;
```

### Port Configuration

Ports are defined in home.nix variables:

```nix
ollamaPort = 11434;
openWebUiPort = 8081;
qdrantHttpPort = 6333;
qdrantGrpcPort = 6334;
mindsdbApiPort = 47334;
mindsdbGuiPort = 7735;
```

### System vs User Level

The deployment automatically chooses:

| `localAiStackEnabled` | System Services | User Services |
|----------------------|-----------------|---------------|
| `true` | ❌ Disabled | ✅ Enabled |
| `false` | ✅ Enabled | ❌ Disabled |

**System Services**:
- `services.ollama` (systemd)
- `systemd.services.qdrant` (systemd)

**User Services**:
- `podman-local-ai-ollama.service` (podman quadlet)
- `podman-local-ai-qdrant.service` (podman quadlet)
- `podman-local-ai-open-webui.service` (podman quadlet)
- `podman-local-ai-mindsdb.service` (podman quadlet)

---

## Typical Workflow

### 1. Start the Stack
```bash
podman-ai-stack up
```

### 2. Pull a Model (Ollama)
```bash
curl http://localhost:11434/api/pull -d '{
  "name": "llama3:8b"
}'

# Or use the ollama CLI if installed
ollama pull llama3:8b
```

### 3. Access Open WebUI
1. Open browser to http://localhost:8081
2. Create account (local only)
3. Select model from dropdown
4. Start chatting!

### 4. Use Qdrant for RAG
```bash
# Create a collection
curl -X PUT http://localhost:6333/collections/my-docs \
  -H 'Content-Type: application/json' \
  -d '{
    "vectors": {
      "size": 384,
      "distance": "Cosine"
    }
  }'

# Upload vectors (from embeddings)
# Query for semantic search
```

### 5. MindsDB Automation
1. Open http://localhost:7735
2. Connect to data sources
3. Create ML models with SQL
4. Automate predictions

---

## Integration Examples

### LangChain with Local Stack

```python
from langchain_community.llms import Ollama
from langchain_community.vectorstores import Qdrant
from qdrant_client import QdrantClient

# Connect to local Ollama
llm = Ollama(
    base_url="http://localhost:11434",
    model="llama3:8b"
)

# Connect to local Qdrant
qdrant_client = QdrantClient(url="http://localhost:6333")
vectorstore = Qdrant(
    client=qdrant_client,
    collection_name="my-docs",
    embeddings=embeddings  # Your embedding model
)

# RAG pipeline
retriever = vectorstore.as_retriever()
# ... build chain with llm and retriever
```

### Direct API Access

```bash
# Ollama
curl http://localhost:11434/api/generate -d '{
  "model": "llama3:8b",
  "prompt": "Why is the sky blue?"
}'

# Qdrant
curl http://localhost:6333/collections

# MindsDB
curl http://localhost:47334/api/status
```

---

## Resource Requirements

### Disk Space
- **Ollama**: 5-50GB (depends on models downloaded)
- **Open WebUI**: <1GB (chat history)
- **Qdrant**: Variable (depends on vector collections)
- **MindsDB**: 1-5GB (models and data)

**Recommended**: 50GB+ free space for AI development

### Memory
- **Ollama**: 4-16GB (depends on model size)
  - 7B models: ~8GB RAM
  - 13B models: ~16GB RAM
  - 70B models: 64GB+ RAM
- **Open WebUI**: ~500MB
- **Qdrant**: 1-4GB (depends on index size)
- **MindsDB**: 2-4GB

**Recommended**: 16GB+ RAM for comfortable development

### CPU/GPU
- **CPU**: Multi-core recommended for Ollama
- **GPU**: AMD/NVIDIA GPUs significantly speed up inference
  - Ollama supports ROCm (AMD) and CUDA (NVIDIA)
  - Container configured for GPU passthrough

---

## Advantages of User-Level Stack

### 1. **Rootless** 🔒
- No root/sudo required to run
- Better security isolation
- User-owned processes

### 2. **Declarative** 📝
- Configuration in home.nix
- Reproducible across machines
- Version controlled

### 3. **Isolated** 🔐
- Separate network namespace
- No conflicts with system services
- Clean separation of concerns

### 4. **Portable** 📦
- Containers can be backed up/restored
- Data in user home directory
- Easy to migrate

### 5. **Auto-Update** 🔄
- Containers pull latest images
- `autoUpdate = "registry"` enabled
- Security patches applied automatically

---

## Comparison: System vs User Level

| Feature | System Level | User Level (Podman) |
|---------|--------------|-------------------|
| **Requires sudo** | ✅ Yes | ❌ No |
| **Isolation** | System-wide | User namespace |
| **Management** | systemd (root) | systemd (user) |
| **Data location** | `/var/lib/*` | `~/.local/share/*` |
| **Port binding** | All interfaces | User ports |
| **GPU access** | Direct | Via container passthrough |
| **Updates** | Manual rebuild | Auto-pull |
| **Conflicts** | Possible | Isolated |
| **Backup** | System backup | Home backup |

---

## Troubleshooting

### Services Won't Start

Check for port conflicts:
```bash
ss -tlnp | grep -E ":(6333|6334|11434|8081)"
```

If system services running:
```bash
# The deployment script handles this automatically,
# but you can manually check:
sudo systemctl status ollama.service qdrant.service
```

### Container Logs

```bash
# All services
podman-ai-stack logs

# Specific service
journalctl --user -u podman-local-ai-ollama.service -f
```

### Reset Stack

```bash
# Stop all
podman-ai-stack down

# Remove containers
podman rm -f $(podman ps -a -q --filter "label=nixos.quick-deploy.ai-stack=true")

# Remove network
podman network rm local-ai

# Restart
systemctl --user daemon-reload
podman-ai-stack up
```

---

## Summary

The Podman AI Stack provides a **complete local AI development environment**:

✅ **4 Integrated Services**: Ollama, Open WebUI, Qdrant, MindsDB
✅ **Rootless & Secure**: User-level containers, no sudo needed
✅ **Declarative**: Managed via home-manager configuration
✅ **Auto-Updating**: Latest versions pulled automatically
✅ **Conflict-Free**: Proper conditional logic prevents port conflicts
✅ **Full-Featured**: Complete AI/ML development platform

**Perfect for**:
- Local LLM development
- RAG pipelines
- AI experimentation
- Privacy-focused AI applications
- Offline AI development

---

**Documentation Version**: 1.0.0
**Last Updated**: 2025-11-16
