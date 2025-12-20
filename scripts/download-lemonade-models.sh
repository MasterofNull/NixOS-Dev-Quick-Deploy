#!/usr/bin/env bash
# ============================================================================
# Automated GGUF Model Download Script for Lemonade AI Server
# ============================================================================
# Downloads recommended GGUF models for Lemonade AI inference stack
# Supports both manual and automated deployment scenarios
# ============================================================================

set -euo pipefail

# ============================================================================
# Configuration
# ============================================================================

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(cd "${SCRIPT_DIR}/.." && pwd)"

# Model storage directory (user-level)
MODEL_DIR="${MODEL_DIR:-${HOME}/.local/share/nixos-ai-stack/lemonade-models}"
CACHE_DIR="${HF_HOME:-${HOME}/.cache/huggingface}"

# Logging
LOG_FILE="${MODEL_DIR}/download.log"
TIMESTAMP=$(date +%Y%m%d_%H%M%S)

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# ============================================================================
# Recommended GGUF Models for Lemonade Stack
# ============================================================================
# Based on ai-stack/compose/docker-compose.yml configuration
# All models use Q4_K_M quantization (4-bit) for optimal CPU performance

declare -A MODELS=(
    # General Purpose Model (lemonade:8000)
    ["qwen3-4b"]="unsloth/Qwen3-4B-Instruct-2507-GGUF:Qwen3-4B-Instruct-2507-Q4_K_M.gguf"

    # Code Generation Model (lemonade-coder:8001)
    ["qwen-coder"]="Qwen/Qwen2.5-Coder-7B-Instruct-GGUF:qwen2.5-coder-7b-instruct-q4_k_m.gguf"

    # Code Analysis Model (lemonade-deepseek:8003)
    ["deepseek"]="TheBloke/deepseek-coder-6.7B-instruct-GGUF:deepseek-coder-6.7b-instruct.Q4_K_M.gguf"
)

# Model sizes (approximate)
declare -A MODEL_SIZES=(
    ["qwen3-4b"]="2.4 GB"
    ["qwen-coder"]="4.3 GB"
    ["deepseek"]="3.8 GB"
)

# Model descriptions
declare -A MODEL_DESCRIPTIONS=(
    ["qwen3-4b"]="General reasoning and task execution"
    ["qwen-coder"]="Advanced code generation and completion"
    ["deepseek"]="Code analysis and understanding"
)

# ============================================================================
# Helper Functions
# ============================================================================

log() {
    local level=$1
    shift
    local message="$*"
    local timestamp=$(date '+%Y-%m-%d %H:%M:%S')
    echo -e "${timestamp} [${level}] ${message}" | tee -a "${LOG_FILE}"
}

info() {
    echo -e "${BLUE}ℹ${NC} $*"
    log "INFO" "$*"
}

success() {
    echo -e "${GREEN}✓${NC} $*"
    log "SUCCESS" "$*"
}

warning() {
    echo -e "${YELLOW}⚠${NC} $*"
    log "WARNING" "$*"
}

error() {
    echo -e "${RED}✗${NC} $*"
    log "ERROR" "$*"
}

# ============================================================================
# Check Prerequisites
# ============================================================================

check_prerequisites() {
    info "Checking prerequisites..."

    # Check for Python 3
    if ! command -v python3 &> /dev/null; then
        error "Python 3 is required but not found"
        return 1
    fi

    # Check for huggingface-cli or install huggingface_hub
    if ! command -v huggingface-cli &> /dev/null; then
        warning "huggingface-cli not found, checking for Python module..."
        if ! python3 -c "import huggingface_hub" 2>/dev/null; then
            info "Installing huggingface_hub..."
            pip3 install --user huggingface_hub
        fi
    fi

    success "Prerequisites satisfied"
}

# ============================================================================
# Create Directory Structure
# ============================================================================

setup_directories() {
    info "Setting up directory structure..."

    mkdir -p "${MODEL_DIR}"
    mkdir -p "${CACHE_DIR}"
    mkdir -p "$(dirname "${LOG_FILE}")"

    success "Directories created:"
    echo "  - Models: ${MODEL_DIR}"
    echo "  - Cache:  ${CACHE_DIR}"
    echo "  - Log:    ${LOG_FILE}"
}

# ============================================================================
# Check if Model Exists
# ============================================================================

model_exists() {
    local repo_id=$1
    local filename=$2

    # Check in cache directory
    if find "${CACHE_DIR}" -name "${filename}" 2>/dev/null | grep -q .; then
        return 0
    fi

    # Check in model directory
    if [ -f "${MODEL_DIR}/${filename}" ]; then
        return 0
    fi

    return 1
}

# ============================================================================
# Download Single Model
# ============================================================================

download_model() {
    local model_key=$1
    local model_spec="${MODELS[$model_key]}"
    local repo_id="${model_spec%%:*}"
    local filename="${model_spec##*:}"
    local size="${MODEL_SIZES[$model_key]}"
    local description="${MODEL_DESCRIPTIONS[$model_key]}"

    echo ""
    echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
    info "Model: ${model_key}"
    echo "  Repository: ${repo_id}"
    echo "  Filename:   ${filename}"
    echo "  Size:       ${size}"
    echo "  Purpose:    ${description}"
    echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"

    # Check if already downloaded
    if model_exists "${repo_id}" "${filename}"; then
        success "Model already exists (cached)"
        return 0
    fi

    info "Downloading model (this may take a while)..."

    # Download using Python API (most reliable method)
    python3 << EOF
from huggingface_hub import hf_hub_download
import sys

try:
    path = hf_hub_download(
        repo_id="${repo_id}",
        filename="${filename}",
        cache_dir="${CACHE_DIR}",
        resume_download=True
    )
    print(f"Downloaded to: {path}")
    sys.exit(0)
except Exception as e:
    print(f"Error downloading model: {e}", file=sys.stderr)
    sys.exit(1)
EOF

    if [ $? -eq 0 ]; then
        success "Model downloaded successfully"

        # Create symlink in model directory for easier access
        local cache_file=$(find "${CACHE_DIR}" -name "${filename}" | head -1)
        if [ -n "${cache_file}" ] && [ -f "${cache_file}" ]; then
            ln -sf "${cache_file}" "${MODEL_DIR}/${filename}"
            info "Symlink created: ${MODEL_DIR}/${filename}"
        fi

        return 0
    else
        error "Failed to download model"
        return 1
    fi
}

# ============================================================================
# Download All Models
# ============================================================================

download_all_models() {
    local failed_models=()

    info "Starting download of all recommended models..."
    echo "Total models: ${#MODELS[@]}"
    echo ""

    for model_key in "${!MODELS[@]}"; do
        if ! download_model "${model_key}"; then
            failed_models+=("${model_key}")
        fi
    done

    echo ""
    echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
    if [ ${#failed_models[@]} -eq 0 ]; then
        success "All models downloaded successfully!"
    else
        warning "Some models failed to download:"
        for model in "${failed_models[@]}"; do
            echo "  - ${model}"
        done
        return 1
    fi
    echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
}

# ============================================================================
# List Downloaded Models
# ============================================================================

list_models() {
    info "Downloaded models:"
    echo ""

    for model_key in "${!MODELS[@]}"; do
        local model_spec="${MODELS[$model_key]}"
        local repo_id="${model_spec%%:*}"
        local filename="${model_spec##*:}"

        if model_exists "${repo_id}" "${filename}"; then
            local cache_file=$(find "${CACHE_DIR}" -name "${filename}" 2>/dev/null | head -1)
            if [ -n "${cache_file}" ]; then
                local file_size=$(du -h "${cache_file}" | cut -f1)
                echo -e "${GREEN}✓${NC} ${model_key} (${file_size})"
                echo "    ${cache_file}"
            fi
        else
            echo -e "${RED}✗${NC} ${model_key} (not downloaded)"
        fi
    done
}

# ============================================================================
# Clean Old Models
# ============================================================================

clean_models() {
    warning "This will remove all downloaded GGUF models"
    read -p "Are you sure? (yes/no): " confirm

    if [ "${confirm}" = "yes" ]; then
        info "Cleaning model cache..."
        rm -rf "${MODEL_DIR}"/*.gguf
        success "Models cleaned"
    else
        info "Cleanup cancelled"
    fi
}

# ============================================================================
# Interactive Menu
# ============================================================================

show_menu() {
    echo ""
    echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
    echo "  Lemonade AI - GGUF Model Download Manager"
    echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
    echo ""
    echo "Available Models:"
    echo ""

    local idx=1
    for model_key in "${!MODELS[@]}"; do
        local size="${MODEL_SIZES[$model_key]}"
        local desc="${MODEL_DESCRIPTIONS[$model_key]}"
        local status="✗ Not downloaded"

        local model_spec="${MODELS[$model_key]}"
        local repo_id="${model_spec%%:*}"
        local filename="${model_spec##*:}"

        if model_exists "${repo_id}" "${filename}"; then
            status="✓ Downloaded"
        fi

        echo "  ${idx}. ${model_key} (${size}) - ${desc}"
        echo "     Status: ${status}"
        echo ""
        ((idx++))
    done

    echo "Options:"
    echo "  a) Download all models"
    echo "  l) List downloaded models"
    echo "  c) Clean model cache"
    echo "  q) Quit"
    echo ""
}

interactive_mode() {
    while true; do
        show_menu
        read -p "Select option: " choice

        case "${choice}" in
            a)
                download_all_models
                ;;
            l)
                list_models
                ;;
            c)
                clean_models
                ;;
            [1-3])
                local idx=1
                for model_key in "${!MODELS[@]}"; do
                    if [ ${idx} -eq ${choice} ]; then
                        download_model "${model_key}"
                        break
                    fi
                    ((idx++))
                done
                ;;
            q)
                info "Exiting..."
                exit 0
                ;;
            *)
                error "Invalid option"
                ;;
        esac

        echo ""
        read -p "Press Enter to continue..."
    done
}

# ============================================================================
# Main Function
# ============================================================================

main() {
    echo ""
    echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
    echo "  Lemonade AI - GGUF Model Download Script"
    echo "  Automated model management for NixOS AI Stack"
    echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
    echo ""

    check_prerequisites
    setup_directories

    # Parse command line arguments
    case "${1:-interactive}" in
        --all|-a)
            download_all_models
            ;;
        --list|-l)
            list_models
            ;;
        --clean|-c)
            clean_models
            ;;
        --help|-h)
            echo "Usage: $0 [OPTIONS]"
            echo ""
            echo "Options:"
            echo "  -a, --all     Download all recommended models"
            echo "  -l, --list    List downloaded models"
            echo "  -c, --clean   Clean model cache"
            echo "  -h, --help    Show this help message"
            echo ""
            echo "Interactive mode (default):"
            echo "  $0"
            ;;
        interactive|*)
            interactive_mode
            ;;
    esac
}

# ============================================================================
# Script Entry Point
# ============================================================================

main "$@"
