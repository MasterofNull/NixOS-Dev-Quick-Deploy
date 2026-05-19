# MAEAH Hardware Validation — Gemini Findings
Date: 2026-05-19
Validator: Gemini (VP Eng) — standing in for Qwen3.6-35B

## Q1: Quant Tier Default
**AMEND**
While Q4_K_M (~22GB) fits in the 27GB physical RAM, the remaining 5GB headroom is **NOT sufficient** for a stable production environment including the OS, KV cache, and required services.
- **Model (35B Q4_K_XL):** ~22.5 GB.
- **KV Cache (16K ctx):** ~4.5 GB (assuming Q4 quantization).
- **OS + Services:** ~6 GB estimated (Open WebUI, Qdrant, Hybrid Coordinator, etc.).
- **Total Required:** ~33 GB.
The 5GB residual headroom would be immediately exhausted by the KV cache and OS baseline alone, leading to aggressive swapping or OOM kills. A safer default for 27GB RAM would be T1 (Q3_K_M ~17GB) to ensure reliable multi-agent operation.

## Q2: n_gpu_layers Ceiling
**CONFIRM**
A ceiling of **12 layers** is correct for reliable operation on the Renoir iGPU. 
- **Rationale:** Empirical data in `facts.nix` confirms that full 41-layer offload overruns the iGPU and causes OOM for inputs >400 tokens. 
- **Safety Margin:** Setting the ceiling at 12 ensures "reliable KV-cache headroom" (as per host comments). While 16 layers may be possible for short context/low RAM pressure, it risks `ErrorDeviceLost` under the heavy load of a 35B model on unified memory.

## Q5: UMBM Memory Budget
**AMEND**
The proposed budget of 18GB (llama.cpp) / 3GB (KV) / 6GB (OS) = 27GB is **incompatible** with the target model (Qwen3.6-35B ~22GB).
- **Inconsistency:** If llama.cpp is limited to 18GB, a 22.5GB GGUF model cannot be loaded.
- **Corrected Budget:** To run the 35B model, the budget must shift to approximately **22.5GB (LLM) / 2GB (KV) / 2.5GB (OS)**. 
- **Risk:** 2.5GB is insufficient for the current service stack (Open WebUI alone can exceed 1GB). The system is currently over-provisioned relative to its physical RAM.

## Q6: Quant Tier Ladder
**AMEND**
The quant tier ladder as described in the prompt is inverted and includes impossible tiers for this hardware.
- **Ladder Correction:** According to `COMBINED-PRD.md` §4, the ladder is T0 (Q2_K) to T5 (Q8_0). 
- **Hardware Compatibility:**
    - **T0-T2 (Q2_K to Q4_K_M):** Compatible but T2 is very tight.
    - **T3 (Q4_K_XL ~23GB):** Absolute upper limit; leaves <4GB for everything else.
    - **T4 (Q5_K_M ~28GB):** Physically impossible (exceeds 27GB).
    - **T5 (Q8_0 ~38GB):** Physically impossible.
- **Verdict:** The ladder is appropriate as a reference, but for a 27GB system, T4 and T5 must be explicitly marked as "Unusable" and T3 as "Risk: High".

## Summary
The current configuration is pushing the Renoir APU to its absolute physical limits. While the 35B model can "fit" into memory at Q4 quantization, there is effectively zero headroom for concurrent agent operations or large context windows without significant performance degradation. Recommend downshifting the default quant tier to T1 (Q3_K_M) for production stability, or strictly limiting context size if T2/T3 is required.
