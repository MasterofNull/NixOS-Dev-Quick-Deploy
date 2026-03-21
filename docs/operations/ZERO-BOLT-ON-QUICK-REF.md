# Zero Bolt-On Features - Quick Reference Card

**Status:** Active
**Owner:** AI Harness Team
**Last Updated:** 2026-03-20

**TL;DR:** Everything works out-of-box. No manual enabling required.

---

## Deploy & Go

```bash
# Deploy the system
sudo nixos-rebuild switch --flake .

# That's it! All features are enabled and ready to use.
```

No manual steps. No feature enabling. No configuration required.

---

## What's Enabled By Default

| Feature | What It Does | Performance |
|---------|-------------|-------------|
| AI Harness | Core framework | < 1% overhead |
| Memory System | Learning & recall | ~50ms per query |
| Context Compression | 35% token savings | ~2% overhead |
| Tree Search | 12% better search | +200ms per query |
| Evaluation | Quality tracking | ~100ms (async) |
| Task Classification | Smart routing | ~50ms |
| Capability Discovery | Tool finding | ~30-50ms |
| Prompt Caching | 5% token savings | Minimal |
| Web Research | Current info | 2-4s when used |
| Monitoring | Health tracking | Background |
| Security Audit | Tool validation | ~50-100ms |

**All of these work immediately after deployment.**

---

## Verify Everything Works

### Quick Check (30 seconds)

```bash
scripts/testing/smoke-integration-complete.sh
```

### Comprehensive Test (2 minutes)

```bash
scripts/testing/test-integration-completeness.py
```

### Check Feature Status

```bash
# Auto-enable report
cat /tmp/auto-enable-report.txt

# Or via API
curl http://localhost:9090/api/status | jq '.features'
```

---

## Customization (Not Enabling)

Configuration is for **tuning**, not enabling. Everything is already on.

### Performance Tuning

```nix
# In your NixOS configuration
mySystem.aiHarness = {
  memory.retentionDays = 90;      # Keep memories longer
  eval.intervalSeconds = 600;     # Eval less frequently
  retrieval.compressionRatio = 0.25;  # Compress more
};
```

### Resource Limits

```bash
# Reduce background activity
export AI_EVAL_INTERVAL_SECONDS="900"
export CONTINUOUS_LEARNING_ENABLED="false"
```

### Air-Gapped Deployment

```bash
# Disable internet-dependent features
export AI_WEB_RESEARCH_ENABLED="false"
export AI_BROWSER_RESEARCH_ENABLED="false"
export AI_TELEMETRY_ENABLED="false"
```

---

## Conditional Features (Auto-Enable If You Have The Hardware)

These enable automatically if you have sufficient resources:

| Feature | Requires | Benefit |
|---------|----------|---------|
| Speculative Decoding | Qwen/DeepSeek + 16GB RAM + GPU | 15-25% faster inference |
| LLM Expansion | 4+ cores + opt-in flag | 12% better recall |
| Cross-Encoder | 8GB+ RAM + opt-in flag | 8% better precision |

**Check auto-enable report to see what activated:**
```bash
cat /tmp/auto-enable-report.txt
```

**Opt in to LLM expansion:**
```bash
export AI_LLM_EXPANSION_OPT_IN="true"
sudo nixos-rebuild switch
```

---

## Experimental Features (Explicit Opt-In Only)

These are disabled by default because they're experimental or costly:

### Query Expansion (Experimental)

```bash
export QUERY_EXPANSION_ENABLED="true"
sudo nixos-rebuild switch
```

**Warning:** Can amplify noise. Use for short/ambiguous queries only.

### Remote LLM Feedback (Requires API Key)

```bash
export REMOTE_LLM_FEEDBACK_ENABLED="true"
export ANTHROPIC_API_KEY="your-key-here"
sudo nixos-rebuild switch
```

**Warning:** Incurs API costs (~$0.001-0.01 per eval).

### Pattern Extraction (Research Only)

```bash
export PATTERN_EXTRACTION_ENABLED="true"
sudo nixos-rebuild switch
```

**Use case:** Training data collection, knowledge distillation.

---

## Troubleshooting

### Feature Not Working?

1. **Check service status**
   ```bash
   systemctl status hybrid-coordinator
   systemctl status llama-cpp
   ```

2. **Check auto-enable report**
   ```bash
   cat /tmp/auto-enable-report.txt
   ```

3. **Check environment**
   ```bash
   systemctl show hybrid-coordinator | grep "Environment="
   ```

4. **Run integration test**
   ```bash
   scripts/testing/test-integration-completeness.py --verbose
   ```

### Conditional Feature Not Enabling?

1. **Check system resources**
   ```bash
   nproc  # CPU cores
   free -h  # RAM
   nvidia-smi  # GPU (if NVIDIA)
   ```

2. **Check auto-enable decision**
   ```bash
   grep "Speculative\|Expansion\|Cross-Encoder" /tmp/auto-enable-report.txt
   ```

3. **Manual override**
   ```bash
   export AI_SPECULATIVE_DECODING_ENABLED="true"
   sudo nixos-rebuild switch
   ```

### Service Won't Start?

1. **Check dependencies**
   ```bash
   systemctl status postgresql
   systemctl status qdrant
   ```

2. **Check logs**
   ```bash
   journalctl -u hybrid-coordinator -n 50
   ```

3. **Validate config**
   ```bash
   scripts/testing/smoke-integration-complete.sh
   ```

---

## Dashboard

**All cards load automatically.** No toggles for core features.

**Access:** `http://localhost:8889`

**Features visible:**
- System health
- Service status
- AI stack metrics
- Memory usage
- Evaluation scores
- Real-time updates

**No configuration needed.**

---

## Philosophy

### What Changed

**Old way (bolt-on):**
```
Deploy → Enable features → Configure → Test → Use
         ↑ Manual step required
```

**New way (integrated):**
```
Deploy → Use
         ↑ No manual steps
```

### Why This Matters

- **Faster onboarding:** Minutes instead of hours
- **Fewer errors:** No missed enabling steps
- **Consistent experience:** Same everywhere
- **Better testing:** Single integrated path

### Core Principle

> If it's stable and tested, it's enabled by default.
> If it's experimental, it's opt-in.
> Configuration is for customization, not enablement.

---

## Learn More

- **Full architecture:** `docs/architecture/integration-model.md`
- **Feature defaults:** `config/feature-defaults.yaml`
- **Auto-enable script:** `lib/deploy/auto-enable-features.sh`
- **Test suites:** `scripts/testing/`

---

## Quick Commands Cheat Sheet

```bash
# Deploy system (all features auto-enable)
sudo nixos-rebuild switch --flake .

# Verify integration
scripts/testing/smoke-integration-complete.sh

# Check feature status
cat /tmp/auto-enable-report.txt

# Customize (example: longer memory)
# Edit configuration.nix:
mySystem.aiHarness.memory.retentionDays = 90;
sudo nixos-rebuild switch

# Opt into experimental feature
export QUERY_EXPANSION_ENABLED="true"
sudo nixos-rebuild switch

# Opt out of telemetry
export AI_TELEMETRY_ENABLED="false"
sudo nixos-rebuild switch

# Dashboard
xdg-open http://localhost:8889

# Health check
./deploy health

# Comprehensive test
scripts/testing/test-integration-completeness.py
```

---

**Everything integrated. Zero bolt-ons. Just deploy and use.**
