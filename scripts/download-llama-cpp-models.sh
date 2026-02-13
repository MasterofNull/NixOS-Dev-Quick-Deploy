#!/usr/bin/env bash
# ============================================================================
# Automated GGUF Model Download Script for llama.cpp
# ============================================================================
# Downloads recommended GGUF models for the local llama.cpp inference stack
# Supports both manual and automated deployment scenarios
# ============================================================================

set -euo pipefail

# ============================================================================
# Configuration
# ============================================================================

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(cd "${SCRIPT_DIR}/.." && pwd)"

# Model storage directory (user-level)
# Standardized to nixos-ai-stack (matches k8s AI_STACK_DATA)
MODEL_DIR="${MODEL_DIR:-${HOME}/.local/share/nixos-ai-stack/llama-cpp-models}"
CACHE_DIR="${HF_HOME:-${HOME}/.cache/huggingface}"
HUGGINGFACE_TOKEN_FILE_DEFAULT="${HUGGINGFACE_TOKEN_FILE:-${HOME}/.cache/nixos-quick-deploy/preferences/huggingface-token.env}"

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
# Recommended GGUF Models for llama.cpp Stack
# ============================================================================
# Based on ai-stack/kubernetes configuration
# All models use Q4_K_M quantization (4-bit) for optimal CPU performance

declare -A MODELS=(
    # General Purpose Model (llama-cpp:8080)
    ["qwen3-4b"]="unsloth/Qwen3-4B-Instruct-2507-GGUF:Qwen3-4B-Instruct-2507-Q4_K_M.gguf"

    # Code Generation Model (optional secondary endpoint)
    ["qwen-coder"]="Qwen/Qwen2.5-Coder-7B-Instruct-GGUF:qwen2.5-coder-7b-instruct-q4_k_m.gguf"

    # Code Analysis Model (optional secondary endpoint)
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
    mkdir -p "$(dirname "${LOG_FILE}")" >/dev/null 2>&1 || true
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
# Hugging Face Token (optional but recommended)
# ============================================================================

ensure_huggingface_token() {
    if [[ -n "${HUGGINGFACEHUB_API_TOKEN:-}" ]]; then
        return 0
    fi

    local token_file="${HUGGINGFACE_TOKEN_FILE_DEFAULT}"
    if [[ -r "$token_file" ]]; then
        local token
        token=$(awk -F'=' '/^HUGGINGFACEHUB_API_TOKEN=/{print $2}' "$token_file" 2>/dev/null | tail -n1 | tr -d '\r')
        if [[ -n "$token" ]]; then
            export HUGGINGFACEHUB_API_TOKEN="$token"
            success "Loaded Hugging Face token from ${token_file}"
            return 0
        fi
    fi

    warning "Hugging Face token not set; public models will download, but gated repositories may fail."
    return 0
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
    info "Large models (2-4GB) may take 10-30 minutes on slower connections"

    # Download using Python API (most reliable method) with timeout
    timeout 1800 python3 << EOF
from huggingface_hub import hf_hub_download
import sys
import os

# Set longer timeout for large model downloads (30 minutes)
os.environ['HF_HUB_DOWNLOAD_TIMEOUT'] = '1800'

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

download_models_by_keys() {
    local keys_csv="$1"
    local failed_models=()
    IFS=',' read -ra keys <<< "$keys_csv"

    for key in "${keys[@]}"; do
        key="$(echo "$key" | xargs)"
        if [[ -z "$key" ]]; then
            continue
        fi
        if [[ -z "${MODELS[$key]:-}" ]]; then
            warning "Unknown model key: ${key}"
            failed_models+=("$key")
            continue
        fi
        if ! download_model "$key"; then
            failed_models+=("$key")
        fi
    done

    if [ ${#failed_models[@]} -gt 0 ]; then
        warning "Some models failed to download:"
        for model in "${failed_models[@]}"; do
            echo "  - ${model}"
        done
        return 1
    fi

    success "Requested models downloaded successfully"
    return 0
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
    echo "  llama.cpp AI - GGUF Model Download Manager"
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
    echo "  llama.cpp AI - GGUF Model Download Script"
    echo "  Automated model management for NixOS AI Stack"
    echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
    echo ""

    check_prerequisites
    setup_directories
    ensure_huggingface_token

    # Parse command line arguments
    case "${1:-interactive}" in
        --all|-a)
            download_all_models
            ;;
        --model|-m)
            if [[ -z "${2:-}" ]]; then
                error "Missing model key. Use --list to see available keys."
                exit 1
            fi
            download_models_by_keys "$2"
            ;;
        --models)
            if [[ -z "${2:-}" ]]; then
                error "Missing model key list. Use --list to see available keys."
                exit 1
            fi
            download_models_by_keys "$2"
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
            echo "  -m, --model   Download a specific model key (e.g., qwen-coder)"
            echo "  --models      Download a comma-separated list of keys"
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
