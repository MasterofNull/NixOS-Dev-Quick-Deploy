#!/usr/bin/env bash
#
# Podman AI Stack Monitor
# Initialize and monitor the local AI stack (Ollama, Qdrant, Open WebUI, MindsDB)
#
# Usage: ./podman-ai-stack-monitor.sh [start|stop|status|logs|restart]
#

set -euo pipefail

# Colors
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
CYAN='\033[0;36m'
MAGENTA='\033[0;35m'
NC='\033[0m'
BOLD='\033[1m'

# Detect LLM backend from preferences
LLM_BACKEND_PREF_FILE="${HOME}/.cache/nixos-quick-deploy/preferences/llm-backend.env"
if [[ -f "$LLM_BACKEND_PREF_FILE" ]]; then
    LLM_BACKEND=$(awk -F'=' '/^LLM_BACKEND=/{print $2}' "$LLM_BACKEND_PREF_FILE" 2>/dev/null | tail -n1 | tr -d '\r')
fi
LLM_BACKEND="${LLM_BACKEND:-ollama}"

# Load models from preferences
LLM_MODELS_PREF_FILE="${HOME}/.cache/nixos-quick-deploy/preferences/llm-models.env"
if [[ -f "$LLM_MODELS_PREF_FILE" ]]; then
    LLM_MODELS=$(awk -F'=' '/^LLM_MODELS=/{print $2}' "$LLM_MODELS_PREF_FILE" 2>/dev/null | tail -n1 | tr -d '\r')
fi
# Default models - December 2025 best coding models for mobile workstations
# qwen2.5-coder:14b  - Best overall coding model
# deepseek-coder-v2  - Excellent for debugging/reasoning
# starcoder2:7b      - Fast autocomplete, 80+ languages
LLM_MODELS="${LLM_MODELS:-qwen2.5-coder:14b,deepseek-coder-v2,starcoder2:7b}"

# Model recommendations by VRAM tier
declare -A MODEL_TIERS=(
    ["8gb"]="qwen2.5-coder:7b,deepseek-coder:6.7b"
    ["16gb"]="qwen2.5-coder:14b,deepseek-coder-v2,starcoder2:7b"
    ["32gb"]="qwen2.5-coder:32b,codestral:22b,deepseek-coder-v2"
    ["48gb+"]="qwen2.5-coder:32b,codestral:22b,llama3.2:70b"
)

# Service names (dynamic based on backend)
if [[ "$LLM_BACKEND" == "lemonade" ]]; then
    SERVICES=(
        "podman-local-ai-network"
        "podman-local-ai-lemonade"
        "podman-local-ai-qdrant"
        "podman-local-ai-open-webui"
        "podman-local-ai-mindsdb"
    )
else
    SERVICES=(
        "podman-local-ai-network"
        "podman-local-ai-ollama"
        "podman-local-ai-qdrant"
        "podman-local-ai-open-webui"
        "podman-local-ai-mindsdb"
    )
fi

# Port mappings
declare -A PORTS=(
    ["ollama"]="11434"
    ["lemonade"]="8080"
    ["qdrant"]="6333"
    ["open-webui"]="8081"
    ["mindsdb"]="47334"
)

info()    { echo -e "${BLUE}[INFO]${NC} $*"; }
success() { echo -e "${GREEN}[✓]${NC} $*"; }
warn()    { echo -e "${YELLOW}[!]${NC} $*"; }
error()   { echo -e "${RED}[✗]${NC} $*" >&2; }
header()  { echo -e "\n${BOLD}${CYAN}$*${NC}"; }

show_banner() {
    echo -e "${MAGENTA}"
    if [[ "$LLM_BACKEND" == "lemonade" ]]; then
        cat << 'EOF'
╭─────────────────────────────────────────────────────────────────╮
│                                                                 │
│     🍋  Podman AI Stack Monitor (Lemonade)                      │
│                                                                 │
│     Backend: Lemonade (AMD ROCm optimized)                      │
│     Services: Lemonade, Qdrant, Open WebUI, MindsDB             │
│                                                                 │
╰─────────────────────────────────────────────────────────────────╯
EOF
    else
        cat << 'EOF'
╭─────────────────────────────────────────────────────────────────╮
│                                                                 │
│     🤖  Podman AI Stack Monitor (Ollama)                        │
│                                                                 │
│     Backend: Ollama (Universal)                                 │
│     Services: Ollama, Qdrant, Open WebUI, MindsDB               │
│                                                                 │
╰─────────────────────────────────────────────────────────────────╯
EOF
    fi
    echo -e "${NC}"
    echo -e "${CYAN}Configured models: ${LLM_MODELS}${NC}"
    echo ""
}

pull_models() {
    header "Pulling LLM Models"
    
    echo "Models to pull: $LLM_MODELS"
    echo ""
    
    # Convert comma-separated to array
    IFS=',' read -ra models <<< "$LLM_MODELS"
    
    if [[ "$LLM_BACKEND" == "lemonade" ]]; then
        info "Lemonade uses GGUF models from Hugging Face."
        info "Models will be downloaded on first inference or can be pre-downloaded."
        echo ""
        for model in "${models[@]}"; do
            model=$(echo "$model" | xargs)  # trim whitespace
            info "To download $model, use:"
            echo "  huggingface-cli download <repo>/$model --local-dir ~/.local/share/podman-ai-stack/lemonade-models/"
        done
        echo ""
        info "After downloading, restart the Lemonade container."
    else
        # Ollama model pull
        local container_name="local-ai-ollama"
        
        if ! podman ps --format '{{.Names}}' 2>/dev/null | grep -q "^${container_name}$"; then
            warn "Ollama container not running. Starting it first..."
            systemctl --user start podman-local-ai-ollama.service
            sleep 5
        fi
        
        for model in "${models[@]}"; do
            model=$(echo "$model" | xargs)  # trim whitespace
            info "Pulling model: $model"
            if podman exec -it "$container_name" ollama pull "$model" 2>&1; then
                success "Downloaded: $model"
            else
                warn "Failed to pull: $model (may need to retry)"
            fi
        done
    fi
    
    echo ""
    success "Model download complete."
}

check_prerequisites() {
    header "Checking Prerequisites"
    
    # Check subuid/subgid (managed by NixOS autoSubUidGidRange)
    if [[ ! -f /etc/subuid ]] || ! grep -q "^$(whoami):" /etc/subuid 2>/dev/null; then
        error "subuid not configured for $(whoami)"
        echo ""
        echo "  This is configured automatically by NixOS. Run:"
        echo "    sudo nixos-rebuild switch"
        echo ""
        echo "  If that doesn't work, the deploy script may need to be re-run."
        echo ""
        return 1
    fi
    success "subuid configured"
    
    if [[ ! -f /etc/subgid ]] || ! grep -q "^$(whoami):" /etc/subgid 2>/dev/null; then
        error "subgid not configured for $(whoami)"
        echo ""
        echo "  Run: sudo nixos-rebuild switch"
        return 1
    fi
    success "subgid configured"
    
    # Check podman
    if ! command -v podman &>/dev/null; then
        error "Podman not found"
        return 1
    fi
    success "Podman available ($(podman --version | head -1))"
    
    # Check systemd user services
    if ! systemctl --user list-unit-files | grep -q "podman-local-ai"; then
        error "Podman AI stack services not installed"
        echo "  Run: home-manager switch"
        return 1
    fi
    success "Podman AI stack services installed"
    
    return 0
}

get_service_status() {
    local service="$1"
    local status
    status=$(systemctl --user is-active "$service.service" 2>/dev/null || echo "unknown")
    echo "$status"
}

show_status() {
    header "Service Status"
    
    printf "  %-35s %-12s %s\n" "SERVICE" "STATUS" "DETAILS"
    printf "  %-35s %-12s %s\n" "───────────────────────────────────" "────────────" "───────────────────"
    
    for service in "${SERVICES[@]}"; do
        local status
        status=$(get_service_status "$service")
        
        local color="${RED}"
        local symbol="✗"
        if [[ "$status" == "active" ]]; then
            color="${GREEN}"
            symbol="✓"
        elif [[ "$status" == "activating" ]]; then
            color="${YELLOW}"
            symbol="⟳"
        elif [[ "$status" == "inactive" ]]; then
            color="${YELLOW}"
            symbol="○"
        fi
        
        # Get container info if running
        local details=""
        local short_name="${service#podman-local-ai-}"
        if [[ "$status" == "active" ]]; then
            local port="${PORTS[$short_name]:-}"
            if [[ -n "$port" ]]; then
                details="http://localhost:$port"
            fi
        fi
        
        printf "  %-35s ${color}%-12s${NC} %s\n" "$service" "[$symbol] $status" "$details"
    done
    
    echo ""
}

show_containers() {
    header "Container Status"
    
    if ! podman ps -a --format "table {{.Names}}\t{{.Status}}\t{{.Ports}}" 2>/dev/null | grep -E "ollama|qdrant|webui|mindsdb|local-ai"; then
        warn "No AI stack containers found"
    fi
    echo ""
}

start_stack() {
    header "Starting AI Stack"
    
    info "Reloading systemd..."
    systemctl --user daemon-reload
    
    for service in "${SERVICES[@]}"; do
        local status
        status=$(get_service_status "$service")
        
        if [[ "$status" == "active" ]]; then
            success "$service already running"
        else
            info "Starting $service..."
            if systemctl --user start "$service.service" 2>&1; then
                success "$service started"
            else
                warn "$service may be starting in background (image pull in progress)"
            fi
        fi
    done
    
    echo ""
    info "Services are starting. Large images may take several minutes to pull."
    echo ""
}

stop_stack() {
    header "Stopping AI Stack"
    
    for service in "${SERVICES[@]}"; do
        info "Stopping $service..."
        systemctl --user stop "$service.service" 2>/dev/null || true
    done
    
    success "AI stack stopped"
    echo ""
}

restart_stack() {
    stop_stack
    sleep 2
    start_stack
}

show_logs() {
    local service="${1:-}"
    
    if [[ -n "$service" ]]; then
        header "Logs for $service"
        journalctl --user -xeu "$service.service" -f --no-pager
    else
        header "Following all AI stack logs"
        echo "Press Ctrl+C to stop"
        echo ""
        journalctl --user -xeu "podman-local-ai-*" -f --no-pager
    fi
}

monitor_startup() {
    header "Monitoring AI Stack Startup"
    
    echo "This will monitor the stack startup and show progress."
    echo "Press Ctrl+C to stop monitoring."
    echo ""
    
    local max_wait=600  # 10 minutes
    local start_time
    start_time=$(date +%s)
    
    while true; do
        local current_time
        current_time=$(date +%s)
        local elapsed=$((current_time - start_time))
        
        if [[ $elapsed -gt $max_wait ]]; then
            warn "Timeout reached ($max_wait seconds)"
            break
        fi
        
        clear
        show_banner
        
        echo -e "${CYAN}Elapsed: ${elapsed}s / ${max_wait}s${NC}"
        echo ""
        
        show_status
        show_containers
        
        # Check if all services are active
        local all_active=true
        for service in "${SERVICES[@]}"; do
            local status
            status=$(get_service_status "$service")
            if [[ "$status" != "active" ]]; then
                all_active=false
                break
            fi
        done
        
        if $all_active; then
            echo ""
            success "All services are running!"
            echo ""
            echo "Access points:"
            echo "  • Ollama:     http://localhost:11434"
            echo "  • Qdrant:     http://localhost:6333"
            echo "  • Open WebUI: http://localhost:3001"
            echo "  • MindsDB:    http://localhost:47334"
            echo ""
            break
        fi
        
        sleep 5
    done
}

print_usage() {
    echo "Usage: $(basename "$0") [command]"
    echo ""
    echo "Current Configuration:"
    echo "  Backend: $LLM_BACKEND"
    echo "  Models:  $LLM_MODELS"
    echo ""
    echo "Commands:"
    echo "  start       Start all AI stack services"
    echo "  stop        Stop all AI stack services"
    echo "  restart     Restart all AI stack services"
    echo "  status      Show current status"
    echo "  monitor     Monitor startup progress (interactive)"
    echo ""
    echo "Model Management:"
    echo "  pull        Download configured LLM models"
    echo "  pull <m>    Pull a specific model (e.g., qwen2.5-coder:14b)"
    echo "  models      List available and installed models"
    echo "  recommend   Show recommended models by VRAM tier"
    echo ""
    echo "Logs & Debugging:"
    echo "  logs        Follow logs for all services"
    echo "  logs <s>    Follow logs for specific service"
    echo "  help        Show this help message"
    echo ""
    echo "Examples:"
    echo "  $(basename "$0") start            # Start the AI stack"
    echo "  $(basename "$0") pull             # Pull all configured models"
    echo "  $(basename "$0") pull qwen2.5-coder:7b  # Pull specific model"
    echo "  $(basename "$0") recommend        # Show model recommendations"
    echo "  $(basename "$0") monitor          # Watch startup progress"
    echo ""
}

show_model_recommendations() {
    header "🎯 Recommended Models for Mobile Workstations (December 2025)"
    echo ""
    echo -e "${BOLD}VRAM Tier Recommendations:${NC}"
    echo ""
    echo -e "  ${CYAN}8GB VRAM:${NC}"
    echo "    qwen2.5-coder:7b      - Fast, efficient coding (primary)"
    echo "    deepseek-coder:6.7b   - Good quality, fast inference"
    echo ""
    echo -e "  ${CYAN}16GB VRAM:${NC} (Default)"
    echo "    qwen2.5-coder:14b     - Best overall coding model"
    echo "    deepseek-coder-v2     - Excellent debugging/reasoning"
    echo "    starcoder2:7b         - Fast autocomplete, 80+ languages"
    echo ""
    echo -e "  ${CYAN}32GB VRAM:${NC}"
    echo "    qwen2.5-coder:32b     - Maximum code quality"
    echo "    codestral:22b         - Mistral's coding model"
    echo "    deepseek-coder-v2     - Complex reasoning"
    echo ""
    echo -e "  ${CYAN}48GB+ VRAM:${NC}"
    echo "    qwen2.5-coder:32b     - Best quality"
    echo "    codestral:22b         - Strong completions"
    echo "    llama3.2:70b          - Multimodal, general purpose"
    echo ""
    echo -e "${BOLD}Model Specializations:${NC}"
    echo ""
    echo "  Code Completion:  starcoder2, qwen2.5-coder"
    echo "  Debugging:        deepseek-coder-v2, codestral"
    echo "  Documentation:    llama3.2, qwen2.5-coder"
    echo "  Refactoring:      deepseek-coder-v2, qwen2.5-coder"
    echo ""
    echo -e "${BOLD}Remote LLM Fallback (for complex tasks):${NC}"
    echo ""
    echo "  Claude 4.5 Sonnet  - Best overall for coding (77% SWE-bench)"
    echo "  GPT-4o / o3-mini   - Fast, reliable, good tool calling"
    echo "  Gemini 3 Flash     - Multimodal, real-time"
    echo ""
    echo "Set up remote with: export OPENROUTER_API_KEY=your_key"
    echo ""
}

list_installed_models() {
    header "📦 Installed Models"
    echo ""
    
    if [[ "$LLM_BACKEND" == "ollama" ]]; then
        if curl -s http://localhost:11434/api/tags >/dev/null 2>&1; then
            local models
            models=$(curl -s http://localhost:11434/api/tags | jq -r '.models[].name' 2>/dev/null || echo "")
            if [[ -n "$models" ]]; then
                echo -e "${GREEN}Ollama Models:${NC}"
                echo "$models" | while read -r model; do
                    local size
                    size=$(curl -s http://localhost:11434/api/show -d "{\"name\":\"$model\"}" | jq -r '.size // "unknown"' 2>/dev/null || echo "unknown")
                    printf "  %-30s %s\n" "$model" "$size"
                done
            else
                echo "  No models installed yet."
            fi
        else
            warn "Ollama not running. Start with: $(basename "$0") start"
        fi
    else
        local models_dir="$HOME/.local/share/podman-ai-stack/lemonade-models"
        if [[ -d "$models_dir" ]]; then
            echo -e "${GREEN}Lemonade Models (GGUF files):${NC}"
            find "$models_dir" -name "*.gguf" -exec basename {} \; 2>/dev/null | while read -r model; do
                echo "  $model"
            done || echo "  No models found in $models_dir"
        else
            echo "  Models directory not found: $models_dir"
        fi
    fi
    
    echo ""
    echo -e "Configured models: ${CYAN}$LLM_MODELS${NC}"
    echo ""
}

pull_specific_model() {
    local model="$1"
    
    if [[ "$LLM_BACKEND" == "ollama" ]]; then
        info "Pulling model: $model via Ollama..."
        local container_name="podman-local-ai-ollama"
        if podman exec "$container_name" ollama pull "$model" 2>&1; then
            success "Model $model pulled successfully!"
        else
            error "Failed to pull $model"
            echo "  Make sure the stack is running: $(basename "$0") start"
            return 1
        fi
    else
        warn "For Lemonade backend, download GGUF files manually to:"
        echo "  ~/.local/share/podman-ai-stack/lemonade-models/"
        echo ""
        echo "Recommended sources:"
        echo "  - Hugging Face: https://huggingface.co/models?sort=trending&search=gguf"
        echo "  - TheBloke: https://huggingface.co/TheBloke"
        echo ""
        echo "Example download:"
        echo "  cd ~/.local/share/podman-ai-stack/lemonade-models/"
        echo "  wget https://huggingface.co/Qwen/Qwen2.5-Coder-14B-Instruct-GGUF/resolve/main/qwen2.5-coder-14b-instruct-q4_k_m.gguf"
    fi
}

main() {
    local cmd="${1:-status}"
    shift || true
    
    case "$cmd" in
        start)
            show_banner
            if check_prerequisites; then
                start_stack
                show_status
            fi
            ;;
        stop)
            show_banner
            stop_stack
            show_status
            ;;
        restart)
            show_banner
            if check_prerequisites; then
                restart_stack
                show_status
            fi
            ;;
        status)
            show_banner
            show_status
            show_containers
            ;;
        monitor)
            if check_prerequisites; then
                start_stack
                monitor_startup
            fi
            ;;
        pull)
            show_banner
            if [[ -n "${1:-}" ]]; then
                # Pull specific model
                if check_prerequisites; then
                    pull_specific_model "$1"
                fi
            else
                # Pull all configured models
                if check_prerequisites; then
                    pull_models
                fi
            fi
            ;;
        models)
            show_banner
            list_installed_models
            ;;
        recommend|recommendations)
            show_banner
            show_model_recommendations
            ;;
        logs)
            show_logs "$@"
            ;;
        help|--help|-h)
            show_banner
            print_usage
            ;;
        *)
            error "Unknown command: $cmd"
            print_usage
            exit 1
            ;;
    esac
}

main "$@"
