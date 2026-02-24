#!/usr/bin/env bash
# ---------------------------------------------------------------------------
# ai-model-setup.sh — Download and place the AI model for llama.cpp.
#
# Usage:
#   sudo scripts/ai-model-setup.sh [--model-url URL] [--model-name NAME]
#
# Defaults:
#   Model: Qwen3-4B-Instruct-2507-Q4_K_M.gguf
#   Source: Hugging Face (qwen model repository)
#   Destination: /var/lib/llama-cpp/models/
#
# After placing the model, starts llama-cpp.service automatically.
# ---------------------------------------------------------------------------
set -euo pipefail

# ── Configuration ────────────────────────────────────────────────────────────
MODEL_DIR="/var/lib/llama-cpp/models"
MODEL_NAME="${MODEL_NAME:-Qwen3-4B-Instruct-2507-Q4_K_M.gguf}"
MODEL_DEST="${MODEL_DIR}/${MODEL_NAME}"

# Primary: Hugging Face GGUF repo for Qwen3 4B
HF_REPO="${HF_REPO:-unsloth/Qwen3-4B-Instruct-2507-GGUF}"
HF_FILE="${HF_FILE:-${MODEL_NAME}}"

# Alternative: direct URL override
MODEL_URL="${MODEL_URL:-}"

# ── Helpers ──────────────────────────────────────────────────────────────────
info()  { printf '\033[0;32m[ai-model-setup] %s\033[0m\n' "$*"; }
warn()  { printf '\033[0;33m[ai-model-setup] WARN: %s\033[0m\n' "$*" >&2; }
error() { printf '\033[0;31m[ai-model-setup] ERROR: %s\033[0m\n' "$*" >&2; exit 1; }

require_root() {
    [[ $EUID -eq 0 ]] || error "This script must be run as root (use sudo)."
}

check_deps() {
    local missing=()
    for cmd in curl; do
        command -v "$cmd" >/dev/null 2>&1 || missing+=("$cmd")
    done
    [[ ${#missing[@]} -eq 0 ]] || error "Missing required commands: ${missing[*]}"
}

# ── Argument parsing ─────────────────────────────────────────────────────────
while [[ $# -gt 0 ]]; do
    case "$1" in
        --model-url)   MODEL_URL="$2";   shift 2 ;;
        --model-name)  MODEL_NAME="$2";  MODEL_DEST="${MODEL_DIR}/${MODEL_NAME}"; shift 2 ;;
        --model-dir)   MODEL_DIR="$2";   MODEL_DEST="${MODEL_DIR}/${MODEL_NAME}"; shift 2 ;;
        --start-service) START_SERVICE=1; shift ;;
        --help|-h)
            cat <<'HELP'
Usage: sudo scripts/ai-model-setup.sh [OPTIONS]

Options:
  --model-url URL      Direct download URL for the GGUF file
  --model-name NAME    Filename to save as (default: Qwen3-4B-Instruct-2507-Q4_K_M.gguf)
  --model-dir DIR      Destination directory (default: /var/lib/llama-cpp/models)
  --start-service      Start llama-cpp.service after download completes
  --help               Show this message

Environment variables:
  HF_REPO              Hugging Face repo (default: Qwen/Qwen3-4B-GGUF)
  HF_FILE              Filename in HF repo (default: same as --model-name)
  MODEL_URL            Direct download URL (overrides HF_REPO lookup)
HELP
            exit 0 ;;
        *) error "Unknown option: $1" ;;
    esac
done

START_SERVICE="${START_SERVICE:-0}"

# ── Main ─────────────────────────────────────────────────────────────────────
require_root
check_deps

info "AI Model Setup"
info "  Destination: ${MODEL_DEST}"

# Create model directory with correct ownership.
install -d -m 0750 -o llama -g llama "${MODEL_DIR}"

# Check if model already exists.
if [[ -f "${MODEL_DEST}" ]]; then
    local_size=$(stat -c%s "${MODEL_DEST}" 2>/dev/null || echo 0)
    info "Model already present: ${MODEL_DEST} (${local_size} bytes)"
    info "  Remove it to re-download: rm '${MODEL_DEST}'"

    if [[ "${START_SERVICE}" == "1" ]] && command -v systemctl >/dev/null 2>&1; then
        info "Starting llama-cpp.service..."
        systemctl start llama-cpp.service && info "llama-cpp.service started." || warn "Failed to start llama-cpp.service"
    fi
    exit 0
fi

# Resolve download URL.
if [[ -z "${MODEL_URL}" ]]; then
    # Build Hugging Face URL (uses the public resolve endpoint).
    MODEL_URL="https://huggingface.co/${HF_REPO}/resolve/main/${HF_FILE}"
    info "Downloading from Hugging Face: ${HF_REPO}/${HF_FILE}"
else
    info "Downloading from: ${MODEL_URL}"
fi

# Download to a temp file first, then atomic-move into place.
TMP_FILE=$(mktemp "${MODEL_DIR}/.download-XXXXXX")
trap 'rm -f "${TMP_FILE}"' EXIT

info "Starting download (this may take several minutes)..."
if curl \
    --location \
    --retry 5 \
    --retry-delay 5 \
    --retry-connrefused \
    --connect-timeout 30 \
    --max-time 3600 \
    --progress-bar \
    --output "${TMP_FILE}" \
    "${MODEL_URL}"; then
    # Verify the download produced a non-empty file.
    dl_size=$(stat -c%s "${TMP_FILE}" 2>/dev/null || echo 0)
    if [[ "${dl_size}" -lt 1048576 ]]; then
        # Less than 1 MB — likely an error page, not a model.
        error "Download appears corrupt (${dl_size} bytes). Check the URL and try again."
    fi

    # Move into final position and fix ownership.
    mv "${TMP_FILE}" "${MODEL_DEST}"
    chown llama:llama "${MODEL_DEST}"
    chmod 0640 "${MODEL_DEST}"
    trap - EXIT

    info "Model saved: ${MODEL_DEST} ($(stat -c%s "${MODEL_DEST}") bytes)"
else
    error "Download failed. Check network connectivity and the model URL."
fi

# Optionally start the service.
if [[ "${START_SERVICE}" == "1" ]] && command -v systemctl >/dev/null 2>&1; then
    info "Starting llama-cpp.service..."
    systemctl start llama-cpp.service && info "llama-cpp.service started." || warn "Failed to start llama-cpp.service — check: journalctl -u llama-cpp"
fi

info ""
info "Model setup complete. To start the inference server:"
info "  sudo systemctl start llama-cpp.service"
info "  sudo systemctl status llama-cpp.service"
info ""
info "To verify the API is running:"
info "  curl http://127.0.0.1:8080/v1/models"
