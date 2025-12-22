#!/usr/bin/env bash
#
# Initialize AI Stack - Complete Setup and Validation
# Version: 2.0.0
# Date: 2025-12-20
#
# This script:
# 1. Validates podman is working correctly
# 2. Starts all AI stack services
# 3. Initializes Qdrant collections with enhanced schema
# 4. Downloads required models (Ollama, Lemonade)
# 5. Runs comprehensive health checks
# 6. Tests RAG workflow end-to-end
#
# Usage:
#   ./scripts/initialize-ai-stack.sh [--skip-models] [--test-only]
#

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"
COMPOSE_DIR="${PROJECT_ROOT}/ai-stack/compose"
COMPOSE_FILE="docker-compose.yml"

# Colors
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
CYAN='\033[0;36m'
NC='\033[0m'

# Flags
SKIP_MODELS=false
TEST_ONLY=false

# Parse arguments
for arg in "$@"; do
    case $arg in
        --skip-models) SKIP_MODELS=true ;;
        --test-only) TEST_ONLY=true ;;
        --help)
            echo "Usage: $0 [OPTIONS]"
            echo "Options:"
            echo "  --skip-models   Skip model downloads (faster for testing)"
            echo "  --test-only     Only run tests, don't start services"
            echo "  --help          Show this help"
            exit 0
            ;;
    esac
done

info() { echo -e "${BLUE}ℹ${NC} $1"; }
success() { echo -e "${GREEN}✓${NC} $1"; }
warning() { echo -e "${YELLOW}⚠${NC} $1"; }
error() { echo -e "${RED}✗${NC} $1"; }
step() { echo -e "\n${CYAN}==>${NC} ${BOLD}$1${NC}"; }

# Step 1: Validate Podman
step "Step 1: Validating Podman installation"

if ! command -v podman &>/dev/null; then
    error "Podman not found. Please ensure NixOS configuration includes podman.nix"
    exit 1
fi

info "Testing podman functionality..."
if podman ps &>/dev/null; then
    success "Podman is working correctly"
else
    error "Podman test failed. Common causes:"
    echo "  1. newuidmap/newgidmap not configured (check /etc/nixos/configuration.nix)"
    echo "  2. User not in podman group"
    echo "  3. Sub-UID/GID mappings missing"
    echo ""
    echo "To fix: Ensure templates/nixos-improvements/podman.nix is imported and rebuild:"
    echo "  sudo nixos-rebuild switch"
    exit 1
fi

if ! command -v podman-compose &>/dev/null; then
    error "podman-compose not found"
    exit 1
fi

success "Podman validation complete"

# Step 2: Ensure data directories exist
step "Step 2: Creating data directories"

DATA_DIR="${HOME}/.local/share/nixos-ai-stack"
mkdir -p "${DATA_DIR}"/{qdrant,ollama,lemonade-models,open-webui,postgres,redis,mindsdb,fine-tuning}
mkdir -p "${HOME}/.cache/huggingface"

success "Data directories created at ${DATA_DIR}"

# Step 3: Start AI Stack (unless test-only)
if [ "$TEST_ONLY" = false ]; then
    step "Step 3: Starting AI Stack services"

    cd "$COMPOSE_DIR"

    # Check if .env exists, create from example if not
    if [ ! -f ".env" ]; then
        if [ -f ".env.example" ]; then
            info "Creating .env from .env.example..."
            cp .env.example .env
        fi
    fi

    info "Starting containers with podman-compose..."
    if podman-compose -f "$COMPOSE_FILE" up -d --build; then
        success "AI Stack started"
    else
        error "Failed to start AI stack"
        exit 1
    fi

    info "Waiting for services to initialize (30 seconds)..."
    sleep 30
else
    info "Skipping service start (--test-only mode)"
fi

# Step 4: Check service health
step "Step 4: Checking service health"

python3 "${SCRIPT_DIR}/check-ai-stack-health-v2.py" -v
HEALTH_STATUS=$?

if [ $HEALTH_STATUS -ne 0 ]; then
    warning "Some services are not healthy. Check logs:"
    echo "  podman-compose logs -f"
fi

# Step 5: Initialize Qdrant collections with enhanced schema
step "Step 5: Initializing Qdrant collections"

python3 << 'PYEOF'
import sys
import time
import requests
from qdrant_client import QdrantClient
from qdrant_client.models import Distance, VectorParams, PayloadSchemaType

# Wait for Qdrant
print("Waiting for Qdrant to be ready...")
for i in range(60):
    try:
        response = requests.get("http://localhost:6333/healthz", timeout=2)
        if response.status_code == 200:
            print("✓ Qdrant is ready")
            break
    except:
        pass
    time.sleep(1)
else:
    print("✗ Qdrant did not become ready in time")
    sys.exit(1)

client = QdrantClient(url="http://localhost:6333")

# Define collections with enhanced schema
# Note: nomic-embed-text produces 768-dimensional embeddings
collections_config = {
    "codebase-context": {
        "description": "Code snippets, functions, and file structures",
        "vector_size": 768,
    },
    "skills-patterns": {
        "description": "Reusable patterns and high-value solutions",
        "vector_size": 768,
    },
    "error-solutions": {
        "description": "Error messages paired with working solutions",
        "vector_size": 768,
    },
    "best-practices": {
        "description": "Generic best practices and guidelines",
        "vector_size": 768,
    },
    "interaction-history": {
        "description": "Complete agent interaction logs for analysis",
        "vector_size": 768,
    },
}

existing_collections = {c.name for c in client.get_collections().collections}

for name, config in collections_config.items():
    if name not in existing_collections:
        client.create_collection(
            collection_name=name,
            vectors_config=VectorParams(
                size=config["vector_size"],
                distance=Distance.COSINE
            )
        )
        print(f"✓ Created collection '{name}': {config['description']}")
    else:
        print(f"✓ Collection '{name}' already exists")

print("\n✓ All Qdrant collections initialized")
PYEOF

# Step 6: Download models (unless skipped)
if [ "$SKIP_MODELS" = false ] && [ "$TEST_ONLY" = false ]; then
    step "Step 6: Downloading AI models"

    info "Pulling Ollama embedding model (nomic-embed-text)..."
    if curl -s -X POST http://localhost:11434/api/pull \
        -d '{"name": "nomic-embed-text"}' | grep -q "success"; then
        success "Ollama model downloaded"
    else
        warning "Ollama model download may be in progress, check: podman logs -f local-ai-ollama"
    fi

    info "Lemonade will download Qwen2.5-Coder-7B on first use (this may take 10-45 minutes)"
    info "Monitor progress: podman logs -f local-ai-lemonade"
else
    info "Skipping model downloads"
fi

# Step 7: Initialize Qdrant collection indexes
step "Step 7: Creating Qdrant payload indexes"

if [ -f "${SCRIPT_DIR}/initialize-qdrant-collections.sh" ]; then
    info "Running Qdrant collection initialization..."
    bash "${SCRIPT_DIR}/initialize-qdrant-collections.sh"
else
    warning "Qdrant initialization script not found, skipping index creation"
fi

# Step 8: Generate dashboard data
step "Step 8: Generating dashboard metrics"

if [ -f "${SCRIPT_DIR}/generate-dashboard-data.sh" ]; then
    info "Generating initial dashboard data..."
    bash "${SCRIPT_DIR}/generate-dashboard-data.sh"
    success "Dashboard data generated"
else
    warning "Dashboard generation script not found"
fi

# Step 9: Test RAG system
step "Step 9: Testing RAG system"

if [ -f "${SCRIPT_DIR}/rag-system-complete.py" ]; then
    info "Running RAG system diagnostic and test..."
    python3 "${SCRIPT_DIR}/rag-system-complete.py"
    RAG_STATUS=$?

    if [ $RAG_STATUS -eq 0 ]; then
        success "RAG system test passed"
    else
        warning "RAG system test had issues (this is expected if models are still downloading)"
    fi
else
    warning "RAG system test script not found, skipping"
fi

# Step 10: Summary
step "Setup Complete!"

echo ""
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo "  AI STACK READY"
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo ""
echo "Services:"
echo "  • Qdrant Vector DB:   http://localhost:6333/dashboard"
echo "  • Ollama Embeddings:  http://localhost:11434"
echo "  • Lemonade GGUF:      http://localhost:8080"
echo "  • Open WebUI:         http://localhost:3001"
echo "  • PostgreSQL:         localhost:5432"
echo "  • Redis:              localhost:6379"
echo "  • AIDB MCP Server:    http://localhost:8091"
echo "  • Hybrid Coordinator: http://localhost:8092 (deploy separately)"
echo ""
echo "Management:"
echo "  • Status:  ./scripts/hybrid-ai-stack.sh status"
echo "  • Logs:    podman-compose -f ai-stack/compose/docker-compose.yml logs -f"
echo "  • Stop:    ./scripts/hybrid-ai-stack.sh down"
echo "  • Restart: ./scripts/hybrid-ai-stack.sh restart"
echo ""
echo "Testing:"
echo "  • Health Check:       python3 scripts/check-ai-stack-health-v2.py -v"
echo "  • RAG Test:           python3 scripts/rag-system-complete.py"
echo "  • Dashboard Metrics:  bash scripts/generate-dashboard-data.sh"
echo ""
echo "Continuous Learning:"
echo "  • RAG Collections:    5 collections initialized in Qdrant"
echo "  • Telemetry:          ${DATA_DIR}/telemetry/"
echo "  • Fine-tuning Data:   ${DATA_DIR}/fine-tuning/"
echo "  • Dashboard Data:     ~/.local/share/nixos-system-dashboard/"
echo ""
echo "Data Location:"
echo "  • ${DATA_DIR}"
echo ""
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo ""

if [ "$SKIP_MODELS" = false ]; then
    echo "⏳ Note: Models may still be downloading. Monitor with:"
    echo "   podman logs -f local-ai-ollama"
    echo "   podman logs -f local-ai-lemonade"
    echo ""
fi

exit 0
