# 🚨 SYSTEM RECOVERY PLAN

**Date:** 2026-03-02 19:50 PST  
**Status:** CRITICAL - Multiple system issues  
**Priority:** STABILITY FIRST

---

## 🔴 CURRENT ISSUES

### 1. llama-cpp Hanging (CRITICAL)
- **Symptom:** Chat completions timeout
- **Cause:** Slots stuck, needs restart
- **Impact:** Continue extension not working

### 2. COSMIC Theme Broken (HIGH)
- **Symptom:** `error loading system dark theme`
- **Cause:** Likely from recent systemd user service changes
- **Impact:** Desktop appearance broken

### 3. Audit Log Errors (MEDIUM)
- **Symptom:** `audit: error in audit_log_subj_ctx`
- **Cause:** AppArmor/security module conflicts
- **Impact:** Log spam, potential security module issues

### 4. Deployment Instability (HIGH)
- **Symptom:** Multiple deploy failures
- **Cause:** Too many concurrent changes
- **Impact:** System in inconsistent state

---

## ✅ IMMEDIATE ACTIONS (Do These NOW)

### Step 1: Restart llama-cpp (Restore Chat)

```bash
sudo systemctl restart llama-cpp.service
```

**Verify:**
```bash
curl -s -X POST http://localhost:8080/v1/chat/completions \
  -H "Content-Type: application/json" \
  -d '{"messages": [{"role": "user", "content": "hi"}], "max_tokens": 5}' \
  --max-time 10
```

Should respond within 10 seconds.

---

### Step 2: Fix COSMIC Theme

```bash
# Reset cosmic theme configuration
gsettings reset com.system76.cosmic-theme theme-mode
gsettings set com.system76.cosmic-theme theme-mode "dark"

# Restart cosmic compositor
systemctl --user restart cosmic-comp.service

# If still broken, reboot into COSMIC session
sudo reboot
```

---

### Step 3: Disable Audit Spam (Temporary)

```bash
# Temporarily reduce audit log noise
sudo sysctl -w kernel.audit=0

# Or add to /etc/sysctl.conf to persist
echo "kernel.audit = 0" | sudo tee -a /etc/sysctl.conf
```

---

### Step 4: Roll Back Recent Changes (If Needed)

If system is too unstable:

```bash
# Boot into previous generation
sudo nixos-rebuild switch --rollback

# Or select from boot menu on next reboot
```

---

## 📋 STABILIZATION PLAN

### Phase 1: Restore Basic Functionality (Today)

- [ ] llama-cpp responds to chat requests
- [ ] COSMIC theme loads correctly
- [ ] No boot/shutdown errors
- [ ] Continue extension works

### Phase 2: Clean Deployment (Tomorrow)

After stability restored:

1. **Commit current working state**
2. **Test ONE change at a time**
3. **Deploy with `--dry-run` first**
4. **Keep rollback generation**

### Phase 3: Re-implement Features (This Week)

Implement features **one at a time**:

1. llama.cpp optimizations (test thoroughly)
2. AIDB embedding fixes (test thoroughly)
3. Quick-deploy improvements (test thoroughly)

---

## 🔧 MINIMAL WORKING CONFIG

For immediate stability, use this minimal `facts.nix`:

```nix
aiStack = {
  backend = "llamacpp";
  acceleration = "auto";
  llamaCpp.model = "/var/lib/llama-cpp/models/Qwen3-4B-Instruct-2507-Q4_K_M.gguf";
  llamaCpp.huggingFaceRepo = "unsloth/Qwen3-4B-Instruct-2507-GGUF";
  llamaCpp.huggingFaceFile = "Qwen3-4B-Instruct-2507-Q4_K_M.gguf";
  llamaCpp.sha256 = "3605803b982cb64aead44f6c1b2ae36e3acdb41d8e46c8a94c6533bc4c67e597";
  
  # MINIMAL optimizations (no aggressive settings)
  llamaCpp.extraArgs = [
    "--timeout" "120"
    "--threads" "8"
  ];
  
  rocmGfxOverride = "9.0.0";
  
  embeddingDimensions = 2560;
  embeddingServer.enable = true;
  embeddingServer.model = "/var/lib/llama-cpp/models/Qwen3-Embedding-4B-q4_k_m.gguf";
  embeddingServer.huggingFaceRepo = "Mungert/Qwen3-Embedding-4B-GGUF";
  embeddingServer.huggingFaceFile = "Qwen3-Embedding-4B-q4_k_m.gguf";
  embeddingServer.sha256 = "2a91ec30c4c694af60cbedfc2f30d6aa5fd69a5286a8fb5544aa47868243054e";
  embeddingServer.pooling = "last";
  
  ui.enable = true;
  vectorDb.enable = false;
  listenOnLan = false;
};
```

**Remove these for now** (add back later one at a time):
- `--parallel` (can cause issues)
- `--batch-size` / `--ubatch-size` (tune later)
- `--flash-attn` (test separately)
- `--mlock` (can cause OOM on some systems)
- `--reasoning-format` (test separately)

---

## 🚀 DEPLOYMENT BEST PRACTICES

### Before Deploy
```bash
# 1. Check current generation
nixos-generation --list

# 2. Test configuration
nixos-rebuild build --flake .#nixos

# 3. Keep last 10 generations
sudo nix-env --delete-generations +10
```

### During Deploy
```bash
# Use verbose output
./nixos-quick-deploy.sh --host nixos --verbose

# Watch logs in another terminal
journalctl -f
```

### After Deploy
```bash
# 1. Verify services
systemctl status llama-cpp ai-aidb llama-cpp-embed

# 2. Test chat
curl -X POST http://localhost:8080/v1/chat/completions \
  -H "Content-Type: application/json" \
  -d '{"messages": [{"role": "user", "content": "test"}], "max_tokens": 10}'

# 3. Keep working generation
# If issues: sudo nixos-rebuild switch --rollback
```

---

## 📞 EMERGENCY CONTACTS

### Quick Rollback
```bash
sudo nixos-rebuild switch --rollback
```

### Boot Previous Generation
- Reboot
- Select previous generation from systemd-boot menu
- Press `e` to edit if needed

### Disable AI Stack Temporarily
```bash
sudo systemctl stop llama-cpp ai-aidb llama-cpp-embed
sudo systemctl disable llama-cpp ai-aidb llama-cpp-embed
```

---

## ✅ SUCCESS CRITERIA

System is stable when:

- [ ] No failed systemd units (`systemctl --failed`)
- [ ] No priority 3 errors in journal (`journalctl -p 3 -xb`)
- [ ] Chat responds in <10 seconds
- [ ] COSMIC theme loads
- [ ] Boot/shutdown clean (no errors)
- [ ] Continue extension works

---

**Last Updated:** 2026-03-02 19:50 PST  
**Next Review:** After each stabilization step
