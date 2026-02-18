# vLLM Migration Guide - HuggingFace TGI, Qdrant, and Ollama Removal

## Overview

This document describes the migration from system-level AI services (HuggingFace TGI, Qdrant, Ollama) to a user-level Podman setup with vLLM.

## What Was Removed

### System-Level Services (configuration.nix)
- **HuggingFace TGI services**: `huggingface-tgi.service` and `huggingface-tgi-scout.service`
- **Qdrant vector database**: `qdrant.service`
- **Ollama references**: State directories and configuration
- **MindsDB**: Container definitions and port configuration

###Services Removed
- All systemd service definitions for AI inference
- Activation scripts for HuggingFace image prefetching
- tmpfiles rules for HuggingFace and Qdrant state directories
- Variables for Ollama, HuggingFace TGI, and Qdrant configuration

### Home Manager Changes (home.nix)
- Removed shell aliases: `hf-start`, `hf-stop`, `hf-restart`, `hf-logs`, `ollama-list`
- Updated variable definitions to use vLLM endpoints instead of TGI
- Removed Qdrant port definitions
- Removed Ollama container references

## What Remains

### Configuration Files
- Gitea service - **unchanged**
- Netdata monitoring - **unchanged**
- Podman/container infrastructure - **unchanged**
- HuggingFace API token secret (still needed for model downloads)

### Migration Status
✅ System services removed from [configuration.nix](templates/configuration.nix)
✅ Variables updated in [home.nix](templates/home.nix)
⚠️  **User action required**: Update VSCode/Continue.dev settings to use vLLM endpoints
⚠️  **User action required**: Update any personal scripts that referenced old endpoints

## New Architecture

### vLLM Setup Location
All AI inference is now managed in: `~/.config/ai-optimizer/`

### Endpoint Changes

| Old Service | Old Endpoint | New Service | New Endpoint |
|------------|-------------|------------|-------------|
| HuggingFace TGI (DeepSeek) | `http://127.0.0.1:8080` | vLLM Primary | `http://127.0.0.1:8000/v1` |
| HuggingFace TGI (Scout) | `http://127.0.0.1:8085` | vLLM Secondary | `http://127.0.0.1:8001/v1` |
| Ollama | `http://127.0.0.1:11434` | *(removed)* | Use vLLM instead |
| Qdrant | `http://127.0.0.1:6333` | *(removed)* | Use ai-optimizer setup |

## Required Manual Updates

### 1. Update VSCode Continue.dev Configuration

The Continue.dev extension settings in home.nix still reference the old endpoints. You need to update these lines manually:

**File**: [templates/home.nix](templates/home.nix) (around line 1987-2010)

**Old**:
```nix
"continue.models" = [
  {
    title = "Llama 3.2 Instruct";
    provider = "ollama";
    model = "llama3.2";
    baseUrl = ollamaHost;
  }
  {
    title = "DeepSeek R1 Distill 7B (coding)";
    provider = "openai";
    model = huggingfaceModelId;
    baseUrl = "${huggingfaceTgiEndpoint}/v1";
  }
];
```

**New** (example):
```nix
"continue.models" = [
  {
    title = "vLLM Primary Model";
    provider = "openai";
    model = "your-model-name";  # Match what's loaded in vLLM
    baseUrl = vllmPrimaryEndpoint;
  }
];
```

### 2. Update Environment Variables

Several environment variables in home.nix (around line 2275-2282) reference old services:

```nix
# Old
HUGGINGFACE_MODEL_ID = "${huggingfaceModelId}";
OLLAMA_HOST = "${ollamaHost}";

# Update to:
VLLM_PRIMARY_ENDPOINT = "${vllmPrimaryEndpoint}";
VLLM_SECONDARY_ENDPOINT = "${vllmSecondaryEndpoint}";
```

### 3. Check ai-optimizer Setup

Ensure your ai-optimizer Podman setup is configured:

```bash
cd ~/.config/ai-optimizer
# Check docker-compose.yml or equivalent Podman setup
# Verify vLLM containers are running
podman ps | grep vllm
```

## Benefits of This Migration

1. **Memory Savings**: ~1.4GB freed when AI services not in use
2. **Faster System Rebuilds**: Fewer systemd services to configure
3. **On-Demand AI**: Start/stop AI services as needed
4. **Easier Updates**: Update AI models without system rebuild
5. **Better Resource Control**: User-level containers are easier to manage

## Rollback (if needed)

If you need to temporarily restore the old services:

1. Check out the previous git commit
2. Copy the old systemd service definitions from git history
3. Run `sudo nixos-rebuild switch`

## Next Steps

1. **Stop old services** (if still running):
   ```bash
   sudo systemctl stop huggingface-tgi.service
   sudo systemctl stop huggingface-tgi-scout.service
   sudo systemctl stop qdrant.service  # if it exists
   ```

2. **Clean up state directories** (optional, saves disk space):
   ```bash
   sudo rm -rf /var/lib/huggingface
   sudo rm -rf /var/lib/huggingface-scout
   sudo rm -rf /var/lib/qdrant
   sudo rm -rf /var/lib/ollama
   ```

3. **Rebuild system**:
   ```bash
   sudo nixos-rebuild switch
   ```

4. **Verify ai-optimizer setup**:
   ```bash
   cd ~/.config/ai-optimizer
   # Start your vLLM containers
   docker-compose up -d  # or equivalent podman command
   ```

5. **Test vLLM endpoints**:
   ```bash
   curl http://127.0.0.1:8000/v1/models
   ```

## Troubleshooting

### Services Won't Stop
```bash
# Force stop and disable
sudo systemctl stop huggingface-tgi.service huggingface-tgi-scout.service
sudo systemctl disable huggingface-tgi.service huggingface-tgi-scout.service
```

### Port Conflicts
If vLLM can't bind to ports 8000/8001, check for lingering processes:
```bash
sudo lsof -i :8000
sudo lsof -i :8001
```

### Missing vLLM Setup
If you don't have the ai-optimizer setup yet, refer to the vLLM documentation:
- Official vLLM docs: https://docs.vllm.ai/
- Your ai-optimizer repository documentation

## Additional Notes

- The HuggingFace API token secret is retained in case you need to download models
- Gitea service is unaffected by this migration
- Netdata monitoring continues to work
- Podman infrastructure remains the same

## Questions?

If you encounter issues with this migration, check:
1. The old git commits for reference implementations
2. The ai-optimizer documentation in `~/.config/ai-optimizer/`
3. vLLM official documentation

---

**Migration Date**: 2025-11-24
**Status**: System services removed, user action required for application configs
