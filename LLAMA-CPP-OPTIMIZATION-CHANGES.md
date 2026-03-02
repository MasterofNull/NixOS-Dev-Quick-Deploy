# llama.cpp Optimization Changes for AMD Cezanne APU

## Problem
The llama-server was experiencing stuck slots and hanging chat completion requests, causing Continue extension timeouts.

## Root Cause
- AMD Cezanne APU (Ryzen 5000U series) requires ROCm graphics version override
- Missing timeout configuration allowed stuck requests to block slots indefinitely
- Suboptimal thread and batch size settings for the hardware

## Changes Made

### 1. ROCm Graphics Version Override
**File:** `nix/hosts/nixos/facts.nix`

```nix
rocmGfxOverride = "9.0.0";  # Cezanne APU uses gfx90c
```

This tells ROCm to use the correct graphics compute version for your Ryzen 7 PRO 5850U APU.

### 2. llama-server Performance & Stability Options

```nix
llamaCpp.extraArgs = [
  # Prevent stuck slots: 120s timeout
  "--timeout" "120"
  
  # Limit concurrent requests to prevent resource contention
  "--parallel" "2"
  
  # Optimize batch sizes for interactive use
  "--batch-size" "512"     # Logical batch size
  "--ubatch-size" "64"     # Physical batch size (VRAM-friendly)
  
  # CPU threads = physical cores (8) for best latency
  "--threads" "8"
  "--threads-batch" "8"
  
  # Flash Attention for faster prompt processing
  "--flash-attn"
  
  # Keep model in RAM (prevents swapping)
  "--mlock"
  
  # Qwen3-Instruct reasoning format
  "--reasoning-format" "deepseek"
];
```

### 3. Embedding Server Optimization

```nix
embeddingServer.extraArgs = [
  "--threads" "8"
  "--batch-size" "512"
  "--flash-attn"
];
```

## Hardware Profile

Your system:
- **CPU:** AMD Ryzen 7 PRO 5850U (8 cores / 16 threads)
- **GPU:** AMD Cezanne Radeon Graphics (gfx90c)
- **RAM:** 27 GB
- **Platform:** Lenovo ThinkPad P14s AMD Gen2

## Deployment

### Apply the changes:

```bash
cd /home/hyperd/Documents/NixOS-Dev-Quick-Deploy
sudo nixos-rebuild switch --flake .#nixos
```

### Restart llama-cpp service:

```bash
sudo systemctl restart llama-cpp
```

### Verify the new configuration:

```bash
# Check service is running with new args
systemctl status llama-cpp

# View the command-line args
ps aux | grep llama-server

# Test chat completion
curl -X POST http://localhost:8080/v1/chat/completions \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer local-llama-cpp" \
  -d '{
    "model": "/var/lib/llama-cpp/models/Qwen3-4B-Instruct-2507-Q4_K_M.gguf",
    "messages": [{"role": "user", "content": "are you working?"}],
    "max_tokens": 50
  }'
```

### Monitor slot status:

```bash
# Check all slots are idle after requests
curl http://localhost:8080/slots | jq .
```

## Expected Improvements

1. **No more stuck slots** - 120s timeout automatically clears hung requests
2. **Faster response times** - Flash Attention + optimized batch sizes
3. **Better GPU utilization** - Correct ROCm gfx version (9.0.0)
4. **Stable inference** - 8 threads match physical cores, preventing CPU oversubscription
5. **Memory efficiency** - mlock prevents swapping, ubatch-size limits VRAM usage

## Continue Extension Configuration

Your Continue config at `ai-stack/continue/config.json` should work as-is:

```json
{
  "models": [
    {
      "title": "Local llama.cpp (direct)",
      "provider": "openai",
      "apiBase": "http://127.0.0.1:8080/v1",
      "apiKey": "dummy",
      "model": "AUTODETECT"
    }
  ]
}
```

## Troubleshooting

### If slots get stuck again:

```bash
# Check slot status
curl http://localhost:8080/slots | jq '.[] | select(.is_processing == true)'

# Force clear by restarting service
sudo systemctl restart llama-cpp

# Check logs for errors
journalctl -u llama-cpp -f --no-pager
```

### If GPU acceleration isn't working:

```bash
# Check ROCm environment variables
systemctl show llama-cpp | grep Environment

# Should show:
# HSA_OVERRIDE_GFX_VERSION=9.0.0
# HSA_ENABLE_SDMA=0
# GPU_MAX_ALLOC_PERCENT=100
```

### Performance monitoring:

```bash
# Watch GPU and CPU usage during inference
watch -n 1 'ps aux | grep llama-server | awk "{print \"CPU: \" \$3 \"%, MEM: \" \$6}\""'

# Check llama-server metrics
curl http://localhost:8080/metrics | grep -E "(request|slot|token)"
```

## Technical Details

### Why gfx9.0.0 for Cezanne?

The Ryzen 7 PRO 5850U uses AMD's Cezanne APU with RDNA2 graphics (gfx90c). ROCm officially supports gfx900/gfx906/gfx908, so we override to gfx9.0.0 which is compatible.

### Thread count rationale

- **Physical cores:** 8
- **Threads:** 8 (1 per physical core for inference)
- **SMT threads:** 16 total, but using 8 avoids context switching overhead

### Batch size tuning

- **batch-size 512:** Good for prompt processing
- **ubatch-size 64:** Fits in APU unified memory, prevents OOM
- **parallel 2:** Allows 2 concurrent users without contention

## References

- [llama.cpp ROCm documentation](https://github.com/ggerganov/llama.cpp/blob/master/docs/build.md#rocm)
- [AMD GPU OpenCL documentation](https://rocm.docs.amd.com/)
- [Qwen3 model documentation](https://huggingface.co/unsloth/Qwen3-4B-Instruct-2507-GGUF)
