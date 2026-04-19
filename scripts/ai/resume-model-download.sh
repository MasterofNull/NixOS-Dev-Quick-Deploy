#!/usr/bin/env bash
# Resume or restart Qwen 3.6 model download with better error handling

set -euo pipefail

MODEL_NAME="Qwen3.6-35B-A3B-UD-Q4_K_M"
MODEL_REPO="unsloth/Qwen3.6-35B-A3B-GGUF"
MODEL_FILE="${MODEL_NAME}.gguf"
CACHE_DIR="${HOME}/.cache/huggingface/hub"
TARGET_FILE="${CACHE_DIR}/models--${MODEL_REPO/\//_}/snapshots/main/${MODEL_FILE}"

echo "=== Qwen 3.6 Model Download Resume Script ==="
echo ""
echo "Model: ${MODEL_NAME}"
echo "Target: ${TARGET_FILE}"
echo ""

# Create cache directory
mkdir -p "$(dirname "${TARGET_FILE}")"

# Check if partial download exists
if [[ -f "${TARGET_FILE}" ]]; then
    SIZE=$(du -h "${TARGET_FILE}" | cut -f1)
    echo "Found partial download: ${SIZE}"
    echo "Will attempt to resume..."
    RESUME="-C -"
else
    echo "No partial download found"
    echo "Starting fresh download..."
    RESUME=""
fi

# Download with resume support
echo ""
echo "Downloading (this may take 1-2 hours)..."
echo "Press Ctrl+C to pause (can resume later)"
echo ""

# Use curl with resume, progress bar, and better error handling
if curl ${RESUME} -L --progress-bar --fail --retry 5 --retry-delay 10 \
    -o "${TARGET_FILE}" \
    "https://huggingface.co/unsloth/Qwen3.6-35B-A3B-GGUF/resolve/main/${MODEL_FILE}"; then

    echo ""
    echo "✓ Download complete!"
    echo ""

    # Verify file size (should be ~20.61GB)
    ACTUAL_SIZE=$(stat -c%s "${TARGET_FILE}")
    EXPECTED_SIZE=22000000000  # ~20.61GB in bytes

    if (( ACTUAL_SIZE > EXPECTED_SIZE - 100000000 )); then
        echo "✓ File size looks correct: $(du -h "${TARGET_FILE}" | cut -f1)"
        echo ""
        echo "Next steps:"
        echo "1. Update facts.nix: llamaCpp.activeModel = \"qwen3.6-35b\";"
        echo "2. Run: sudo nixos-rebuild switch --flake .#hyperd"
        echo "3. Restart AI services: sudo systemctl restart ai-llama-cpp"
        exit 0
    else
        echo "⚠ Warning: File size seems incorrect"
        echo "   Expected: ~20.61GB"
        echo "   Got: $(du -h "${TARGET_FILE}" | cut -f1)"
        echo ""
        echo "The download may be incomplete. Try running this script again."
        exit 1
    fi
else
    EXIT_CODE=$?
    echo ""
    echo "⚠ Download failed or interrupted (exit code: ${EXIT_CODE})"
    echo ""
    echo "You can resume by running this script again:"
    echo "  bash scripts/ai/resume-model-download.sh"
    exit ${EXIT_CODE}
fi
