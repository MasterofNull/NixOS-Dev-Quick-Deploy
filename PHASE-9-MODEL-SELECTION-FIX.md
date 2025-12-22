# Phase 9 Model Selection Fix
**Date**: 2025-12-20
**Issue**: Phase 9 showed 6+ model options when only 3 were downloaded
**Status**: ✅ FIXED

---

## Problem Identified

During Phase 9 (AI Model Deployment), the system was showing a menu with 6+ model options from the full registry, even though the user had already downloaded only 3 specific models earlier. This created confusion and violated the principle of treating the AI stack as a cohesive system.

### User Feedback

> "i though we already set the llm models with the list of three? why are we setting more models?"
>
> "please only give options for the llm that where downloaded, chossen, and listed from the previous user input in phase 1. you are adding too many complications when the choices and variables have already been set. pleae treat the ai podman stack as a cohesive system and don't just slap new steps onto the system without taking into account what has already been set, setup, and choosen."

### Root Cause

The `ai_select_model()` function in [lib/ai-optimizer.sh](lib/ai-optimizer.sh) was:
1. Showing a hardcoded menu with 6+ models from the full registry
2. Not checking which models were already downloaded
3. Not respecting previous user choices

This disconnect occurred because:
- `scripts/download-lemonade-models.sh` downloads 3 specific models
- Phase 9's menu showed 6+ options from `ai-stack/models/registry.json`
- No detection of cached models before displaying the menu

---

## Solution Applied

Modified [lib/ai-optimizer.sh](lib/ai-optimizer.sh) to detect cached models and only show those as options.

### New Functions Added

#### 1. `ai_detect_cached_models()`
**Purpose**: Detect which models are already downloaded in HuggingFace cache

**Location**: Lines 233-255

**Logic**:
```bash
ai_detect_cached_models() {
    local cache_dir="${HOME}/.cache/huggingface"
    declare -A cached_models

    # Check for qwen-coder (Qwen2.5-Coder-7B)
    if ls "${cache_dir}/models--Qwen--Qwen2.5-Coder-7B-Instruct-GGUF/snapshots/"*/qwen2.5-coder-7b-instruct-q4_k_m.gguf >/dev/null 2>&1; then
        cached_models[qwen-coder]="Qwen/Qwen2.5-Coder-7B-Instruct-GGUF"
    fi

    # Check for qwen3-4b (Qwen3-4B-Instruct)
    if ls "${cache_dir}/models--unsloth--Qwen3-4B-Instruct-2507-GGUF/snapshots/"*/Qwen3-4B-Instruct-2507-Q4_K_M.gguf >/dev/null 2>&1; then
        cached_models[qwen3-4b]="unsloth/Qwen3-4B-Instruct-2507-GGUF"
    fi

    # Check for deepseek (DeepSeek-Coder-6.7B)
    if ls "${cache_dir}/models--TheBloke--deepseek-coder-6.7B-instruct-GGUF/snapshots/"*/deepseek-coder-6.7b-instruct.Q4_K_M.gguf >/dev/null 2>&1; then
        cached_models[deepseek]="TheBloke/deepseek-coder-6.7B-instruct-GGUF"
    fi

    # Return the keys of cached models
    echo "${!cached_models[@]}"
}
```

**Returns**: Space-separated list of cached model keys (e.g., "qwen-coder qwen3-4b deepseek")

#### 2. `ai_display_cached_model_menu()`
**Purpose**: Display menu showing ONLY downloaded models

**Location**: Lines 257-310

**Features**:
- Shows numbered list (1, 2, 3) based on how many models are cached
- Displays model name, size, speed, and quality for each
- Shows "[0] Skip" option
- If no models cached: Shows message explaining models will download on startup

**Example Output** (3 models cached):
```
╭───────────────────────────────────────────────────────────────────────────╮
│ AI Model Selection (Lemonade)                                             │
│                                                                            │
│ The following models are already downloaded and ready to use:             │
│                                                                            │
│ [1] Qwen2.5-Coder-7B (Recommended)                                      │
│     - Size: 4.4GB  |  Speed: 40-60 tok/s  |  Quality: 88.4%               │
│ [2] Qwen3-4B-Instruct (Lightweight)                                     │
│     - Size: 2.3GB  |  Speed: 60-80 tok/s  |  Quality: 85%                 │
│ [3] DeepSeek-Coder-6.7B (Advanced reasoning)                            │
│     - Size: 3.8GB  |  Speed: 35-50 tok/s  |  Quality: 86%                 │
│                                                                            │
│ [0] Skip AI model deployment                                              │
╰───────────────────────────────────────────────────────────────────────────╯
```

#### 3. Modified `ai_select_model()`
**Purpose**: Use cached model detection instead of hardcoded menu

**Location**: Lines 312-361

**Changes**:
- Calls `ai_detect_cached_models()` to get list of cached models
- Passes cached list to `ai_display_cached_model_menu()`
- Validates selection against cached count (1-N instead of 1-6)
- Returns HuggingFace model ID for selected cached model
- Returns "SKIP" if user chooses [0] or no models cached

---

## Models Detected

The function detects these 3 models that were downloaded via `download-lemonade-models.sh`:

| Key | HuggingFace ID | Size | File Location |
|-----|----------------|------|---------------|
| **qwen-coder** | Qwen/Qwen2.5-Coder-7B-Instruct-GGUF | 4.4GB | ~/.cache/huggingface/models--Qwen--Qwen2.5-Coder-7B-Instruct-GGUF/snapshots/*/qwen2.5-coder-7b-instruct-q4_k_m.gguf |
| **qwen3-4b** | unsloth/Qwen3-4B-Instruct-2507-GGUF | 2.3GB | ~/.cache/huggingface/models--unsloth--Qwen3-4B-Instruct-2507-GGUF/snapshots/*/Qwen3-4B-Instruct-2507-Q4_K_M.gguf |
| **deepseek** | TheBloke/deepseek-coder-6.7B-instruct-GGUF | 3.8GB | ~/.cache/huggingface/models--TheBloke--deepseek-coder-6.7B-instruct-GGUF/snapshots/*/deepseek-coder-6.7b-instruct.Q4_K_M.gguf |

**Total Cached**: ~10.5GB

---

## Expected Behavior

### Before Fix
```
./nixos-quick-deploy.sh
↓
Phase 9: AI Model Deployment
↓
Menu shows 6+ options:
  [1] Qwen2.5-Coder-7B
  [2] Qwen2.5-Coder-14B
  [3] DeepSeek-Coder-V2-Lite
  [4] DeepSeek-Coder-V2
  [5] Phi-3-mini
  [6] CodeLlama-13B
  [c] Custom
  [0] Skip

❌ Problem: Options 2, 4, 5, 6 are NOT downloaded
❌ Problem: User confused - "why are we setting more models?"
```

### After Fix
```
./nixos-quick-deploy.sh
↓
Phase 9: AI Model Deployment
↓
Menu shows ONLY cached models:
  [1] Qwen2.5-Coder-7B (Recommended) - 4.4GB ✅ Cached
  [2] Qwen3-4B-Instruct (Lightweight) - 2.3GB ✅ Cached
  [3] DeepSeek-Coder-6.7B (Advanced reasoning) - 3.8GB ✅ Cached
  [0] Skip

✅ Only shows downloaded models
✅ Clear which models are ready to use
✅ User selects from models they already chose
```

---

## Benefits

✅ **Respects Previous Choices** - Only shows models user already downloaded
✅ **Cohesive System** - Phase 9 integrates with earlier model downloads
✅ **No Confusion** - Clear that these are ready-to-use cached models
✅ **No Extra Downloads** - User won't accidentally trigger new 10GB+ downloads
✅ **Better UX** - Simpler menu with only relevant options
✅ **Performance** - Uses cached models immediately (no download time)

---

## Files Modified

### 1. [lib/ai-optimizer.sh](lib/ai-optimizer.sh)

**Lines Modified**: 233-361

**Changes**:
1. Added `ai_detect_cached_models()` function (lines 233-255)
2. Added `ai_display_cached_model_menu()` function (lines 257-310)
3. Rewrote `ai_select_model()` to use detection (lines 312-361)

**Old Behavior**:
- Hardcoded menu with 6+ options
- No cache detection
- Offered models not downloaded

**New Behavior**:
- Dynamic menu based on cache
- Detects 3 downloaded models
- Only shows cached options

---

## Testing

### Verify Cached Models Detected
```bash
# Test the detection function
bash -c '
ai_detect_cached_models() {
    local cache_dir="${HOME}/.cache/huggingface"
    declare -A cached_models

    if ls "${cache_dir}/models--Qwen--Qwen2.5-Coder-7B-Instruct-GGUF/snapshots/"*/qwen2.5-coder-7b-instruct-q4_k_m.gguf >/dev/null 2>&1; then
        cached_models[qwen-coder]="Qwen/Qwen2.5-Coder-7B-Instruct-GGUF"
    fi

    if ls "${cache_dir}/models--unsloth--Qwen3-4B-Instruct-2507-GGUF/snapshots/"*/Qwen3-4B-Instruct-2507-Q4_K_M.gguf >/dev/null 2>&1; then
        cached_models[qwen3-4b]="unsloth/Qwen3-4B-Instruct-2507-GGUF"
    fi

    if ls "${cache_dir}/models--TheBloke--deepseek-coder-6.7B-instruct-GGUF/snapshots/"*/deepseek-coder-6.7b-instruct.Q4_K_M.gguf >/dev/null 2>&1; then
        cached_models[deepseek]="TheBloke/deepseek-coder-6.7B-instruct-GGUF"
    fi

    echo "${!cached_models[@]}"
}

ai_detect_cached_models
'

# Expected output: qwen-coder qwen3-4b deepseek
```

### Verify Phase 9 Menu (During Deployment)
```bash
./nixos-quick-deploy.sh

# When Phase 9 prompt appears, answer: Y
# Expected menu: Only 3 options (Qwen2.5-Coder-7B, Qwen3-4B-Instruct, DeepSeek-Coder-6.7B)
# Choose option 1 (Qwen2.5-Coder-7B) for best performance
```

---

## User Hardware Recommendation

**System**: AMD Ryzen 7 PRO 5850U with integrated Radeon Graphics (iGPU, no dedicated GPU)

**Best Model Choice**: **[1] Qwen2.5-Coder-7B**

**Reasoning**:
- ✅ Already cached (4.4GB)
- ✅ Best accuracy (88.4%)
- ✅ Good speed even on CPU (40-60 tok/s with GPU, 5-10 tok/s on CPU)
- ✅ Recommended for most users
- ⚠️ Will run on CPU (iGPU not powerful enough for inference)
- ⚠️ Expect slower inference (~5-10 tok/s on CPU vs 40-60 on GPU)

**Alternative**: **[2] Qwen3-4B-Instruct** (Lightweight)
- Smaller model (2.3GB)
- Faster on CPU (~10-15 tok/s)
- Slightly lower accuracy (85% vs 88.4%)

---

## Integration with Other Fixes

This fix works together with the other fixes applied in this session:

1. **Phase 9 Default** - AI stack prompt shown by default (no --with-ai-stack flag)
2. **Container Caching** - Downloaded models remain cached (no re-downloads)
3. **Model Pre-Download** - Models downloaded before Phase 9 menu appears
4. **Cohesive System** - All parts respect previous user choices

**Complete Flow**:
```
User runs: ./nixos-quick-deploy.sh
↓
Phase 3: Models download (qwen-coder, qwen3-4b, deepseek)
↓
Phase 9: Menu shows ONLY the 3 downloaded models
↓
User selects one → No additional download needed
↓
Lemonade starts with cached model immediately
```

---

## Rollback Instructions

If needed, restore the old menu behavior:

```bash
cd /home/hyperd/Documents/try/NixOS-Dev-Quick-Deploy

# Checkout previous version
git diff HEAD lib/ai-optimizer.sh  # Review changes
git checkout HEAD~1 lib/ai-optimizer.sh  # Restore old version
```

---

**Status**: ✅ Fix applied and ready for next deployment
**Next Step**: Run `./nixos-quick-deploy.sh` and verify Phase 9 menu shows only 3 options

**Expected Result**: Menu displays "The following models are already downloaded and ready to use" with 3 numbered options instead of 6+
