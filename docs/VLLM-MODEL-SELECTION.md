# vLLM Model Selection Guide for NixOS-Dev-Quick-Deploy
# Version: 1.0.0
# Date: 2025-11-22

## Overview

This guide helps you select the best AI coding model for your laptop or desktop workstation based on November 2025 benchmarks and real-world performance data.

---

## Quick Selection Guide

### By GPU VRAM

| Your GPU | VRAM | Recommended Model | Parameters | Speed (tok/s) | Best For |
|----------|------|-------------------|------------|---------------|----------|
| **RTX 4060/4070** | 16GB | Qwen2.5-Coder-7B-Instruct | 7B | 40-60 | NixOS, general coding |
| **RTX 4070 Ti/4080** | 16-20GB | DeepSeek-Coder-V2-Lite | 16B | 20-30 | Advanced code generation |
| **RTX 4090** | 24GB | Qwen2.5-Coder-14B-Instruct | 14B | 30-45 | Best balance |
| **RTX 3090/A100** | 24-48GB | DeepSeek-Coder-V2 | 21B (236B total) | 15-25 | Enterprise workloads |
| **RTX 3060/4050** | 8-12GB | Phi-3-mini-4k-instruct | 3.8B | 60-80 | Lightweight testing |
| **Testing/CPU** | <8GB | Qwen2.5-Coder-1.5B | 1.5B | 20-40 | CPU-only development |

### By Use Case

| Use Case | Recommended Model | Why |
|----------|-------------------|-----|
| **NixOS Configuration** | Qwen2.5-Coder-7B | Excellent at structured data (Nix syntax) |
| **Python Development** | Qwen2.5-Coder-14B | Superior code completion |
| **Multi-language** | DeepSeek-Coder-V2 | Supports 300+ languages |
| **Math/Algorithms** | DeepSeek-Coder-V2-Lite | Enhanced logical reasoning |
| **Fast Iteration** | Phi-3-mini | 2x faster than larger models |
| **Production Quality** | Qwen2.5-Coder-32B | Best benchmarks (88.4% accuracy) |

---

## Model Comparison Matrix

### Qwen2.5-Coder Family (Alibaba Cloud, Sep 2024)

**Training:** 5.5 trillion tokens, 40+ programming languages, 128K context length

| Model | Parameters | VRAM | Speed | Benchmark | Notes |
|-------|-----------|------|-------|-----------|-------|
| **Qwen2.5-Coder-1.5B** | 1.5B | 4GB | Fast | 65% | CPU-friendly, basic tasks |
| **Qwen2.5-Coder-7B** | 7B | 16GB | 40-60 tok/s | 88.4% | **Best for laptops** |
| **Qwen2.5-Coder-14B** | 14B | 24GB | 30-45 tok/s | 89.7% | High-end workstations |
| **Qwen2.5-Coder-32B** | 32B | 48GB+ | 15-25 tok/s | 92.1% | Data center / multi-GPU |

**Strengths:**
- ✅ Best-in-class code completion
- ✅ Excellent at JSON, YAML, Nix (structured data)
- ✅ Multi-file code understanding
- ✅ Advanced debugging capabilities

**Weaknesses:**
- ⚠️ Newer model, less community testing
- ⚠️ Larger context requires more VRAM

**HuggingFace IDs:**
```bash
Qwen/Qwen2.5-Coder-1.5B-Instruct
Qwen/Qwen2.5-Coder-7B-Instruct      # Recommended
Qwen/Qwen2.5-Coder-14B-Instruct
Qwen/Qwen2.5-Coder-32B-Instruct
```

---

### DeepSeek Coder V2 Family (DeepSeek AI, June 2024)

**Training:** 1.17 trillion code tokens, 300+ programming languages, Mixture-of-Experts (MoE)

| Model | Parameters | Active | VRAM | Speed | Benchmark | Notes |
|-------|-----------|--------|------|-------|-----------|-------|
| **DeepSeek-Coder-V2-Lite** | 16B | 16B | 16-20GB | 20-30 tok/s | 81.1% | Solid all-around |
| **DeepSeek-Coder-V2** | 236B | 21B | 24GB+ | 15-25 tok/s | 84.5% | MoE efficiency |

**Strengths:**
- ✅ Advanced mathematical reasoning
- ✅ MoE architecture (efficient inference)
- ✅ 300+ language support
- ✅ Strong logical reasoning

**Weaknesses:**
- ⚠️ Lower benchmark than Qwen2.5-Coder
- ⚠️ Heavier VRAM usage

**HuggingFace IDs:**
```bash
deepseek-ai/DeepSeek-Coder-V2-Lite-Instruct
deepseek-ai/DeepSeek-Coder-V2-Instruct
```

---

### CodeLlama Family (Meta, 2023)

**Training:** Code-focused variant of LLaMA 2

| Model | Parameters | VRAM | Speed | Benchmark | Notes |
|-------|-----------|------|-------|-----------|-------|
| **CodeLlama-7b** | 7B | 14GB | 35-50 tok/s | 75% | Older, slower |
| **CodeLlama-13b** | 13B | 24GB | 20-35 tok/s | 78% | General purpose |
| **CodeLlama-34b** | 34B | 48GB+ | 10-20 tok/s | 81% | Legacy option |

**Strengths:**
- ✅ Well-tested, mature
- ✅ Good documentation
- ✅ Wide community support

**Weaknesses:**
- ⚠️ Outperformed by newer models
- ⚠️ Lower accuracy on benchmarks
- ⚠️ Slower than Qwen2.5-Coder

**HuggingFace IDs:**
```bash
codellama/CodeLlama-7b-Instruct-hf
codellama/CodeLlama-13b-Instruct-hf
codellama/CodeLlama-34b-Instruct-hf
```

---

### Phi-3-mini (Microsoft, 2024)

**Training:** 3.3 trillion tokens, compact architecture

| Model | Parameters | VRAM | Speed | Benchmark | Notes |
|-------|-----------|------|-------|-----------|-------|
| **Phi-3-mini-4k** | 3.8B | 8GB | 60-80 tok/s | 68% | Lightweight |

**Strengths:**
- ✅ Extremely fast inference
- ✅ Low VRAM requirements
- ✅ Good for quick prototyping
- ✅ CPU-compatible

**Weaknesses:**
- ⚠️ Lower code quality
- ⚠️ Limited context (4K tokens)
- ⚠️ Basic capabilities

**HuggingFace IDs:**
```bash
microsoft/Phi-3-mini-4k-instruct
```

---

## Performance Benchmarks (November 2025)

### HumanEval Benchmark

| Model | Pass@1 | Pass@10 | Ranking |
|-------|--------|---------|---------|
| **Qwen2.5-Coder-32B** | 92.1% | 97.5% | 🥇 #1 Open Source |
| **Qwen2.5-Coder-14B** | 89.7% | 95.2% | 🥈 #2 |
| **Qwen2.5-Coder-7B** | 88.4% | 93.8% | 🥉 #3 |
| DeepSeek-Coder-V2 | 84.5% | 91.2% | #4 |
| DeepSeek-Coder-V2-Lite | 81.1% | 88.5% | #5 |
| CodeLlama-34b | 81.0% | 87.9% | #6 |
| CodeLlama-13b | 78.2% | 85.1% | #7 |
| Phi-3-mini | 68.3% | 78.5% | #8 |

### Speed Comparison (Tokens/Second on RTX 4090)

| Model | Speed | Latency (first token) |
|-------|-------|----------------------|
| Phi-3-mini | 60-80 tok/s | 150ms |
| Qwen2.5-Coder-7B | 40-60 tok/s | 200ms |
| Qwen2.5-Coder-14B | 30-45 tok/s | 300ms |
| DeepSeek-Coder-V2-Lite | 20-30 tok/s | 400ms |
| DeepSeek-Coder-V2 | 15-25 tok/s | 500ms |
| CodeLlama-13b | 20-35 tok/s | 350ms |

---

## Recommended Configurations

### Option 1: Best for Most Users (Qwen2.5-Coder-7B)

```bash
# .env configuration
VLLM_MODEL=Qwen/Qwen2.5-Coder-7B-Instruct
VLLM_GPU_MEM=0.85
VLLM_MAX_LEN=8192
VLLM_TP_SIZE=1
VLLM_GPU_COUNT=1

# Expected performance:
# - VRAM: 14-16GB
# - Speed: 40-60 tok/s
# - Quality: 88.4% accuracy
# - Download: ~14GB
```

**Why This Model:**
- Perfect balance of speed, quality, and VRAM usage
- Works on most modern GPUs (RTX 3060 Ti and up)
- Excellent at NixOS configuration generation
- Fast enough for interactive development

---

### Option 2: Maximum Quality (Qwen2.5-Coder-14B)

```bash
# .env configuration
VLLM_MODEL=Qwen/Qwen2.5-Coder-14B-Instruct
VLLM_GPU_MEM=0.85
VLLM_MAX_LEN=8192
VLLM_TP_SIZE=1
VLLM_GPU_COUNT=1

# Expected performance:
# - VRAM: 22-24GB
# - Speed: 30-45 tok/s
# - Quality: 89.7% accuracy
# - Download: ~28GB
```

**Why This Model:**
- Best quality available for single-GPU workstations
- Requires RTX 4090 or equivalent (24GB VRAM)
- Still fast enough for development work
- Top-tier code generation

---

### Option 3: Lightweight/Testing (Phi-3-mini)

```bash
# .env configuration
VLLM_MODEL=microsoft/Phi-3-mini-4k-instruct
VLLM_GPU_MEM=0.75
VLLM_MAX_LEN=4096
VLLM_TP_SIZE=1
VLLM_GPU_COUNT=1

# Expected performance:
# - VRAM: 6-8GB
# - Speed: 60-80 tok/s
# - Quality: 68% accuracy
# - Download: ~7GB
```

**Why This Model:**
- Works on budget GPUs (RTX 3060, 4050)
- Extremely fast for quick prototyping
- Good for testing the infrastructure
- CPU-compatible for development

---

### Option 4: Advanced Reasoning (DeepSeek-Coder-V2-Lite)

```bash
# .env configuration
VLLM_MODEL=deepseek-ai/DeepSeek-Coder-V2-Lite-Instruct
VLLM_GPU_MEM=0.85
VLLM_MAX_LEN=8192
VLLM_TP_SIZE=1
VLLM_GPU_COUNT=1

# Expected performance:
# - VRAM: 18-20GB
# - Speed: 20-30 tok/s
# - Quality: 81.1% accuracy
# - Download: ~32GB
```

**Why This Model:**
- Best mathematical and logical reasoning
- Good for algorithm development
- Supports 300+ programming languages
- MoE efficiency advantage

---

## Model Selection Workflow

```
┌─────────────────────────────────────┐
│ What GPU do you have?               │
└─────────────┬───────────────────────┘
              │
       ┌──────┴──────┐
       │ VRAM Check  │
       └──────┬──────┘
              │
    ┌─────────┴─────────┐
    │                   │
┌───▼───┐         ┌─────▼─────┐
│ <16GB │         │   >=16GB  │
└───┬───┘         └─────┬─────┘
    │                   │
    │              ┌────┴────┐
    │              │ Use Case│
    │              └────┬────┘
    │                   │
    │        ┌──────────┼──────────┐
    │        │          │          │
    │   ┌────▼───┐ ┌───▼────┐ ┌───▼────┐
    │   │NixOS/  │ │Multi-  │ │Math/   │
    │   │Coding  │ │Language│ │Logic   │
    │   └────┬───┘ └───┬────┘ └───┬────┘
    │        │          │          │
┌───▼────┐ ┌▼──────┐  ┌▼───────┐ ┌▼────────┐
│Phi-3   │ │Qwen2.5│  │Qwen2.5 │ │DeepSeek │
│mini    │ │7B     │  │14B     │ │V2-Lite  │
└────────┘ └───────┘  └────────┘ └─────────┘
```

---

## Installation in NixOS-Dev-Quick-Deploy

### Phase 1: Model Selection Prompt

The deployment script will now prompt for model selection:

```bash
╭───────────────────────────────────────────────────────────╮
│ AI Model Selection (vLLM)                                 │
│                                                            │
│ Select the AI coding model for your workstation:          │
│                                                            │
│ [1] Qwen2.5-Coder-7B (Recommended)                        │
│     - VRAM: 14-16GB                                        │
│     - Speed: 40-60 tok/s                                   │
│     - Quality: 88.4%                                       │
│     - Best for: NixOS, general coding                      │
│                                                            │
│ [2] Qwen2.5-Coder-14B (High Quality)                      │
│     - VRAM: 22-24GB                                        │
│     - Speed: 30-45 tok/s                                   │
│     - Quality: 89.7%                                       │
│     - Best for: Production workloads                       │
│                                                            │
│ [3] DeepSeek-Coder-V2-Lite (Advanced Reasoning)           │
│     - VRAM: 18-20GB                                        │
│     - Speed: 20-30 tok/s                                   │
│     - Quality: 81.1%                                       │
│     - Best for: Algorithms, math                           │
│                                                            │
│ [4] Phi-3-mini (Lightweight)                              │
│     - VRAM: 6-8GB                                          │
│     - Speed: 60-80 tok/s                                   │
│     - Quality: 68%                                         │
│     - Best for: Testing, budget GPUs                       │
│                                                            │
│ [5] Custom (specify HuggingFace model ID)                 │
│                                                            │
│ [0] Skip AI model installation                            │
│                                                            │
╰───────────────────────────────────────────────────────────╯

Your GPU: RTX 4090 (24GB VRAM detected)
Recommended: [1] Qwen2.5-Coder-7B or [2] Qwen2.5-Coder-14B

Select option [0-5]:
```

### Phase 2: GPU Detection

```bash
# Auto-detect GPU and suggest appropriate model
detect_gpu_vram() {
    local vram_gb=0

    if command -v nvidia-smi &> /dev/null; then
        vram_gb=$(nvidia-smi --query-gpu=memory.total --format=csv,noheader,nounits | head -1 | awk '{print int($1/1024)}')
    fi

    if [ "$vram_gb" -ge 24 ]; then
        echo "Qwen/Qwen2.5-Coder-14B-Instruct"
    elif [ "$vram_gb" -ge 16 ]; then
        echo "Qwen/Qwen2.5-Coder-7B-Instruct"
    elif [ "$vram_gb" -ge 12 ]; then
        echo "deepseek-ai/DeepSeek-Coder-V2-Lite-Instruct"
    else
        echo "microsoft/Phi-3-mini-4k-instruct"
    fi
}
```

---

## Model Download Times

Approximate download times on 1 Gbps connection:

| Model | Size | Download Time |
|-------|------|---------------|
| Phi-3-mini | ~7GB | 5-10 minutes |
| Qwen2.5-Coder-7B | ~14GB | 10-20 minutes |
| DeepSeek-Coder-V2-Lite | ~32GB | 25-40 minutes |
| Qwen2.5-Coder-14B | ~28GB | 20-35 minutes |
| DeepSeek-Coder-V2 | ~200GB | 2-3 hours |

**First-time deployment:** Budget 15-45 minutes for model download depending on your selection.

---

## Troubleshooting

### Out of Memory (OOM) Errors

```bash
# Symptom: vLLM container crashes with OOM
# Solution: Reduce GPU memory utilization

# Edit .env:
VLLM_GPU_MEM=0.75  # Down from 0.85
VLLM_MAX_LEN=4096  # Down from 8192

# Restart:
docker compose -f docker-compose.new.yml restart vllm
```

### Slow Inference

```bash
# Symptom: <10 tok/s on decent hardware
# Cause: Model too large for GPU

# Solution: Switch to smaller model
VLLM_MODEL=Qwen/Qwen2.5-Coder-7B-Instruct  # Down from 14B
```

### Model Download Stuck

```bash
# Check download progress
docker logs -f vllm-inference

# If stuck, clear cache and retry
docker volume rm vllm-models
docker compose -f docker-compose.new.yml up -d vllm
```

---

## Future Models to Watch

### Q1 2026

- **Qwen3-Coder** (Expected: Jan 2026)
  - Rumored 50B+ parameter flagship
  - 95%+ HumanEval accuracy
  - Multi-modal code understanding

- **DeepSeek-Coder-V3** (Expected: Feb 2026)
  - Enhanced MoE architecture
  - Better NixOS/functional language support

### Community Developments

- **Fine-tuned Nix models** based on Qwen2.5-Coder
- **Domain-specific models** for infrastructure-as-code

---

## Skill Metadata

- **Skill Version**: 1.0.0
- **Last Updated**: 2025-11-22
- **Compatibility**: NixOS 23.11+, CUDA 12.0+
- **Category**: ai-infrastructure, model-selection
- **Tags**: vllm, qwen, deepseek, coding-models, ai-selection
