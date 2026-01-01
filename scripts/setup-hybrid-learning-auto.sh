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
    echo "  Creating virtual environment..."
    python3 -m venv venv || {
        echo "✗ Failed to create virtual environment"
        exit 1
    }
fi
echo "  Activating virtual environment and installing packages..."
if source venv/bin/activate && pip install -q -r requirements.txt; then
    deactivate
    echo "✓ Dependencies installed"
else
    echo "✗ Failed to install dependencies"
    deactivate 2>/dev/null || true
    exit 1
fi

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
mkdir -p ~/.local/share/nixos-ai-stack/{llama-cpp-models,fine-tuning,qdrant,open-webui,postgres,redis,aidb,aidb-cache,telemetry}
mkdir -p ~/.cache/huggingface
echo "✓ Directories created"

echo "==> Step 4: Starting AI stack..."
cd "${PROJECT_ROOT}/ai-stack/compose"
if $COMPOSE_CMD up -d 2>&1 | tee /tmp/hybrid-learning-compose.log; then
    echo "✓ AI stack containers started"
else
    echo "✗ Failed to start AI stack containers"
    echo "  Check logs: /tmp/hybrid-learning-compose.log"
    exit 1
fi

echo "==> Step 5: Waiting for services..."
sleep 10

echo "==> Step 6: Initializing Qdrant collections..."
if python3 << 'PYEOF'
from qdrant_client import QdrantClient
from qdrant_client.models import Distance, VectorParams
import time
import sys

# Wait for Qdrant to be ready
print("Waiting for Qdrant to start...")
connected = False
for i in range(30):
    try:
        client = QdrantClient(url="http://localhost:6333")
        client.get_collections()  # Test connection
        connected = True
        print(f"✓ Connected to Qdrant after {i*2} seconds")
        break
    except Exception as e:
        if i == 0:
            print(f"Attempt {i+1}/30: Waiting for Qdrant...")
        time.sleep(2)

if not connected:
    print("✗ Warning: Qdrant not ready after 60 seconds")
    print("  Collections will be created on first use")
    sys.exit(1)

collections = {
    "codebase-context": 384,
    "skills-patterns": 384,
    "error-solutions": 384,
    "best-practices": 384,
    "interaction-history": 384
}

try:
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
except Exception as e:
    print(f"✗ Error creating collections: {e}")
    sys.exit(1)
PYEOF
then
    echo "✓ Qdrant collections initialized"
else
    echo "⚠ Qdrant initialization incomplete (will retry on first use)"
fi

echo ""
echo "✅ Hybrid Learning System Setup Complete!"
echo ""
echo "Services running:"
echo "  • Qdrant:     http://localhost:6333"
echo "  • llama.cpp:   http://localhost:8080"
echo "  • Ollama:     http://localhost:11434"
echo "  • Open WebUI: http://localhost:3001"
echo "  • PostgreSQL: localhost:5432"
echo "  • Redis:      localhost:6379"
echo ""
echo "Dashboard: ${PROJECT_ROOT}/ai-stack/dashboard/index.html"
