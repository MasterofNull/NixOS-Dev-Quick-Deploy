# Fine-Tuning Viability Research — Phase 4.1.1 / 4.1.2

**Machine:** ThinkPad P14s Gen 2a — AMD Ryzen, ~27 GB RAM, AMD iGPU (ROCm), no NVIDIA GPU
**Current model format:** GGUF (served by llama.cpp)
**Date:** 2026-02-25

---

## 4.1.1 — Toolchain Research

### Option A: `llama.cpp finetune` (native GGUF)

`llama.cpp` has a `finetune` subcommand that can perform LoRA adapter training
directly on GGUF weights.

| Aspect | Assessment |
|--------|-----------|
| ROCm support | HIP backend compiles; training path (`train-text-from-scratch`, `finetune`) lags behind inference; HIP training not officially validated |
| Memory (7B model) | Requires loading full weights in FP16 (~14 GB) plus activations; leaves ~11 GB free — marginal for any batch > 1 |
| Memory (13B model) | 26 GB FP16 — leaves ~1 GB; effectively OOM |
| Output format | Produces a GGUF LoRA adapter (`.gguf`) that can be fused at inference time with `--lora` flag |
| Tooling maturity | Experimental; training loss curves unstable; gradient checkpointing not implemented |
| Conclusion | Technically possible for 7B models; not production-ready on AMD ROCm as of 2026-02 |

### Option B: Unsloth

- **ROCm support: None.** Unsloth hard-requires CUDA (`triton` backend, CUDA kernels).
  AMD ROCm is explicitly unsupported. Eliminated.

### Option C: Axolotl

| Aspect | Assessment |
|--------|-----------|
| ROCm support | Yes, via `torch` + DeepSpeed ZeRO on ROCm. Requires `rocm/pytorch` Docker image or manual ROCm PyTorch build |
| Memory (7B LoRA, 4-bit QLoRA) | ~18-22 GB; fits in 27 GB with batch size 1–2 |
| Memory (13B QLoRA) | ~28 GB — exceeds available RAM; OOM without offload |
| GGUF round-trip | Must convert GGUF → safetensors (via `convert_hf_to_gguf.py`), train adapter, merge, re-quantize. Approximately 4 manual steps |
| NixOS integration | No Nix package; requires `pip install axolotl` inside a virtualenv or container; breaks reproducibility guarantee |
| Time per epoch (7B, 1000 examples, RTX-equivalent AMD) | ~45–90 min estimated on iGPU without dedicated VRAM |
| Conclusion | Technically feasible for 7B; NixOS integration is a significant barrier |

---

## 4.1.2 — Viability Decision

**Decision: Do NOT pursue on-device fine-tuning. Use RAG as the learning mechanism.**

### Rationale

1. **Hardware mismatch.** Fine-tuning benefits most from dedicated GPU VRAM. The
   ThinkPad P14s Gen 2a uses unified system RAM shared between CPU and AMD iGPU.
   Llama.cpp inference already uses ~16–20 GB for a 13B model; leaving ≤7 GB for
   training activations makes any useful batch size impossible without OOM.

2. **Reproducibility violation.** All three viable tools (llama.cpp finetune,
   axolotl, unsloth) require runtime pip installs not expressible as NixOS
   packages. A non-declarative training dependency breaks the core project constraint.

3. **Complexity vs. benefit.** The GGUF → safetensors → train → merge → requantize
   pipeline has 4+ manual steps, each with its own failure mode. For a personal
   one-machine setup producing ~50–200 high-value interactions per week, the
   signal-to-noise ratio is too low to justify this complexity.

4. **RAG already closes the loop.** Phase 3 implemented:
   - `query_gaps` table capturing low-confidence queries
   - `aq-gaps` digest surfacing what to import
   - `aq-rate` feedback loop recording what was useful
   These are sufficient for personalizing behavior without touching model weights.

5. **Off-device alternative.** If fine-tuning ever becomes necessary, export
   the JSONL interaction archive (`~/.local/share/nixos-ai-stack/interaction-archive/dataset.jsonl`)
   to a machine with a proper NVIDIA GPU, fine-tune there, and deploy the merged
   GGUF back via the NixOS model registry. No on-device pipeline needed.

### Consequence (Phase 4.1.3)

The `fine-tuning/` output directory has been renamed to `interaction-archive/`
in `server.py` and `Config.FINETUNE_DATA_PATH` now defaults to
`~/.local/share/nixos-ai-stack/interaction-archive/dataset.jsonl`.
The `generate_training_data` MCP tool is retained for archival/export use.
