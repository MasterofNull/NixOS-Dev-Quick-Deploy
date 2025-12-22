# Quick Start - Get AI Stack Running

**Purpose**: Get the hybrid learning system up and running in 5 minutes

---

## Prerequisites Check

```bash
# Verify services are running
./scripts/hybrid-ai-stack.sh status

# If not running, start them
./scripts/hybrid-ai-stack.sh up
```

---

## First-Time Setup (Automated)

If running for the first time after `nixos-quick-deploy.sh --with-ai-stack`:

```bash
# Check deployment status
cat DEPLOYMENT-STATUS.md

# Verify all containers
podman ps --filter "label=nixos.quick-deploy.ai-stack=true"

# Expected output: 6-7 containers running
# - local-ai-qdrant
# - local-ai-ollama
# - local-ai-lemonade
# - local-ai-open-webui
# - local-ai-postgres
# - local-ai-redis
# - local-ai-mindsdb (optional)
```

---

## Quick Health Check

```bash
# Qdrant Vector DB
curl http://localhost:6333/healthz
# Expected: {"title":"healthz OK","version":"1.x.x"}

# Ollama Embeddings
curl http://localhost:11434/api/tags
# Expected: {"models":[...]}

# Lemonade Inference
curl http://localhost:8080/health
# Expected: {"status":"ok"}

# Open WebUI
curl -I http://localhost:3001
# Expected: HTTP/1.1 200 OK

# PostgreSQL
podman exec local-ai-postgres pg_isready -U mcp
# Expected: /var/run/postgresql:5432 - accepting connections

# Redis
podman exec local-ai-redis redis-cli ping
# Expected: PONG
```

---

## Verify Qdrant Collections

```bash
# List all collections
curl http://localhost:6333/collections | jq

# Check each collection exists
for collection in codebase-context skills-patterns error-solutions best-practices interaction-history; do
    echo "Checking $collection..."
    curl -s http://localhost:6333/collections/$collection | jq '.result.status'
done
```

Expected: All 5 collections show `"green"`

---

## First Query to Local LLM

```bash
# Test Lemonade inference
curl -X POST http://localhost:8080/v1/chat/completions \
  -H "Content-Type: application/json" \
  -d '{
    "model": "qwen-coder",
    "messages": [{"role": "user", "content": "Hello, are you working?"}],
    "max_tokens": 50
  }' | jq
```

Expected response with generated text.

---

## First RAG Query (Python)

Create test script:

```python
#!/usr/bin/env python3
import ollama
from qdrant_client import QdrantClient

# Step 1: Create embedding
response = ollama.embeddings(
    model="nomic-embed-text",
    prompt="test query"
)
embedding = response["embedding"]

# Step 2: Search Qdrant
client = QdrantClient(url="http://localhost:6333")
results = client.search(
    collection_name="codebase-context",
    query_vector=embedding,
    limit=3
)

print(f"Found {len(results)} results")
for result in results:
    print(f"Score: {result.score}")
    print(f"Data: {result.payload}")
```

Run:
```bash
python3 test_rag.py
```

---

## Open Dashboard

```bash
# Open system dashboard in browser
firefox ai-stack/dashboard/index.html

# Or manually navigate to:
# file:///home/hyperd/Documents/try/NixOS-Dev-Quick-Deploy/ai-stack/dashboard/index.html
```

Dashboard shows:
- ✅ Real-time service health
- 📊 Learning metrics
- 🔄 Federation status
- 📚 Quick doc links

---

## Access Web Interface

```bash
# Open WebUI in browser
firefox http://localhost:3001
```

Features:
- ChatGPT-like interface
- Access to local LLMs
- RAG web search enabled
- No authentication required (local only)

---

## Common First-Time Issues

### Issue: Containers not starting
```bash
# Check container logs
./scripts/hybrid-ai-stack.sh logs

# Restart specific service
podman restart local-ai-qdrant
```

### Issue: Qdrant collections missing
```bash
# Re-initialize collections
cd ai-stack/compose
python3 << 'EOF'
from qdrant_client import QdrantClient
from qdrant_client.models import Distance, VectorParams

client = QdrantClient(url="http://localhost:6333")

collections = {
    "codebase-context": 384,
    "skills-patterns": 384,
    "error-solutions": 384,
    "best-practices": 384,
    "interaction-history": 384
}

for name, size in collections.items():
    try:
        client.create_collection(
            collection_name=name,
            vectors_config=VectorParams(size=size, distance=Distance.COSINE)
        )
        print(f"✓ Created {name}")
    except Exception as e:
        print(f"✗ {name}: {e}")
EOF
```

### Issue: Ollama models not downloaded
```bash
# Pull embedding model
podman exec local-ai-ollama ollama pull nomic-embed-text

# Verify
podman exec local-ai-ollama ollama list
```

### Issue: Lemonade model downloading
```bash
# Check download progress
podman logs -f local-ai-lemonade

# First download takes 10-45 minutes (7-32GB models)
# Patience required!
```

---

## Quick Operations Reference

```bash
# Start everything
./scripts/hybrid-ai-stack.sh up

# Stop everything
./scripts/hybrid-ai-stack.sh down

# Restart everything
./scripts/hybrid-ai-stack.sh restart

# View logs (all services)
./scripts/hybrid-ai-stack.sh logs

# View specific service logs
./scripts/hybrid-ai-stack.sh logs qdrant

# Check status
./scripts/hybrid-ai-stack.sh status

# Clean restart (remove containers, keep data)
./scripts/hybrid-ai-stack.sh down
./scripts/hybrid-ai-stack.sh up
```

---

## Data Locations

All data stored in: `~/.local/share/nixos-ai-stack/`

```
~/.local/share/nixos-ai-stack/
├── qdrant/              # Vector database
├── ollama/              # Ollama models
├── lemonade-models/     # GGUF models (10.5GB)
├── open-webui/          # Web UI data
├── postgres/            # PostgreSQL data
├── redis/               # Redis persistence
└── fine-tuning/         # Training datasets
```

**Backup important data**:
```bash
tar -czf ai-stack-backup-$(date +%Y%m%d).tar.gz \
  ~/.local/share/nixos-ai-stack/qdrant \
  ~/.local/share/nixos-ai-stack/postgres \
  ~/.local/share/nixos-ai-stack/fine-tuning
```

---

## Next Steps

1. **Store your first learning**: [Continuous Learning Guide](22-CONTINUOUS-LEARNING.md)
2. **Try RAG queries**: [RAG & Context Guide](21-RAG-CONTEXT.md)
3. **Check what's running**: [Service Status Guide](02-SERVICE-STATUS.md)
4. **Explore workflows**: [Hybrid Workflow Guide](40-HYBRID-WORKFLOW.md)

---

## Emergency Commands

```bash
# Everything broken? Stop all containers
podman stop $(podman ps -aq --filter "label=nixos.quick-deploy.ai-stack=true")

# Nuclear option: Remove all containers (keeps data)
podman rm -f $(podman ps -aq --filter "label=nixos.quick-deploy.ai-stack=true")

# Start fresh
./scripts/hybrid-ai-stack.sh up

# System completely broken? Rollback NixOS
./nixos-quick-deploy.sh --rollback
```

---

**You're ready!** The system is now running and ready for continuous learning.
