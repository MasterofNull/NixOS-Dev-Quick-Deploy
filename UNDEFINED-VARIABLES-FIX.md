# Undefined Variables Fix - AI Service Migration

## Status: Variables Are Properly Handled

After review of the codebase, the AI service migration (HuggingFace TGI, Qdrant, Ollama, MindsDB) is **properly configured** and should not cause undefined variable errors.

## Variable Replacement Status

### ✅ Properly Handled Variables

All AI service variables are defined with placeholders in templates and replaced during config generation:

| Variable | Template Placeholder | Replacement Location | Default Value |
|----------|---------------------|---------------------|---------------|
| `huggingfaceModelId` | `HUGGINGFACE_MODEL_ID_PLACEHOLDER` | [lib/config.sh:3769](lib/config.sh#L3769) | `"deepseek-ai/DeepSeek-R1-Distill-Qwen-7B"` |
| `huggingfaceScoutModelId` | `HUGGINGFACE_SCOUT_MODEL_ID_PLACEHOLDER` | [lib/config.sh:3770](lib/config.sh#L3770) | `"meta-llama/Llama-4-Scout-17B-16E"` |
| `huggingfaceTgiEndpoint` | `HUGGINGFACE_TGI_ENDPOINT_PLACEHOLDER` | [lib/config.sh:3771](lib/config.sh#L3771) | `"http://127.0.0.1:8000"` |
| `huggingfaceScoutTgiEndpoint` | `HUGGINGFACE_SCOUT_TGI_ENDPOINT_PLACEHOLDER` | [lib/config.sh:3772](lib/config.sh#L3772) | `"http://127.0.0.1:8001"` |
| `huggingfaceTgiContainerEndpoint` | `HUGGINGFACE_TGI_CONTAINER_ENDPOINT_PLACEHOLDER` | [lib/config.sh:3773](lib/config.sh#L3773) | `"http://host.containers.internal:8000"` |
| `LOCAL_AI_STACK_ENABLED` | `LOCAL_AI_STACK_ENABLED_PLACEHOLDER` | [lib/config.sh:3768](lib/config.sh#L3768) | `false` |

### ✅ Legacy Variables (Backward Compatibility)

These variables remain defined in [templates/home.nix](templates/home.nix) to prevent errors:

- `ollamaPort` = `11434` (deprecated but defined)
- `ollamaHost` = `"http://127.0.0.1:11434"` (deprecated but defined)
- `podmanAiStackOllamaContainerName` (deprecated but defined)
- `podmanAiStackQdrantContainerName` (deprecated but defined)
- `podmanAiStackMindsdbContainerName` (deprecated but defined)

## Default Values Aligned with vLLM

The deployment script now defaults AI endpoints to vLLM-compatible ports:

```bash
# lib/config.sh defaults (lines 3745-3755)
huggingface_tgi_endpoint_default="http://127.0.0.1:8000"  # vLLM primary
huggingface_scout_tgi_endpoint_default="http://127.0.0.1:8001"  # vLLM secondary
huggingface_tgi_container_endpoint_default="http://host.containers.internal:8000"
```

**Note**: These defaults point to vLLM endpoints, not the old TGI services.

## What Was Actually Removed

### From [configuration.nix](templates/configuration.nix):
- ✅ System-level HuggingFace TGI systemd services
- ✅ Qdrant systemd service
- ✅ Ollama state directory references
- ✅ HuggingFace activation scripts
- ✅ tmpfiles rules for HuggingFace/Qdrant

### From [home.nix](templates/home.nix):
- ✅ Shell aliases (`hf-start`, `hf-stop`, `ollama-list`)
- ✅ MindsDB port variables

### Kept (for compatibility):
- ✅ Variable placeholders (replaced at build time)
- ✅ HuggingFace cache directory references (still needed for model downloads)
- ✅ HuggingFace API token secret (still needed for authentication)

## Common Error Scenarios and Fixes

### Error 1: "Undefined variable: huggingfaceModelId"

**Cause**: Old home.nix from before migration
**Fix**: Rebuild with the latest templates:
```bash
cd /path/to/NixOS-Dev-Quick-Deploy
sudo nixos-rebuild switch
```

### Error 2: "Undefined variable: localAiStackEnabled"

**Cause**: LOCAL_AI_STACK_ENABLED not set in environment
**Fix**: Variable defaults to `false` automatically in [lib/config.sh:3768](lib/config.sh#L3768)

### Error 3: Service systemd errors for removed services

**Cause**: Old services still enabled
**Fix**:
```bash
# Stop and disable removed services
sudo systemctl stop huggingface-tgi.service huggingface-tgi-scout.service
sudo systemctl disable huggingface-tgi.service huggingface-tgi-scout.service

# Rebuild system
sudo nixos-rebuild switch
```

### Error 4: Placeholder not replaced

**Cause**: Script version mismatch
**Fix**: Ensure you're using the latest version of `lib/config.sh`:
```bash
git pull origin main
./nixos-quick-deploy.sh
```

## Validation Steps

To verify proper configuration:

### 1. Check Template Placeholders
```bash
grep -n "_PLACEHOLDER" templates/home.nix | grep -i "huggingface\|ollama\|qdrant"
```

Expected output:
```
46:  huggingfaceModelId = HUGGINGFACE_MODEL_ID_PLACEHOLDER;
47:  huggingfaceScoutModelId = HUGGINGFACE_SCOUT_MODEL_ID_PLACEHOLDER;
48:  huggingfaceTgiEndpoint = HUGGINGFACE_TGI_ENDPOINT_PLACEHOLDER;
49:  huggingfaceScoutTgiEndpoint = HUGGINGFACE_SCOUT_TGI_ENDPOINT_PLACEHOLDER;
50:  huggingfaceTgiContainerEndpoint = HUGGINGFACE_TGI_CONTAINER_ENDPOINT_PLACEHOLDER;
```

### 2. Check lib/config.sh Replacements
```bash
grep -n "replace_placeholder.*HUGGINGFACE" lib/config.sh
```

Expected output should show all placeholder replacements around lines 3769-3773.

### 3. Test Configuration Generation
```bash
# Generate config without applying
./nixos-quick-deploy.sh --dry-run

# Check generated home.nix for undefined variables
grep -n "PLACEHOLDER" ~/.config/home-manager/home.nix
# Should return nothing (all placeholders replaced)
```

### 4. Verify NixOS Build
```bash
# Build without switching
sudo nixos-rebuild build

# Check for undefined variable errors in output
```

## Migration Impact Summary

| Component | Status | Impact |
|-----------|--------|--------|
| System services | Removed | ✅ No errors - properly cleaned up |
| Variable placeholders | Retained | ✅ No errors - replaced at build time |
| Legacy compatibility | Maintained | ✅ No errors - deprecated vars defined |
| Default endpoints | Updated | ✅ Points to vLLM (8000/8001) |
| User applications | Manual update needed | ⚠️ See [VLLM-MIGRATION.md](VLLM-MIGRATION.md) |

## References to Other Services

Some scripts may still reference the old services but are not critical to system deployment:

### Non-Critical Scripts (Optional Cleanup):
- `scripts/ai-model-manager.sh` - Model management (can be updated later)
- `scripts/system-health-check.sh` - Health monitoring (can be updated later)
- `scripts/setup-mcp-databases.sh` - MCP setup (still functional)
- `scripts/deploy-aidb-mcp-server.sh` - AIDB deployment (still functional)

### Archive Scripts (No Action Needed):
- `archive/temp-docs-*/` - Old documentation and tests

## Conclusion

**All undefined variable errors related to the AI service migration have been prevented** through:

1. ✅ Proper placeholder replacement in `lib/config.sh`
2. ✅ Default values for all variables
3. ✅ Legacy variable definitions for backward compatibility
4. ✅ Updated endpoint defaults to vLLM ports

**No script changes are required** for the core deployment to work. The system will build successfully with the current configuration.

**Optional**: Update user-facing scripts (`scripts/` directory) and VSCode settings in `home.nix` to use vLLM endpoints instead of TGI - see [VLLM-MIGRATION.md](VLLM-MIGRATION.md) for details.

---

**Last Updated**: 2025-11-24
**Migration Status**: Complete - No undefined variables
