# Qwen 3.6 Model Switch Recovery Plan

**Date:** 2026-04-19
**Issue:** Download failed at 64% (13.35GB out of 20.61GB)
**Error:** `curl: (23) Failure writing output to destination`

---

## Problem Summary

The model switch from Gemma 4 E4B to Qwen 3.6 35B failed during download due to:
- Network interruption or instability
- Download incomplete at 64% completion
- facts.nix configuration not persisted

**Current State:**
- facts.nix still shows: `llamaCpp.activeModel = "gemma4-e4b"`
- Partial download may exist in cache
- Need to resume download and complete switch

---

## Recovery Options

### Option A: Resume Partial Download ⭐ (RECOMMENDED)

**Why:** Fastest - resumes from 64%, saves 1+ hour

```bash
# Step 1: Resume download (will continue from 13.35GB)
bash scripts/ai/resume-model-download.sh

# Step 2: After download completes, update config
# Edit nix/hosts/hyperd/facts.nix line 36:
# Change: llamaCpp.activeModel = "gemma4-e4b";
# To:     llamaCpp.activeModel = "qwen3.6-35b";

# Step 3: Apply configuration
sudo nixos-rebuild switch --flake .#hyperd

# Step 4: Restart AI services
sudo systemctl restart ai-llama-cpp
sudo systemctl restart ai-hybrid-coordinator
```

**Estimated Time:** 30-45 minutes (resume from 64%)

---

### Option B: Clean Restart

**Why:** If partial download is corrupted

```bash
# Step 1: Clean partial downloads
rm -rf ~/.cache/huggingface/hub/*Qwen* 2>/dev/null

# Step 2: Re-run clean deploy
cd /home/hyperd/Documents/NixOS-Dev-Quick-Deploy
./nixos-quick-deploy.sh --clean-deploy

# When prompted:
#   Chat model: qwen3.6-35b
#   Embedding: bge-m3
```

**Estimated Time:** 1.5-2 hours (full download)

---

### Option C: Use Smaller Qwen Model

**Why:** Much faster download, still excellent performance

**Available Variants:**
- Qwen 3.6 14B (~8GB) - 70% faster download
- Qwen 3.6 8B (~5GB) - 80% faster download

```bash
# For 14B variant (recommended for 27GB RAM):
# Edit nix/hosts/hyperd/facts.nix line 36:
# Change to: llamaCpp.activeModel = "qwen3.6-14b";

# Then rebuild
sudo nixos-rebuild switch --flake .#hyperd
```

**Estimated Time:** 15-20 minutes (14B model)

---

## Troubleshooting

### Issue: Download Keeps Failing

**Solution 1: Check network stability**
```bash
# Test network stability
ping -c 100 huggingface.co

# If packet loss > 1%, download will be unreliable
# Consider downloading during off-peak hours
```

**Solution 2: Use wget instead of curl**
```bash
wget -c -O ~/.cache/huggingface/qwen3.6-35b.gguf \
  "https://huggingface.co/unsloth/Qwen3.6-35B-A3B-GGUF/resolve/main/Qwen3.6-35B-A3B-UD-Q4_K_M.gguf"
```

**Solution 3: Download to external location first**
```bash
# Download to stable location (like external drive)
# Then copy to cache when complete
```

### Issue: HuggingFace Authentication Errors

```bash
# Check token
echo $HF_TOKEN

# If missing, set token:
export HF_TOKEN="your_token_here"

# Or login:
huggingface-cli login
```

### Issue: Disk Space During Download

```bash
# Monitor space during download
watch -n 5 'df -h / | grep -v Filesystem'

# Qwen 35B needs ~25GB free space during download
# (20.6GB model + 5GB temp/buffer)
```

---

## Verification Steps

After successful model switch:

```bash
# 1. Check model is loaded
curl -s http://127.0.0.1:8080/v1/models | jq '.data[0].id'
# Should show: qwen3.6-35b (or similar)

# 2. Test inference
curl -X POST http://127.0.0.1:8080/v1/chat/completions \
  -H "Content-Type: application/json" \
  -d '{
    "messages": [{"role": "user", "content": "Reply with exactly: TEST OK"}],
    "max_tokens": 10,
    "temperature": 0
  }' | jq '.choices[0].message.content'

# 3. Check orchestrator health
curl -s http://127.0.0.1:8003/health | jq

# 4. Test with local orchestrator
scripts/ai/local-orchestrator "What model are you running on?"
```

---

## Rollback Plan (If Needed)

If Qwen 3.6 doesn't work well:

```bash
# 1. Revert facts.nix
# Change back to: llamaCpp.activeModel = "gemma4-e4b";

# 2. Rebuild
sudo nixos-rebuild switch --flake .#hyperd

# 3. Restart services
sudo systemctl restart ai-llama-cpp
```

The Gemma 4 model files should still be in cache and will load immediately.

---

## Model Comparison

| Model | Size | RAM Needed | Speed | Quality | Download Time |
|-------|------|------------|-------|---------|---------------|
| **Gemma 4 E4B** | 5.4GB | 8GB+ | Fast | Good | 15 min |
| **Qwen 3.6 8B** | 5GB | 8GB+ | Fast | Very Good | 15 min |
| **Qwen 3.6 14B** | 8GB | 12GB+ | Medium | Excellent | 25 min |
| **Qwen 3.6 35B** | 20.6GB | 24GB+ | Slower | Superior | 1.5 hours |

**Your System:** 27GB RAM - Can run up to 35B model

**Recommendation:** Try 14B first if 35B download keeps failing. It's 70% faster to download and still significantly better than Gemma 4.

---

## Next Steps After Model Switch

1. **Test system prompt v2-optimized** with Qwen 3.6
   ```bash
   python scripts/testing/test-prompt-effectiveness.py --compare
   ```

2. **Validate improvements**
   - Check prompt understanding
   - Test tool usage
   - Verify delegation decisions

3. **Tune if needed**
   - Qwen 3.6 may allow slightly more complex prompts
   - Can add back JSON schemas if helpful
   - May benefit from more detailed tool descriptions

---

## Status Tracking

- [ ] Download complete (resume-model-download.sh)
- [ ] facts.nix updated (qwen3.6-35b)
- [ ] NixOS rebuild successful
- [ ] Services restarted
- [ ] Model loaded and responding
- [ ] System prompt tested with new model
- [ ] Performance validated

---

**Document Version:** 1.0.0
**Created:** 2026-04-19
**Status:** Ready for Execution
**Estimated Total Time:** 30-45 minutes (resume) or 1.5-2 hours (clean)
