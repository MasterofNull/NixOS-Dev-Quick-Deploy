#!/usr/bin/env bash
#
# Automated Hybrid Learning Setup (Non-Interactive)
# Called by phase-09 during nixos-quick-deploy
#

set -euo pipefail

PROJECT_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"

# Determine compose command
if command -v podman-compose >/dev/null 2>&1; then
    COMPOSE_CMD="podman-compose"
elif command -v docker-compose >/dev/null 2>&1; then
    COMPOSE_CMD="docker-compose"
else
    echo "Error: Neither podman-compose nor docker-compose found"
    exit 1
fi

echo "==> Step 1: Installing Python dependencies..."
cd "${PROJECT_ROOT}/ai-stack/mcp-servers/hybrid-coordinator"
if [ ! -d "venv" ]; then
    python3 -m venv venv
fi
source venv/bin/activate
pip install -q -r requirements.txt
deactivate
echo "✓ Dependencies installed"

echo "==> Step 2: Configuring environment..."
ENV_FILE="${PROJECT_ROOT}/ai-stack/compose/.env"
if [ ! -f "$ENV_FILE" ]; then
    cp "${PROJECT_ROOT}/ai-stack/compose/.env.example" "$ENV_FILE"
fi

if ! grep -q "HYBRID_MODE_ENABLED" "$ENV_FILE"; then
    cat >> "$ENV_FILE" << 'ENVEOF'

# Hybrid Learning Configuration
HYBRID_MODE_ENABLED=true
LOCAL_CONFIDENCE_THRESHOLD=0.7
HIGH_VALUE_THRESHOLD=0.7
PATTERN_EXTRACTION_ENABLED=true
AUTO_FINETUNE_ENABLED=false
FINETUNE_DATA_PATH=~/.local/share/nixos-ai-stack/fine-tuning/dataset.jsonl
ENVEOF
fi
echo "✓ Environment configured"

echo "==> Step 3: Creating directories..."
mkdir -p ~/.local/share/nixos-ai-stack/{lemonade-models,fine-tuning,qdrant,ollama,open-webui,postgres,redis,aidb,aidb-cache,telemetry}
mkdir -p ~/.cache/huggingface
echo "✓ Directories created"

echo "==> Step 4: Starting AI stack..."
cd "${PROJECT_ROOT}/ai-stack/compose"
$COMPOSE_CMD up -d
echo "✓ AI stack started"

echo "==> Step 5: Waiting for services..."
sleep 10

echo "==> Step 6: Initializing Qdrant collections..."
python3 << 'PYEOF'
from qdrant_client import QdrantClient
from qdrant_client.models import Distance, VectorParams
import time

# Wait for Qdrant to be ready
for i in range(30):
    try:
        client = QdrantClient(url="http://localhost:6333")
        break
    except:
        time.sleep(2)
else:
    print("Warning: Qdrant not ready, collections will be created on first use")
    exit(0)

collections = {
    "codebase-context": 384,
    "skills-patterns": 384,
    "error-solutions": 384,
    "best-practices": 384,
    "interaction-history": 384
}

existing = [c.name for c in client.get_collections().collections]
for name, size in collections.items():
    if name not in existing:
        client.create_collection(
            collection_name=name,
            vectors_config=VectorParams(size=size, distance=Distance.COSINE)
        )
        print(f"✓ Created collection '{name}'")
    else:
        print(f"✓ Collection '{name}' exists")
PYEOF

echo ""
echo "✅ Hybrid Learning System Setup Complete!"
echo ""
echo "Services running:"
echo "  • Qdrant:     http://localhost:6333"
echo "  • Lemonade:   http://localhost:8080"
echo "  • Ollama:     http://localhost:11434"
echo "  • Open WebUI: http://localhost:3001"
echo "  • PostgreSQL: localhost:5432"
echo "  • Redis:      localhost:6379"
echo ""
echo "Dashboard: ${PROJECT_ROOT}/ai-stack/dashboard/index.html"
