#!/usr/bin/env bash
# ============================================================================
# Setup Hybrid Local-Remote AI Learning System
# ============================================================================
# Automated setup for the continuous learning AI system
# ============================================================================

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(cd "${SCRIPT_DIR}/.." && pwd)"

# Colors
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m'

info() { echo -e "${BLUE}ℹ${NC} $*"; }
success() { echo -e "${GREEN}✓${NC} $*"; }
warning() { echo -e "${YELLOW}⚠${NC} $*"; }
error() { echo -e "${RED}✗${NC} $*"; }

echo ""
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo "  Hybrid Local-Remote AI Learning System Setup"
echo "  Continuous Learning for Local LLMs + Remote Agents"
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo ""

# ============================================================================
# Step 1: Check Prerequisites
# ============================================================================

info "Step 1: Checking prerequisites..."

# Check Python
if ! command -v python3 &> /dev/null; then
    error "Python 3 is required but not found"
    exit 1
fi
success "Python 3 found"

# Check pip
if ! command -v pip3 &> /dev/null; then
    error "pip3 is required but not found"
    exit 1
fi
success "pip3 found"

if ! command -v kubectl &> /dev/null; then
    error "kubectl is required but not found"
    exit 1
fi
success "kubectl found"

echo ""

# ============================================================================
# Step 2: Install Hybrid Coordinator Dependencies
# ============================================================================

info "Step 2: Installing Hybrid Coordinator dependencies..."

cd "${PROJECT_ROOT}/ai-stack/mcp-servers/hybrid-coordinator"

# Create virtual environment if it doesn't exist
if [ ! -d "venv" ]; then
    info "Creating Python virtual environment..."
    python3 -m venv venv || {
        error "Failed to create virtual environment"
        exit 1
    }
fi

# Activate virtual environment and install dependencies
info "Installing dependencies in virtual environment..."
# Set pip timeout to prevent hanging on large downloads
export PIP_DEFAULT_TIMEOUT=300
if source venv/bin/activate && pip install --timeout 300 --retries 3 -r requirements.txt; then
    success "Dependencies installed in virtual environment"
    deactivate
else
    error "Failed to install dependencies"
    exit 1
fi

echo ""

# ============================================================================
# Step 3: Configure Environment
# ============================================================================

info "Step 3: Configuring environment..."

ENV_FILE="${AI_STACK_ENV_FILE:-$HOME/.config/nixos-ai-stack/.env}"

if [ ! -f "$ENV_FILE" ]; then
    error "Missing AI stack env file: $ENV_FILE"
    exit 1
fi

# Add hybrid learning configuration
if ! grep -q "HYBRID_MODE_ENABLED" "$ENV_FILE"; then
    info "Adding hybrid learning configuration to .env..."
    cat >> "$ENV_FILE" << 'EOF'

# ============================================================================
# Hybrid Learning Configuration
# ============================================================================
HYBRID_MODE_ENABLED=true
LOCAL_CONFIDENCE_THRESHOLD=0.7
HIGH_VALUE_THRESHOLD=0.7
PATTERN_EXTRACTION_ENABLED=true
AUTO_FINETUNE_ENABLED=false

# Paths
FINETUNE_DATA_PATH=~/.local/share/nixos-ai-stack/fine-tuning/dataset.jsonl
EOF
    success "Hybrid learning configuration added"
else
    success "Hybrid learning configuration already present"
fi

echo ""

# ============================================================================
# Step 4: Create Required Directories
# ============================================================================

info "Step 4: Creating required directories..."

# Create all required directories for AI stack
mkdir -p ~/.local/share/nixos-ai-stack/llama-cpp-models
mkdir -p ~/.local/share/nixos-ai-stack/fine-tuning
mkdir -p ~/.local/share/nixos-ai-stack/aidb
mkdir -p ~/.local/share/nixos-ai-stack/aidb-cache
mkdir -p ~/.local/share/nixos-ai-stack/telemetry
mkdir -p ~/.cache/huggingface
mkdir -p ~/.cache/nixos-ai-stack
mkdir -p /var/lib/hybrid-learning/{models,exports,fine-tuning} 2>/dev/null || {
    info "System directories require sudo access, will be created by NixOS module"
}

success "Directories created"
echo ""

# ============================================================================
# Step 5: Download GGUF Models
# ============================================================================

info "Step 5: Downloading GGUF models..."

read -p "Download recommended swap models now? (qwen3-4b,qwen-coder,deepseek) [Y/n]: " download_confirm

if [[ ! "$download_confirm" =~ ^[Nn]$ ]]; then
    if bash "${PROJECT_ROOT}/scripts/download-llama-cpp-models.sh" --models "qwen3-4b,qwen-coder,deepseek"; then
        success "Models downloaded successfully"
    else
        warning "Model download incomplete - models will download on first container startup"
    fi
else
    info "Skipping model download - models will download on first container startup"
fi

echo ""

# ============================================================================
# Step 6: Start AI Stack
# ============================================================================

info "Step 6: Starting AI stack..."

if kubectl --request-timeout=30s apply -k "${PROJECT_ROOT}/ai-stack/kubernetes"; then
    success "AI stack deployment initiated"
else
    error "Failed to start AI stack"
    exit 1
fi

echo ""
info "Waiting for services to initialize..."
sleep 5

# ============================================================================
# Step 7: Verify Services
# ============================================================================

info "Step 7: Verifying services..."

check_service() {
    local name=$1
    local port=$2
    local endpoint=${3:-/health}

    if curl -sf --max-time 5 "http://${SERVICE_HOST:-localhost}:$port$endpoint" > /dev/null 2>&1; then
        success "$name is running on port $port"
        return 0
    else
        warning "$name not responding on port $port (may still be starting)"
        return 1
    fi
}

# Check llama.cpp services
check_service "llama.cpp General" 8080 "/health"
check_service "llama.cpp Coder" 8001 "/health"
check_service "llama.cpp DeepSeek" 8003 "/health"

# Check Qdrant
check_service "Qdrant Vector DB" 6333 ""

# Check Ollama
check_service "Ollama" 11434 "/api/tags"

# Check Open WebUI
check_service "Open WebUI" 3001 ""

echo ""

# ============================================================================
# Step 8: Initialize Qdrant Collections
# ============================================================================

info "Step 8: Initializing Qdrant collections..."

python3 << 'PYTHON_SCRIPT'
import sys
import asyncio
from pathlib import Path

# Add hybrid-coordinator to path
sys.path.insert(0, str(Path(__file__).parent / "ai-stack/mcp-servers/hybrid-coordinator"))

try:
    from server import initialize_server
    asyncio.run(initialize_server())
    print("✓ Qdrant collections initialized")
except Exception as e:
    print(f"⚠ Error initializing collections: {e}")
    print("Collections will be created on first use")
PYTHON_SCRIPT

echo ""

# ============================================================================
# Step 9: Create Test Interaction
# ============================================================================

info "Step 9: Creating test interaction to verify system..."

python3 << 'PYTHON_SCRIPT'
import asyncio
import os

import httpx
from qdrant_client import QdrantClient

service_host = os.getenv("SERVICE_HOST", "localhost")

async def test_system():
    try:
        # Test Qdrant
        client = QdrantClient(f"http://{service_host}:6333")
        collections = client.get_collections().collections
        print(f"✓ Qdrant collections: {len(collections)}")

        # Test llama.cpp
        async with httpx.AsyncClient() as http:
            response = await http.get(f"http://{service_host}:8080/health", timeout=5.0)
            if response.status_code == 200:
                print("✓ llama.cpp inference ready")

        # Test embedding (Ollama)
        async with httpx.AsyncClient() as http:
            response = await http.post(
                f"http://{service_host}:11434/api/embeddings",
                json={"model": "nomic-embed-text", "prompt": "test"},
                timeout=10.0
            )
            if response.status_code == 200:
                print("✓ Embedding service ready")

    except Exception as e:
        print(f"⚠ Some services may still be starting: {e}")

asyncio.run(test_system())
PYTHON_SCRIPT

echo ""

# ============================================================================
# Summary
# ============================================================================

echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo "  Setup Complete!"
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo ""
success "Hybrid Local-Remote AI Learning System is ready!"
echo ""
echo "Service URLs:"
echo "  • llama.cpp General:    http://${SERVICE_HOST:-localhost}:8080"
echo "  • llama.cpp Coder:      http://${SERVICE_HOST:-localhost}:8001"
echo "  • llama.cpp DeepSeek:   http://${SERVICE_HOST:-localhost}:8003"
echo "  • Qdrant Vector DB:    http://${SERVICE_HOST:-localhost}:6333"
echo "  • Ollama:              http://${SERVICE_HOST:-localhost}:11434"
echo "  • Open WebUI:          http://${SERVICE_HOST:-localhost}:3001"
echo ""
echo "Qdrant Collections:"
echo "  • codebase-context     - Code snippets and context"
echo "  • skills-patterns      - Reusable patterns"
echo "  • error-solutions      - Known errors and fixes"
echo "  • interaction-history  - Complete interaction log"
echo "  • best-practices       - Curated guidelines"
echo ""
echo "Next Steps:"
echo "  1. Read the guide: cat HYBRID-AI-SYSTEM-GUIDE.md"
echo "  2. Seed your codebase into Qdrant collections"
echo "  3. Start using remote agents with context augmentation"
echo "  4. Monitor learning progress in interaction-history"
echo "  5. Generate fine-tuning datasets when ready (500+ interactions)"
echo ""
echo "Monitoring:"
echo "  • View logs:     ${COMPOSE_CMD} logs -f"
echo "  • Check Qdrant:  curl http://${SERVICE_HOST:-localhost}:6333/collections"
echo "  • Test llama.cpp: curl http://${SERVICE_HOST:-localhost}:8080/health"
echo ""
echo "Documentation:"
echo "  • Architecture:         ai-knowledge-base/HYBRID-LEARNING-ARCHITECTURE.md"
echo "  • Complete Guide:       HYBRID-AI-SYSTEM-GUIDE.md"
echo "  • llama.cpp API:        ai-knowledge-base/reference/llama-cpp-api.md"
echo "  • Hybrid Coordinator:   ai-stack/mcp-servers/hybrid-coordinator/README.md"
echo ""
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
