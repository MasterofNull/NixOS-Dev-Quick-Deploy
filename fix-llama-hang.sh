#!/usr/bin/env bash
#
# Fix llama-server hanging and Continue extension issues
# Run this script to apply all fixes
#

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$SCRIPT_DIR"

echo "========================================"
echo "LLama-Server Hang Fix - Quick Deploy"
echo "========================================"
echo ""

# Step 1: Restart llama-cpp to clear stuck slots
echo "[1/4] Restarting llama-cpp service to clear stuck slots..."
if sudo systemctl restart llama-cpp.service 2>&1; then
    echo "  ✓ llama-cpp restarted"
else
    echo "  ✗ Failed to restart llama-cpp (needs sudo password)"
    echo "  → Please run: sudo systemctl restart llama-cpp.service"
    exit 1
fi

# Step 2: Wait for service to be ready
echo ""
echo "[2/4] Waiting for llama-cpp to be ready..."
for i in {1..30}; do
    if curl -sf http://localhost:8080/health >/dev/null 2>&1; then
        echo "  ✓ llama-cpp is ready (${i}s)"
        break
    fi
    if [ $i -eq 30 ]; then
        echo "  ✗ llama-cpp failed to start"
        exit 1
    fi
    sleep 1
done

# Step 3: Test chat completions
echo ""
echo "[3/4] Testing chat completions endpoint..."
RESPONSE=$(curl -s -X POST http://localhost:8080/v1/chat/completions \
  -H "Content-Type: application/json" \
  -d '{"model": "Qwen3-4B-Instruct", "messages": [{"role": "user", "content": "Hi"}], "max_tokens": 10}' \
  --max-time 30)

if echo "$RESPONSE" | grep -q "choices"; then
    echo "  ✓ Chat completions working"
else
    echo "  ✗ Chat completions failed"
    echo "  Response: $RESPONSE"
    exit 1
fi

# Step 4: Restart AIDB to pick up embedding fix
echo ""
echo "[4/4] Restarting AIDB service..."
if sudo systemctl restart ai-aidb.service 2>&1; then
    echo "  ✓ AIDB restarted"
else
    echo "  ⚠ AIDB restart skipped (may need manual restart)"
fi

echo ""
echo "========================================"
echo "✅ All fixes applied successfully!"
echo "========================================"
echo ""
echo "Next steps:"
echo "1. Test Continue extension in VSCodium"
echo "2. Deploy NixOS configuration to make changes permanent:"
echo "   sudo nixos-rebuild switch --flake .#nixos"
echo ""
echo "If llama-server hangs again before deployment:"
echo "  sudo systemctl restart llama-cpp.service"
echo ""
