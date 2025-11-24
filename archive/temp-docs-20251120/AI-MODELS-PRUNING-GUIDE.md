# AI Models Pruning and Management Guide

## Current AI Model Inventory

### TGI (Text Generation Inference) Models - System Services

**Location**: `/var/lib/huggingface/cache/` and `/var/lib/huggingface-scout/cache/`

#### Active Models:
1. **DeepSeek-R1-Distill-Qwen-7B** (Port 8080)
   - **Repository**: `deepseek-ai/DeepSeek-R1-Distill-Qwen-7B`
   - **Size**: ~15GB
   - **Status**: ✅ **KEEP** - Latest distilled reasoning model
   - **Service**: `huggingface-tgi.service`

2. **Llama-4-Scout-17B-16E** (Port 8085)
   - **Repository**: `meta-llama/Llama-4-Scout-17B-16E`
   - **Size**: ~35GB
   - **Status**: ✅ **KEEP** - Latest Llama 4 Scout with MoE architecture
   - **Service**: `huggingface-tgi-scout.service`

### Ollama Models - User Services

**Location**: `~/.ollama/models/` (for user-level service)

#### Active Models (from Phase 8):
1. **phi4**
   - **Size**: ~8GB
   - **Status**: ✅ **KEEP** - Lightweight, fast, Microsoft's latest SLM
   - **Pulled by**: Phase 8 deployment script

#### Models You May Have Downloaded Previously:

**To check what's installed**, run:
```bash
# For user-level Ollama
ollama list

# Or via API
curl -s http://127.0.0.1:11434/api/tags | jq -r '.models[].name'
```

#### Common Models to Consider Pruning:

1. **llama3.2** (if present)
   - **Status**: 🔄 **CONSIDER REMOVING** - Superseded by Llama 4 Scout
   - **Reason**: Llama 4 Scout is more capable and uses MoE for efficiency
   - **Remove with**: `ollama rm llama3.2`

2. **llama3.1** (if present)
   - **Status**: 🗑️ **REMOVE** - Older generation
   - **Reason**: Both phi4 and Llama 4 Scout are superior
   - **Remove with**: `ollama rm llama3.1`

3. **llama3** (if present)
   - **Status**: 🗑️ **REMOVE** - Two generations old
   - **Reason**: Significantly outdated
   - **Remove with**: `ollama rm llama3`

4. **qwen2.5-coder** (if present)
   - **Status**: ⚠️ **CONDITIONAL** - Keep if you do coding tasks
   - **Reason**: Specialized for code, better than phi4 for coding
   - **Alternative**: Use DeepSeek-R1 via TGI (better reasoning for code)
   - **Remove with**: `ollama rm qwen2.5-coder` (if you prefer DeepSeek)

5. **mistral** or **mixtral** (if present)
   - **Status**: 🗑️ **REMOVE** - Superseded
   - **Reason**: phi4 and Llama 4 Scout are more capable
   - **Remove with**: `ollama rm mistral` or `ollama rm mixtral`

6. **codellama** (if present)
   - **Status**: 🗑️ **REMOVE** - Outdated for coding
   - **Reason**: qwen2.5-coder and DeepSeek-R1 are superior
   - **Remove with**: `ollama rm codellama`

## Recommended Model Lineup (Current State)

### For General Use:
- **phi4** (Ollama) - Fast, lightweight, good for quick tasks
- **DeepSeek-R1-Distill-Qwen-7B** (TGI) - Reasoning and deep thinking
- **Llama 4 Scout** (TGI) - Large tasks, high capability

### For Coding:
- **DeepSeek-R1-Distill-Qwen-7B** (TGI) - Best reasoning for code
- **qwen2.5-coder** (Ollama, if you kept it) - Fast code completion

## Pruning Commands

### Check Current Ollama Models:
```bash
ollama list
```

### Remove Individual Models:
```bash
# Remove old Llama versions
ollama rm llama3.2
ollama rm llama3.1
ollama rm llama3

# Remove old Mistral versions
ollama rm mistral
ollama rm mixtral

# Remove old code models (if not needed)
ollama rm codellama
```

### Check HuggingFace Cache Size:
```bash
# DeepSeek cache
du -sh /var/lib/huggingface/cache/

# Scout cache
du -sh /var/lib/huggingface-scout/cache/
```

### Manual HuggingFace Model Removal (if needed):
```bash
# CAUTION: Only do this if you want to re-download the model
sudo rm -rf /var/lib/huggingface/cache/models--deepseek-ai--DeepSeek-R1-Distill-Qwen-7B
sudo rm -rf /var/lib/huggingface-scout/cache/models--meta-llama--Llama-4-Scout-17B-16E

# Then restart services to re-download
sudo systemctl restart huggingface-tgi.service
sudo systemctl restart huggingface-tgi-scout.service
```

## Storage Savings Estimate

Assuming you had downloaded common outdated models:

| Model | Size | Action |
|-------|------|--------|
| llama3.2 | ~2GB | Remove → Save 2GB |
| llama3.1 | ~4GB | Remove → Save 4GB |
| qwen2.5-coder | ~3GB | Keep for coding OR remove → Save 3GB |
| mistral | ~4GB | Remove → Save 4GB |
| codellama | ~4GB | Remove → Save 4GB |

**Total Potential Savings**: 9-17GB depending on what you have installed

## Model Update Strategy

### When to Update Models:

1. **Ollama Models**:
   - Check for updates: `ollama list` shows version tags
   - Update manually: `ollama pull <model>`
   - Auto-prune old versions: Enabled in Podman config (weekly)

2. **TGI Models**:
   - Automatically download latest on service restart
   - Cache location: `/var/lib/huggingface/cache/`
   - Update by: `sudo systemctl restart huggingface-tgi.service`

### Best Practice:
- Keep only models you actively use
- Run `ollama list` monthly and remove unused models
- Monitor disk space: `df -h`
- Use `podman system prune -a --volumes` quarterly to clean up container layers

## Quick Cleanup Script

```bash
#!/usr/bin/env bash
# Quick AI model cleanup

echo "=== Ollama Models ==="
ollama list

echo ""
echo "Remove old models? (llama3.2, llama3.1, mistral)"
read -p "Continue? [y/N] " -n 1 -r
echo
if [[ $REPLY =~ ^[Yy]$ ]]; then
    ollama rm llama3.2 2>/dev/null || echo "llama3.2 not found"
    ollama rm llama3.1 2>/dev/null || echo "llama3.1 not found"
    ollama rm llama3 2>/dev/null || echo "llama3 not found"
    ollama rm mistral 2>/dev/null || echo "mistral not found"
    ollama rm mixtral 2>/dev/null || echo "mixtral not found"
    echo "Cleanup complete!"
fi

echo ""
echo "=== HuggingFace Cache Size ==="
du -sh /var/lib/huggingface/cache/ 2>/dev/null || echo "DeepSeek cache not found"
du -sh /var/lib/huggingface-scout/cache/ 2>/dev/null || echo "Scout cache not found"

echo ""
echo "=== Podman Cleanup ==="
echo "This will remove unused container images and volumes"
read -p "Run podman system prune? [y/N] " -n 1 -r
echo
if [[ $REPLY =~ ^[Yy]$ ]]; then
    podman system prune -a --volumes -f
    echo "Podman cleanup complete!"
fi
```

Save this as `cleanup-ai-models.sh`, make it executable, and run when needed.
