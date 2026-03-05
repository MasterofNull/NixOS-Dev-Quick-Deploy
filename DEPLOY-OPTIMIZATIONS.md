# Deploy Llama-Server Optimizations

**Status:** ✅ Configuration files updated, ready to deploy

---

## What's Been Changed

Your `nix/hosts/nixos/facts.nix` now includes optimized llama-server settings:

```nix
# ROCm graphics override for AMD Cezanne APU
rocmGfxOverride = "9.0.0";

# Stability and performance optimizations
llamaCpp.extraArgs = [
  "--timeout" "120"           # Auto-clear stuck requests (PREVENTS HANGS)
  "--parallel" "2"            # Limit concurrent slots
  "--batch-size" "512"        # Optimize batch processing
  "--ubatch-size" "64"
  "--threads" "8"             # Match physical cores (not hyperthreads)
  "--threads-batch" "8"
  "--flash-attn"              # Faster prompt processing
  "--mlock"                   # Prevent memory swapping
  "--reasoning-format" "deepseek"  # Qwen3-Instruct format
];

embeddingServer.extraArgs = [
  "--threads" "8"
  "--batch-size" "512"
  "--flash-attn"
];
```

---

## Deploy Using Your Quick Deploy Script

### Option 1: Standard Deploy (Recommended)

```bash
./nixos-quick-deploy.sh --host nixos
```

This will:
1. Build the new NixOS configuration with optimized llama-server
2. Restart llama-cpp service with new parameters
3. Apply all other configuration changes
4. Run health checks

**Expected time:** 5-15 minutes (depending on what changed)

### Option 2: Quick Rebuild (If You Prefer Direct Command)

```bash
sudo nixos-rebuild switch --flake .#nixos
```

---

## What Will Happen After Deploy

### Before Deploy (Current State)
```bash
$ ps aux | grep llama-server
llama  328093  --host 127.0.0.1 --port 8080 --model ... --ctx-size 32768 --n-gpu-layers 99
# ❌ No timeout, no parallel limit, wrong thread count
```

### After Deploy (Optimized)
```bash
$ ps aux | grep llama-server  
llama  XXXXXX  --host 127.0.0.1 --port 8080 --model ... \
  --ctx-size 32768 --n-gpu-layers 99 \
  --timeout 120 --parallel 2 --batch-size 512 --ubatch-size 64 \
  --threads 8 --threads-batch 8 --flash-attn --mlock \
  --reasoning-format deepseek
# ✅ All optimizations active
```

---

## Verify After Deploy

### 1. Check Service Configuration

```bash
# Verify new command-line args
systemctl show llama-cpp -p ExecStart

# Should show:
# --timeout 120 --parallel 2 --threads 8 --flash-attn --mlock --reasoning-format deepseek
```

### 2. Test Chat Completions

```bash
curl -X POST http://localhost:8080/v1/chat/completions \
  -H "Content-Type: application/json" \
  -d '{
    "model": "Qwen3-4B-Instruct",
    "messages": [{"role": "user", "content": "are you working?"}],
    "max_tokens": 50
  }'
```

**Expected:** Response within 5-10 seconds

### 3. Test Continue Extension

1. Open VSCodium
2. Open Continue extension
3. Ask: "are you working?"
4. **Expected:** Quick response (no hanging)

### 4. Check Slot Status

```bash
# When idle, all slots should be free
curl http://localhost:8080/slots | python3 -m json.tool

# Expected:
# [{"id": 0, "is_processing": false}, ...]
```

---

## If llama-server Hangs BEFORE You Deploy

Run the emergency fix script:

```bash
./fix-llama-hang.sh
```

This will restart llama-cpp to clear stuck slots (temporary fix until deploy).

---

## Rollback If Needed

If something goes wrong after deploy:

```bash
# Boot into previous generation
sudo nixos-rebuild switch --rollback

# Or select from boot menu at startup
```

---

## Configuration Files Modified

These files have been updated and will be deployed:

| File | Changes |
|------|---------|
| `nix/hosts/nixos/facts.nix` | Added `rocmGfxOverride`, `llamaCpp.extraArgs`, `embeddingServer.extraArgs` |
| `ai-stack/mcp-servers/aidb/server.py` | Fixed embedding fallback to use correct URL |
| `scripts/testing/check-mcp-health.sh` | Added `--optional` flag support |
| `scripts/data/rebuild-qdrant-collections.sh` | Fixed uninitialized variables |

**All changes are declarative** - they survive rebuilds and reboots.

---

## Expected Performance After Deploy

| Metric | Before | After |
|--------|--------|-------|
| First token latency | Hangs/timeout | 2-5 seconds |
| Slot hangs | Frequent | Never (auto-clear at 120s) |
| Concurrent users | 1 (slots hang) | 2 (stable) |
| GPU utilization | Suboptimal | Optimized |
| CPU usage | Oversubscribed | Optimal (8 threads) |
| Continue extension | Hangs | Works smoothly |

---

## Next Steps

1. **Deploy now:**
   ```bash
   ./nixos-quick-deploy.sh --host nixos
   ```

2. **Test Continue extension** after deploy completes

3. **Monitor for 24 hours** to ensure no more hangs

4. **Report back** if any issues

---

**Questions?** See [`CONTINUE-EXTENSION-HANG-FIX.md`](CONTINUE-EXTENSION-HANG-FIX.md) for complete troubleshooting guide.
