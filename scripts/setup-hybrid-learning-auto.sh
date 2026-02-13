#!/usr/bin/env bash
#
# Automated Hybrid Learning Setup (Non-Interactive)
# Called by phase-09 during nixos-quick-deploy
#

set -euo pipefail

PROJECT_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
ENABLE_LOCAL_DEPS="${HYBRID_LEARNING_LOCAL_DEPS:-false}"
QDRANT_VECTOR_SIZE="${QDRANT_VECTOR_SIZE:-768}"
QDRANT_DISTANCE="${QDRANT_DISTANCE:-Cosine}"
SETUP_TIMEOUT="${HYBRID_LEARNING_SETUP_TIMEOUT:-900}"
STATE_DIR="${HYBRID_LEARNING_STATE_DIR:-$HOME/.cache/nixos-quick-deploy}"
MARKER_FILE="${HYBRID_LEARNING_MARKER_FILE:-$STATE_DIR/hybrid-learning-ready}"
mkdir -p "$STATE_DIR" >/dev/null 2>&1 || true

timeout_cmd=()
if command -v timeout >/dev/null 2>&1; then
    timeout_cmd=(timeout "${SETUP_TIMEOUT}")
fi

echo "==> Step 0: Checking existing hybrid learning setup..."
if [[ -f "$MARKER_FILE" ]]; then
    if curl -sf --max-time 3 http://${SERVICE_HOST:-localhost}:6333/healthz >/dev/null 2>&1; then
        echo "✓ Hybrid learning already initialized (marker: $MARKER_FILE)"
        exit 0
    fi
    echo "⚠ Marker present but Qdrant not ready; continuing setup."
fi

echo "==> Step 1: Installing Python dependencies..."
if [[ "$ENABLE_LOCAL_DEPS" == "true" ]]; then
    cd "${PROJECT_ROOT}/ai-stack/mcp-servers/hybrid-coordinator"
    if [ ! -d "venv" ]; then
        echo "  Creating virtual environment..."
        python3 -m venv venv || {
            echo "✗ Failed to create virtual environment"
            exit 1
        }
    fi
    echo "  Activating virtual environment and installing packages..."
    # Set pip timeout to prevent hanging on large downloads
    export PIP_DEFAULT_TIMEOUT=300
    export PIP_DISABLE_PIP_VERSION_CHECK=1
    if source venv/bin/activate && "${timeout_cmd[@]}" pip install --no-input --timeout 300 --retries 3 -q -r requirements.txt; then
        deactivate
        echo "✓ Dependencies installed"
    else
        echo "✗ Failed to install dependencies"
        deactivate 2>/dev/null || true
        exit 1
    fi
else
    echo "  Skipping local Python deps (HYBRID_LEARNING_LOCAL_DEPS=false)"
fi

echo "==> Step 2: Configuring environment..."
ENV_FILE="${AI_STACK_ENV_FILE:-$HOME/.config/nixos-ai-stack/.env}"
if [ ! -f "$ENV_FILE" ]; then
    echo "✗ Missing AI stack env file: $ENV_FILE"
    echo "  Re-run nixos-quick-deploy.sh to set AI stack credentials."
    exit 1
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
if ! command -v kubectl >/dev/null 2>&1; then
    echo "✗ kubectl not found. K3s/Kubernetes is required."
    exit 1
fi
if ! kubectl --request-timeout=30s cluster-info >/dev/null 2>&1; then
    echo "✗ Kubernetes cluster not reachable. Start K3s and try again."
    exit 1
fi
tmp_root="${TMPDIR:-/${TMP_FALLBACK:-tmp}}"
hybrid_log="${tmp_root}/hybrid-learning-k8s.log"
if "${timeout_cmd[@]}" kubectl --request-timeout=30s apply -k "${PROJECT_ROOT}/ai-stack/kubernetes" \
  > >(tee "$hybrid_log") 2>&1; then
    echo "✓ AI stack deployment initiated"
else
    echo "✗ Failed to apply AI stack manifests"
    echo "  Check logs: $hybrid_log"
    exit 1
fi

echo "==> Step 5: Waiting for services..."
qdrant_ready=false
for i in $(seq 1 30); do
    if curl -sf --max-time 3 http://${SERVICE_HOST:-localhost}:6333/healthz >/dev/null 2>&1; then
        qdrant_ready=true
        echo "✓ Qdrant is ready"
        break
    fi
    if [[ $i -eq 1 ]]; then
        echo "  Waiting for Qdrant to start..."
    fi
    sleep 2
done
if [[ "$qdrant_ready" != "true" ]]; then
    echo "⚠ Qdrant not ready after 60 seconds"
fi

echo "==> Step 6: Initializing Qdrant collections..."
collections=(
  "codebase-context"
  "skills-patterns"
  "error-solutions"
  "best-practices"
  "interaction-history"
)

qdrant_ok=true
for name in "${collections[@]}"; do
    payload=$(cat <<EOF
{"vectors":{"size":${QDRANT_VECTOR_SIZE},"distance":"${QDRANT_DISTANCE}"}}
EOF
)
    if curl -sf --max-time 5 -X PUT "http://${SERVICE_HOST:-localhost}:6333/collections/${name}" \
        -H "Content-Type: application/json" \
        -d "${payload}" >/dev/null 2>&1; then
        echo "✓ Created collection '${name}'"
        continue
    fi
    if curl -sf --max-time 5 "http://${SERVICE_HOST:-localhost}:6333/collections/${name}" >/dev/null 2>&1; then
        echo "✓ Collection '${name}' exists"
    else
        echo "✗ Failed to create collection '${name}'"
        qdrant_ok=false
    fi
done

if [[ "$qdrant_ok" == "true" ]]; then
    echo "✓ Qdrant collections initialized"
    touch "$MARKER_FILE" 2>/dev/null || true
else
    echo "⚠ Qdrant initialization incomplete (will retry on first use)"
fi

echo ""
echo "✅ Hybrid Learning System Setup Complete!"
echo ""
echo "Services running:"
echo "  • Qdrant:     http://${SERVICE_HOST:-localhost}:6333"
echo "  • llama.cpp:   http://${SERVICE_HOST:-localhost}:8080"
echo "  • Ollama:     http://${SERVICE_HOST:-localhost}:11434"
echo "  • Open WebUI: http://${SERVICE_HOST:-localhost}:3001"
echo "  • PostgreSQL: localhost:5432"
echo "  • Redis:      localhost:6379"
echo ""
echo "Dashboard: ${PROJECT_ROOT}/ai-stack/dashboard/index.html"
