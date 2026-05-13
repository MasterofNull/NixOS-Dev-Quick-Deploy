#!/usr/bin/env bash
#
# Deploy CLI - Model Download Optimization
# AI model caching and prefetching strategy
#
# Usage:
#   source optimize-model-downloads.sh
#   prefetch_models
#   check_models_cached
#   optimize_model_downloads

set -euo pipefail

# ============================================================================
# Configuration
# ============================================================================

LLAMA_MODEL_PATH="${LLAMA_MODEL_PATH:-/var/lib/llama-cpp/models/llama.gguf}"
LLAMA_MODEL_BACKUP="${LLAMA_MODEL_PATH}.backup"
EMBED_MODEL_PATH="${EMBED_MODEL_PATH:-/var/lib/llama-cpp/models/embeddings.gguf}"
EMBED_MODEL_BACKUP="${EMBED_MODEL_PATH}.backup"

# Model download metadata
declare -gA MODEL_SOURCES
declare -gA MODEL_SIZES

# ============================================================================
# Model Path Management
# ============================================================================

setup_model_directories() {
  local llama_dir
  local embed_dir

  llama_dir="$(dirname "$LLAMA_MODEL_PATH")"
  embed_dir="$(dirname "$EMBED_MODEL_PATH")"

  log_debug "Setting up model directories..."

  for dir in "$llama_dir" "$embed_dir"; do
    if [[ ! -d "$dir" ]]; then
      mkdir -p "$dir" 2>/dev/null || {
        log_warn "Could not create model directory: $dir (may not have permissions)"
      }
    fi
  done

  log_debug "Model directories ready"
}

get_model_size() {
  local model_path="$1"

  if [[ -f "$model_path" ]]; then
    du -h "$model_path" | awk '{print $1}'
  else
    echo "not-cached"
  fi
}

# ============================================================================
# Model Prefetching
# ============================================================================

prefetch_models() {
  log_info "Checking AI model cache..."

  setup_model_directories

  local llama_status
  local embed_status

  # Check llama model
  if [[ -f "$LLAMA_MODEL_PATH" ]]; then
    llama_status="cached"
    local size
    size="$(get_model_size "$LLAMA_MODEL_PATH")"
    log_success "  ✓ Llama model cached ($size)"
  else
    llama_status="missing"
    log_warn "  ✗ Llama model not cached"

    # Try to fetch
    log_info "    Downloading llama model (this may take 2-5 minutes)..."
    if fetch_llama_model; then
      log_success "    ✓ Llama model downloaded"
      llama_status="cached"
    else
      log_warn "    ⚠ Could not download llama model (will retry during deploy)"
      llama_status="download-failed"
    fi
  fi

  # Check embedding model
  if [[ -f "$EMBED_MODEL_PATH" ]]; then
    embed_status="cached"
    local size
    size="$(get_model_size "$EMBED_MODEL_PATH")"
    log_success "  ✓ Embedding model cached ($size)"
  else
    embed_status="missing"
    log_warn "  ✗ Embedding model not cached"

    # Try to fetch
    log_info "    Downloading embedding model (this may take 2-5 minutes)..."
    if fetch_embed_model; then
      log_success "    ✓ Embedding model downloaded"
      embed_status="cached"
    else
      log_warn "    ⚠ Could not download embedding model (will retry during deploy)"
      embed_status="download-failed"
    fi
  fi

  # Summary
  if [[ "$llama_status" == "cached" ]] && [[ "$embed_status" == "cached" ]]; then
    log_success "All AI models are cached and ready"
    return 0
  else
    log_warn "Some models not yet cached (will download during deployment)"
    return 1
  fi
}

fetch_llama_model() {
  # Check if systemd service exists
  if systemctl is-enabled llama-cpp-model-fetch.service 2>/dev/null; then
    log_debug "Starting llama-cpp-model-fetch service..."

    # Run the fetch service
    if systemctl start llama-cpp-model-fetch.service 2>/dev/null && \
       systemctl wait llama-cpp-model-fetch.service 2>/dev/null; then
      log_success "Llama model fetch completed"
      return 0
    else
      log_warn "Llama model fetch service failed"
      return 1
    fi
  else
    log_debug "llama-cpp-model-fetch service not found"
    return 1
  fi
}

fetch_embed_model() {
  # Check if systemd service exists
  if systemctl is-enabled llama-cpp-embed-model-fetch.service 2>/dev/null; then
    log_debug "Starting llama-cpp-embed-model-fetch service..."

    # Run the fetch service
    if systemctl start llama-cpp-embed-model-fetch.service 2>/dev/null && \
       systemctl wait llama-cpp-embed-model-fetch.service 2>/dev/null; then
      log_success "Embedding model fetch completed"
      return 0
    else
      log_warn "Embedding model fetch service failed"
      return 1
    fi
  else
    log_debug "llama-cpp-embed-model-fetch service not found"
    return 1
  fi
}

# ============================================================================
# Model Verification
# ============================================================================

check_models_cached() {
  local llama_cached=0
  local embed_cached=0

  if [[ -f "$LLAMA_MODEL_PATH" ]]; then
    llama_cached=1
  fi

  if [[ -f "$EMBED_MODEL_PATH" ]]; then
    embed_cached=1
  fi

  if [[ $llama_cached -eq 1 ]] && [[ $embed_cached -eq 1 ]]; then
    return 0  # All models cached
  else
    return 1  # Some models missing
  fi
}

verify_model_integrity() {
  log_info "Verifying model integrity..."

  local all_valid=1

  # Check llama model
  if [[ -f "$LLAMA_MODEL_PATH" ]]; then
    # Verify it's a valid GGUF file
    if file "$LLAMA_MODEL_PATH" 2>/dev/null | grep -q "data"; then
      log_success "  ✓ Llama model integrity verified"
    else
      log_warn "  ⚠ Llama model may be corrupted"
      all_valid=0
    fi
  fi

  # Check embedding model
  if [[ -f "$EMBED_MODEL_PATH" ]]; then
    if file "$EMBED_MODEL_PATH" 2>/dev/null | grep -q "data"; then
      log_success "  ✓ Embedding model integrity verified"
    else
      log_warn "  ⚠ Embedding model may be corrupted"
      all_valid=0
    fi
  fi

  return $(( 1 - all_valid ))
}

# ============================================================================
# Model Cache Management
# ============================================================================

backup_models() {
  log_info "Backing up model files..."

  if [[ -f "$LLAMA_MODEL_PATH" ]]; then
    cp "$LLAMA_MODEL_PATH" "$LLAMA_MODEL_BACKUP" 2>/dev/null && \
      log_success "  ✓ Backed up llama model"
  fi

  if [[ -f "$EMBED_MODEL_PATH" ]]; then
    cp "$EMBED_MODEL_PATH" "$EMBED_MODEL_BACKUP" 2>/dev/null && \
      log_success "  ✓ Backed up embedding model"
  fi
}

restore_models() {
  log_info "Restoring models from backup..."

  if [[ -f "$LLAMA_MODEL_BACKUP" ]]; then
    cp "$LLAMA_MODEL_BACKUP" "$LLAMA_MODEL_PATH" 2>/dev/null && \
      log_success "  ✓ Restored llama model from backup"
  fi

  if [[ -f "$EMBED_MODEL_BACKUP" ]]; then
    cp "$EMBED_MODEL_BACKUP" "$EMBED_MODEL_PATH" 2>/dev/null && \
      log_success "  ✓ Restored embedding model from backup"
  fi
}

clear_model_cache() {
  log_warn "Clearing model cache..."

  rm -f "$LLAMA_MODEL_PATH" "$EMBED_MODEL_PATH"
  log_success "Model cache cleared (models will be re-downloaded)"
}

model_cache_size() {
  local total_size=0

  if [[ -f "$LLAMA_MODEL_PATH" ]]; then
    total_size=$(( total_size + $(stat -f%z "$LLAMA_MODEL_PATH" 2>/dev/null || stat -c%s "$LLAMA_MODEL_PATH" 2>/dev/null || echo 0) ))
  fi

  if [[ -f "$EMBED_MODEL_PATH" ]]; then
    total_size=$(( total_size + $(stat -f%z "$EMBED_MODEL_PATH" 2>/dev/null || stat -c%s "$EMBED_MODEL_PATH" 2>/dev/null || echo 0) ))
  fi

  # Convert to human readable
  if (( total_size > 1073741824 )); then
    echo "$(( total_size / 1073741824 ))GB"
  elif (( total_size > 1048576 )); then
    echo "$(( total_size / 1048576 ))MB"
  else
    echo "$(( total_size / 1024 ))KB"
  fi
}

# ============================================================================
# Model Download Optimization
# ============================================================================

optimize_model_downloads() {
  log_info "Optimizing model downloads..."

  local llama_ok=0
  local embed_ok=0

  # Check and cache llama model
  if [[ -f "$LLAMA_MODEL_PATH" ]]; then
    log_debug "Llama model already cached - skipping download"
    llama_ok=1
  else
    log_info "Llama model not cached - prefetching..."
    if fetch_llama_model; then
      llama_ok=1
    fi
  fi

  # Check and cache embedding model
  if [[ -f "$EMBED_MODEL_PATH" ]]; then
    log_debug "Embedding model already cached - skipping download"
    embed_ok=1
  else
    log_info "Embedding model not cached - prefetching..."
    if fetch_embed_model; then
      embed_ok=1
    fi
  fi

  # Report results
  if [[ $llama_ok -eq 1 ]] && [[ $embed_ok -eq 1 ]]; then
    log_success "All models optimized"
    return 0
  else
    log_warn "Some models could not be optimized (will download live)"
    return 1
  fi
}

# ============================================================================
# Deployment Integration
# ============================================================================

should_skip_model_downloads() {
  # Return 0 if models are cached and valid, 1 if downloads needed
  check_models_cached && verify_model_integrity
}

get_expected_download_time() {
  # Estimate download time based on cache status
  local missing=0

  if ! [[ -f "$LLAMA_MODEL_PATH" ]]; then
    missing=$(( missing + 1 ))
  fi

  if ! [[ -f "$EMBED_MODEL_PATH" ]]; then
    missing=$(( missing + 1 ))
  fi

  case $missing in
    0)
      echo "0-5s (cached)"
      ;;
    1)
      echo "30-120s (1 model download)"
      ;;
    2)
      echo "60-240s (2 model downloads)"
      ;;
  esac
}

# ============================================================================
# Export Functions
# ============================================================================

export -f setup_model_directories
export -f get_model_size
export -f prefetch_models
export -f fetch_llama_model
export -f fetch_embed_model
export -f check_models_cached
export -f verify_model_integrity
export -f backup_models
export -f restore_models
export -f clear_model_cache
export -f model_cache_size
export -f optimize_model_downloads
export -f should_skip_model_downloads
export -f get_expected_download_time
