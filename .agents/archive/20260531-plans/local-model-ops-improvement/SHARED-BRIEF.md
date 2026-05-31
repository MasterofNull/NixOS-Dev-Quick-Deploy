# Local Model Operations Improvement — Shared Brief
**Date**: 2026-05-23  
**Claude role**: NixOS implementation, live diagnostics, Python fixes  
**Gemini role**: Monitoring framework design, evaluation schema, analysis patterns  
**Stack**: NixOS flake, llama.cpp b9222+, Qwen3.6-35B-A3B-MTP, 27GB RAM, Renoir APU 4GB VRAM

---

## Live System State (Claude-collected, 2026-05-23)

| Metric | Value | Status |
|--------|-------|--------|
| Generation TPS (reported) | 3.46 t/s | Low |
| MTP acceptance rate (derived) | **49%** | Untracked |
| Effective TPS (MTP-adjusted) | **~6.85 t/s** | Untracked |
| CPU temp | 74°C | WARN tier |
| GPU temp | 68°C | WARN |
| RAM used | 48.6% (13GB / 27GB) | OK |
| llama.cpp swap | **965 MB** | Pressure |
| vm.swappiness | 10 | Already tuned |
| KV cache ctx-size | 8192 | Constrained |
| n_gpu_layers | 12 (Renoir ceiling) | Correct |
| Flash attention | OFF | Intentional |
| MTP n_max | 2 | Tunable |
| Hints success rate | 24.2% (pre-fix) | Fixed 2026-05-23 |
| hint_adoption tracked | 0 entries | Fixed 2026-05-23 |
| metadata.backend tracked | 0% | Fixed 2026-05-23 |
| speculative_decoding_enabled (scorecard) | false | BUG |
| mtp_acceptance_rate (IPM) | null | BUG |
| n_gpu_layers_current (IPM) | 99 | BUG (should be 12) |
| semantic_tooling_autorun_enabled_pct | 0% | Investigate |
| Prompt cache hit rate | 78.9% | Healthy |
| Route retrieval breadth metadata | 33.8% | Low |

---

## Root Causes Found

### 1. MTP acceptance rate = null (IPM tracking bug)
IPM polls for `llm_spec_accept_rate` / `llama_speculative_acceptance_rate` in Prometheus output.
These metrics don't exist in this build of llama.cpp. MTP IS working — derived rate = 49%.
**Fix**: Derive from `llamacpp:tokens_predicted_total / llamacpp:n_decode_total` ratio.

### 2. speculative_decoding_enabled = false (scorecard bug)
Scorecard doesn't detect `--spec-type draft-mtp` from process cmdline.
**Fix**: Detect via `/proc/<pid>/cmdline` or llama.cpp `/props` endpoint.

### 3. n_gpu_layers_current = 99 (IPM proc parsing bug)
IPM parses n_gpu_layers from `/proc/<pid>/cmdline`. The process uses 
`--n-gpu-layers 12` but IPM is reading 99. Likely parsing the embed server or fallback.
**Fix**: Parse the correct llama-server PID cmdline.

### 4. 965MB model swap pressure
Despite vm.swappiness=10, 965MB of llama.cpp is swapped.
Cause: KV cache allocations during context expansion push model weights to swap.
**Fix option A**: Add `--mlock` flag to llama.cpp service (pins all allocations to RAM).
**Fix option B**: Reduce ctx-size to reduce KV pressure.
**Fix option C**: Enable huge pages for llama process.

### 5. semantic_tooling_autorun_enabled_pct = 0%
All 8541 route calls show autorun as disabled. May be a metadata tracking gap rather
than the feature being disabled — `AI_SEMANTIC_TOOLING_AUTORUN=true` in env.

---

## Work Division

### Claude (this session + next):
- [x] Fix hints sys.path pollution (commit 39c18849)
- [x] Fix aq-qa 62.1 nsjail detection
- [ ] Fix IPM `_fetch_mtp_rate`: derive from token ratio
- [ ] Fix IPM `n_gpu_layers_current`: parse correct PID
- [ ] Fix scorecard `speculative_decoding_enabled` detection
- [ ] Investigate semantic_tooling_autorun 0% anomaly
- [ ] Evaluate `--mlock` addition to llama.cpp service
- [ ] Expose derived MTP metrics via `/api/hardware/state`

### Gemini (framework design — feed results back via aq-chat):
- [ ] Design continuous inference monitoring schema (builds on generic framework above)
  - What to sample, at what frequency, retention policy
  - Alert thresholds for MTP acceptance rate degradation
- [ ] Design MTP tuning decision tree:
  - When to increase `--spec-draft-n-max` (3→4) 
  - Acceptance rate thresholds that justify increasing/decreasing
  - Temperature vs acceptance rate correlation
- [ ] Design ctx-size expansion analysis:
  - RAM budget formula: model_size + kv_cache(ctx) + OS_reserve
  - Safe ctx-size ceiling for our 27GB / 12GB model config
- [ ] Evaluate swap mlock tradeoffs:
  - mlock pros/cons for inference workload
  - Risk analysis: OOM if KV grows beyond locked budget

---

## Gemini Context to Copy Into aq-chat

Stack specifics for Gemini's custom analysis:
- **OS**: NixOS 25.05, flake-based, systemd services
- **Hardware**: Renoir APU (AMD), 8-core CPU, 4GB shared VRAM, 27GB RAM total
- **GPU layers**: Ceiling = 12 (VRAM constraint). Renoir ROCm = blocked (APU).
- **Model**: Qwen3.6-35B-A3B (MTP variant), UD-Q4_K_XL quant, ~22.5GB on disk
- **Inference**: llama.cpp b9222, `--spec-type draft-mtp --spec-draft-n-max 2`
- **Observed**: 3.46 TPS base, 49% MTP acceptance → ~6.85 effective TPS
- **Context**: `--ctx-size 8192` (training ctx = 262144), 78.9% prompt cache hit rate
- **Swap**: 965MB of model in swap despite vm.swappiness=10
- **Thermal**: CPU 74°C / GPU 68°C = WARN tier (throttles MLFQ concurrency)
- **KV cache**: 8192 ctx × 35B params → estimate ~2GB KV at current ctx

