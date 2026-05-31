# PRD: Edge AI Specialist — Multi-Agent Edge AI Harness
> Author: Qwen3.6-35B (proxy authored by Claude Sonnet 4.6 on behalf of Qwen)
> Role: Edge AI Specialist / Hardware Optimization Lead
> Date: 2026-05-19 · Version: 1.0
> Status: PROXY — Qwen model offline (new model downloading). To be reviewed and amended
>         by Qwen when model load completes. Qwen's sign-off required before plan finalisation.
> Exercise: Greenfield design — independent of current system

---

## Proxy Author Note

Qwen3.6-35B is the primary local inference model for this project and holds unique authority on
edge inference constraints — it *is* the edge model being orchestrated. This PRD is authored as a
proxy using domain knowledge from the 7-pass research corpus. Qwen must review, challenge, and
amend this PRD before the combined PRD is finalised. Specifically, Qwen should validate:
- All quantization performance claims against its own observed token rates
- The thermal budget estimates (Qwen runs on the exact target hardware)
- The n-gpu-layers trade-off analysis (Qwen experienced the ErrorDeviceLost at 41 layers)
- MTP draft model viability claims

---

## 1. Executive Summary

The edge inference layer is where the entire multi-agent harness lives or dies. Every architectural
decision upstream — scheduling, memory management, protocol choice, model routing — is irrelevant
if the inference engine itself is misconfigured for the hardware. This PRD focuses exclusively on
making inference correct, efficient, and thermally sustainable on constrained hardware, then works
upward from that foundation.

**Central thesis**: the harness must be hardware-honest. Most agent OS designs are written for
cloud GPUs and retrofitted to edge devices. This PRD writes for the Renoir APU, the ThinkPad
thermal envelope, and unified VRAM — and generalises upward to more capable hardware, not downward.

**Primary contribution**: a quantization-tier lifecycle system that dynamically selects inference
parameters based on real-time thermal state, workload class, and memory pressure — invisible to
the agent application layer.

---

## 2. Problem Statement (Edge AI Specialist Lens)

### 2.1 The Hardware Reality Gap

Every design paper cited in our research (AIOS, AgentRM, HiveMind, Agent.xpu) was benchmarked on
hardware with dedicated GPU memory — A100s, H100s, M4 Pro, Jetson Xavier. Our primary target is a
**Renoir APU**: shared CPU+GPU memory, no discrete VRAM, 27 GB total RAM, iGPU with Vulkan partial
offload. Key constraints:

- **Unified memory**: VRAM and RAM compete. Every GB allocated to n-gpu-layers is unavailable for
  KV cache, agent working memory, and OS. The correct `--n-gpu-layers` value is a dynamic variable,
  not a config constant.
- **Thermal ceiling**: sustained inference at full GPU offload causes junction temps >85°C within
  minutes (arXiv:2504.03360). The APU's power budget (~15–28W TDP) cannot sustain peak compute
  indefinitely. Our observed behaviour: `--n-gpu-layers 41` → ErrorDeviceLost within seconds.
  `--n-gpu-layers 12` → stable but half the theoretical throughput.
- **Quantization is the primary knob**: on this hardware, quantization level affects: model size
  (fits in RAM or not), inference speed (tokens/sec), quality (perplexity), and thermal load.
  These four dimensions cannot be optimised simultaneously. The right quant depends on the task.
- **MTP (Multi-Token Prediction)**: draft-based speculative decoding (`--spec-type draft-mtp`)
  can yield 1.5–2.5× effective throughput when the draft acceptance rate >65%. On low-complexity
  tasks (code completion, structured output) this is achievable. On open-ended generation it is not.

### 2.2 The Static Configuration Problem

Current systems configure inference once at deploy time:
```
--n-gpu-layers 12 --threads 8 --ctx-size 8192 --flash-attn
```

This is correct for one workload type at one thermal state. It is wrong for:
- A coding agent that needs 32K context (ctx-size wrong)
- A background crystallisation task where throughput matters more than latency (n-gpu-layers wrong)
- A system under thermal stress where the current config causes throttling (n-gpu-layers wrong)
- A model swap where the new model is larger/smaller and the same params cause OOM or underutilisation

### 2.3 The Quantization Format Proliferation Problem

Four formats are in production use (GGUF, GPTQ, AWQ, EXL2). Each has a different runtime requirement.
On CPU+iGPU hybrid hardware, **only GGUF is universally viable** — the others require CUDA.
Yet model catalogs mix formats without hardware-target tags, leading to download of models that
cannot run on the target device.

---

## 3. Goals & Non-Goals

### Goals
- **G1**: Dynamic inference parameter selection: n-gpu-layers, ctx-size, batch-size, and quant tier
  adjust per workload class and thermal state automatically
- **G2**: Thermal budget enforcement: inference halted or throttled before hardware protection kicks
  in; proactive not reactive
- **G3**: MTP (speculative decoding) integration: automatic enable/disable based on task type and
  acceptance rate monitoring
- **G4**: Format-safe model catalog: every model entry tagged with `hardware_targets` and
  `runtime_requirements`; incompatible formats rejected at download time, not at load time
- **G5**: GGUF quantization tier ladder: Q2_K → Q3_K_M → Q4_K_M → Q4_K_XL → Q5_K_M → Q8_0,
  traversable dynamically at runtime
- **G6**: Unified memory budget manager: tracks RAM allocation across model weights, KV cache,
  agent working memory, and OS; enforces per-component ceilings
- **G7**: Cold-start minimisation: mmap-friendly model layout, page-in on first use; llama.cpp
  mmap already supports this — harness must not defeat it with unnecessary file copies
- **G8**: Graceful degradation: if optimal config fails (OOM, ErrorDeviceLost), auto-retry with
  reduced parameters before surfacing error to scheduler

### Non-Goals
- **NG1**: CUDA-specific optimisations (GPTQ/AWQ runtime paths) — out of scope for v1 on APU
- **NG2**: Multi-node split inference in v1 — single-node inference only; mesh coordination deferred
- **NG3**: On-device fine-tuning — inference harness only
- **NG4**: Batch inference optimisation (Continuous Batching, PagedAttention) — llama.cpp handles
  this internally; we configure, not reimplement

---

## 4. Architecture Proposal

### 4.1 Inference Parameter Manager (IPM)

The IPM sits between the scheduler and llama.cpp. It translates abstract workload descriptors into
concrete inference parameters.

```
Scheduler Request
  {
    workload_class: "reactive" | "proactive" | "batch",
    task_type: "chat" | "code" | "structured" | "embedding",
    priority: 0–3,
    ctx_required: int,
    quality_floor: "high" | "medium" | "low"
  }
        │
        ▼
[Inference Parameter Manager]
  reads: thermal_state, ram_budget, current_quant_tier, acceptance_rate (MTP)
  outputs: {
    n_gpu_layers: int,      # 0–41 on Renoir
    ctx_size: int,          # 2048–65536
    batch_size: int,        # 1–512
    flash_attn: bool,
    mmap: bool,
    mtp_enabled: bool,
    mtp_draft_n: int,       # 1–4
    threads: int,
    numa: bool
  }
        │
        ▼
[llama.cpp server] ← parameters applied at session level or via restart-with-config
```

### 4.2 Quantization Tier Ladder

```
TIER  QUANT     SIZE(35B)  TOKENS/SEC  QUALITY   THERMAL  USE CASE
T0    Q2_K      ~14 GB     ~8 t/s      degraded  low      emergency fallback only
T1    Q3_K_M    ~17 GB     ~6 t/s      fair      medium   background batch tasks
T2    Q4_K_M    ~22 GB     ~4.5 t/s   good      medium+  default; daily driver
T3    Q4_K_XL   ~23 GB     ~4.2 t/s   better    medium+  coding, reasoning (Unsloth calibrated)
T4    Q5_K_M    ~28 GB     ~3.2 t/s   high      high     quality-critical tasks (needs 28GB free)
T5    Q8_0      ~38 GB     N/A         ref       N/A      doesn't fit on P14s — never use
```

**Tier selection policy**:
```
if thermal > T_critical:        → T1 (emergency throttle)
if thermal > T_warn:            → T2 (back off one tier)
if task == "batch" and RAM_free < 4GB:  → T1
if task == "code" or task == "structured": → T3 (Q4_K_XL — Unsloth calibrated)
if quality_floor == "high":     → T4 if RAM_free > 30GB, else T3
default:                        → T2 (Q4_K_M)
```

### 4.3 n-gpu-layers Dynamic Policy

```
RAM budget available for GPU offload = total_ram - model_weights - kv_cache_budget - os_reserve
  = 27GB - 22GB - 2GB - 2GB ≈ 1GB headroom (tight)

Renoir iGPU characteristics:
  - Each GPU layer ≈ ~100–200 MB depending on model width
  - Layers 0-11: safe on Renoir (validated: 12 layers stable)
  - Layers 12-28: depends on RAM_free at session start
  - Layers 29-41: ErrorDeviceLost risk (observed); never exceed 28 on Renoir
  - Sweet spot: 8–16 layers; 12 is empirically validated default

Dynamic policy:
  reactive task, RAM_free > 3GB:    n_gpu_layers = 16
  reactive task, RAM_free 1–3GB:    n_gpu_layers = 12  (validated default)
  reactive task, RAM_free < 1GB:    n_gpu_layers = 8
  proactive/batch task:             n_gpu_layers = 8   (leave GPU headroom for reactive preemption)
  thermal > T_warn:                 n_gpu_layers = max(4, current - 4)  (step down)
  ErrorDeviceLost recovery:         n_gpu_layers = current - 4, retry once
```

### 4.4 MTP (Speculative Decoding) Manager

From current deployment: `--spec-type draft-mtp --spec-draft-n-max 2` with Unsloth MTP model.

```
MTP acceptance rate monitoring:
  - Track per-request: draft_tokens_proposed / draft_tokens_accepted
  - Window: rolling 50-request average
  - acceptance_rate_threshold = 0.65

MTP enable policy:
  task_type in ["code", "structured_output", "json_schema"]:
    if acceptance_rate > 0.65: spec_draft_n = 2
    if acceptance_rate > 0.75: spec_draft_n = 3 (try bump)
    if acceptance_rate > 0.80: spec_draft_n = 4 (max)
  task_type in ["chat", "reasoning", "open_ended"]:
    spec_draft_n = 1 (minimal; acceptance usually <0.5 for free text)
  thermal > T_warn:
    spec_draft_n = 0  (disable; draft model adds thermal load)
```

### 4.5 Unified Memory Budget Manager (UMBM)

Single source of truth for all memory allocations on the node:

```
UMBM tracks:
  model_weights_mmap:   GB      # mapped but not necessarily resident
  model_weights_active: GB      # actually paged in
  kv_cache_active:      GB      # llama.cpp KV cache
  kv_cache_staged:      GB      # Q4 KV caches on disk (not in RAM)
  agent_working_mem:    GB      # per-agent episodic + semantic query results
  os_reserve:           GB      # 2GB hard floor, never allocated below
  download_buffer:      GB      # pre-downloading model (background)

Allocation policy:
  Priority: os_reserve > model_weights_active > kv_cache_active > agent_working_mem > download_buffer

  On memory pressure:
    1. Evict lowest-priority agent working memory (AMV-L policy)
    2. Spill KV caches to Q4 disk (persistent KV cache manager)
    3. Reduce download_buffer bandwidth (throttle background download)
    4. Reduce n_gpu_layers (IPM policy update)
    5. NEVER: let OS OOM killer run on inference process
```

### 4.6 Thermal Monitor Integration

```
Sources (NixOS):
  /sys/class/hwmon/hwmon*/temp*_input  ← CPU/GPU junction temp
  /sys/class/thermal/thermal_zone*/temp ← thermal zones

Sampling: 500ms interval (async, non-blocking)

Thresholds (AMD Renoir):
  T_optimal:  <70°C   → full params
  T_warn:     70–80°C → step down tier + n_gpu_layers
  T_critical: 80–85°C → emergency throttle (T1 quant, n_gpu_layers=4)
  T_shutdown: >88°C   → SIGSTOP llama.cpp; cool-down timer; resume at T_optimal

Proactive scheduling gaps:
  After sustained inference >10min: insert 30s idle gap before next proactive task
  Reactive tasks: always accepted (user-facing; acceptable brief spike)
```

### 4.7 Interface Contracts

**IPM → Kernel Scheduler** (upward notification):
```json
{
  "thermal_state": "optimal|warn|critical|shutdown",
  "ram_pressure": "low|medium|high|critical",
  "effective_throughput_tps": 4.2,
  "mtp_acceptance_rate": 0.71,
  "active_quant_tier": "T3",
  "n_gpu_layers_current": 12,
  "recommended_concurrency_limit": 2
}
```

**Scheduler → IPM** (workload descriptor):
```json
{
  "workload_class": "reactive",
  "task_type": "code",
  "priority": 0,
  "ctx_required": 16384,
  "quality_floor": "high",
  "mtp_hint": true
}
```

**IPM → llama.cpp** (parameter set):
```json
{
  "n_gpu_layers": 14,
  "ctx_size": 16384,
  "batch_size": 256,
  "flash_attn": true,
  "mmap": true,
  "spec_type": "draft-mtp",
  "spec_draft_n_max": 3,
  "threads": 8,
  "cache_type_k": "q4_0",
  "cache_type_v": "q4_0"
}
```

---

## 5. Model Management (Pre-Download + Hot-Swap)

### 5.1 Format Validation at Download Time

Before downloading any model:
```python
def validate_model_for_hardware(catalog_entry, hardware_profile):
    format = catalog_entry["format"]
    hardware_targets = catalog_entry["hardware_targets"]

    # Hard block: wrong format for hardware
    if format == "gptq" and "cuda" not in hardware_profile["accelerators"]:
        raise IncompatibleFormatError("GPTQ requires CUDA; target has no CUDA")
    if format == "awq" and "cuda" not in hardware_profile["accelerators"]:
        raise IncompatibleFormatError("AWQ requires CUDA; target has no CUDA")

    # RAM check
    if catalog_entry["size_gb"] > hardware_profile["ram_gb"] * 0.85:
        raise InsufficientMemoryError(f"Model {size}GB exceeds 85% of {ram}GB RAM")

    # Tier assignment
    quant = catalog_entry["quant"]
    catalog_entry["assigned_tier"] = QUANT_TIER_MAP[quant]
    return catalog_entry
```

### 5.2 Pre-Download Strategy

- **Bandwidth throttling**: background download limited to 25% of available I/O to avoid interfering with active KV cache spills
- **Chunk verification**: SHA256 checked per 256MB chunk; partial downloads resumable
- **Staging location**: `/var/lib/ai-stack/models/staged/` — separate filesystem from active models
- **Eviction policy**: staged models expire after 7 days if not promoted; configurable

### 5.3 Hot-Swap Sequence (Edge-Specific)

Standard hot-swap (GPU checkpoint from SwapServeLLM) requires CUDA. On Renoir APU (Vulkan only):

```
EDGE HOT-SWAP SEQUENCE (no CUDA checkpoint):

1. NOTIFY IPM:   Mark thermal budget as "swap_in_progress" → pause proactive tasks
2. DRAIN:        Stop new request admission; drain in-flight (timeout 30s)
3. FLUSH KV:     Write all active KV caches to Q4 disk (UMBM coordinates)
4. STOP llama:   SIGTERM llama.cpp server; wait for clean exit (timeout 10s)
5. FLIP SYMLINK: atomic: /var/lib/ai-stack/models/active → staged model path
6. START llama:  Launch with new model + IPM-computed parameters
   - mmap=true: model pages in on first access (no full load wait)
   - First request triggers warm-up; UX shows "loading" state
7. HEALTH CHECK: GET /health with 60s timeout; verify inference with probe query
8. RESTORE KV:   Reload staged Q4 KV caches for active agent sessions
9. RESUME:       Scheduler accepts new work; IPM resumes thermal monitoring

Downtime (Renoir, no CUDA): ~15–25s (dominated by llama.cpp startup + first-page-in)
Downtime (CUDA-capable):     ~2–5s  (GPU checkpoint restore)

Mitigation for long downtime on CPU-only path:
  - Queue requests during swap; release queue on RESUME (buffer up to 60s of requests)
  - Dashboard shows countdown + queue depth
  - User-visible: "Model updating — your request is queued (position N)"
```

### 5.4 Rollback Trigger Conditions

```
Auto-rollback if within 5 minutes of swap:
  - Health check timeout (>60s)
  - First 10 inference requests have avg_tokens_per_sec < 50% of previous model's baseline
  - ErrorDeviceLost during first 5 requests
  - OOM during model load

Rollback procedure: mirror swap sequence with previous model from archive
Archive retention: keep 2 previous model versions; older evicted
```

### 5.5 Dashboard Integration

- **Hardware compatibility badge** per model: green (native GGUF), yellow (format convert needed), red (incompatible)
- **Thermal state indicator** during swap: shows if swap was blocked pending cool-down
- **Live param display**: current n_gpu_layers, quant tier, MTP acceptance rate
- **Tier history graph**: quant tier and n_gpu_layers over time (shows thermal correlation)
- **Swap log**: full audit trail with timestamps, trigger, downtime, rollback events

---

## 6. Key Design Decisions

| Decision | Choice | Rationale |
|----------|--------|-----------|
| Inference config | Dynamic via IPM | Fixed config is wrong for multi-workload systems; thermal state changes params at runtime |
| n_gpu_layers | 12 default, dynamic 4–16 | Empirically validated on Renoir; ErrorDeviceLost at full offload |
| Primary quant | GGUF Q4_K_XL (Unsloth) | Best perplexity at 4bpw for CPU+iGPU hybrid; calibrated quant outperforms standard Q4_K_M |
| MTP | Enable on code/structured; monitor acceptance | 1.5–2× throughput when acceptance >65%; thermal-aware disable |
| Thermal sampling | 500ms async, proactive throttle | APU loses 50% throughput past 85°C; proactive > reactive |
| Format validation | At download, not load | Fail fast; don't consume hours of download bandwidth on incompatible format |
| KV cache on swap | Flush to Q4 disk before stop | Enables context restore post-swap; agent sessions survive model upgrade |
| CPU-only swap path | Queue-buffered (no GPU checkpoint) | No CUDA on Renoir; 15–25s swap is acceptable with queue buffer |
| Unified memory budget | Single UMBM | Prevents OOM races between model weights, KV cache, and download buffer |

---

## 7. Risks & Mitigations

| Risk | Severity | Mitigation |
|------|----------|------------|
| ErrorDeviceLost on new model (different architecture) | High | Validate n_gpu_layers ceiling for new model at staging; IPM has per-model-family overrides |
| Thermal spike during swap (two models partially loaded) | High | IPM marks "swap_in_progress"; reduces n_gpu_layers during transition; thermal guard blocks swap if T > T_warn |
| KV cache disk flush too slow (blocks drain) | Medium | NVMe preferred; async flush with timeout; if flush fails, proceed with swap (context lost; agent notified) |
| MTP draft model stale (pre-downloaded base model changed) | Medium | Draft model version locked to base model version in catalog; mismatch → MTP disabled, alert raised |
| n_gpu_layers IPM recommendation wrong for new model size | Medium | Catalog includes recommended_gpu_layers field from benchmarking at upload time; IPM uses as floor |
| UMBM accounting drift (mmap pages not tracked accurately) | Low | Periodic reconciliation against /proc/meminfo; alerts on >500MB drift |
| Quantization calibration data mismatch | Low | Unsloth UD-Q4_K_XL calibrated on Qwen3 tokenizer; for other model families, fall back to standard Q4_K_M |

---

## 8. Research Citations Used

| Paper | Where Used |
|-------|-----------|
| arXiv:2504.03360 (Sustainable LLM Inference Energy) | Thermal constraint analysis; 50% throughput loss; DVFS |
| arXiv:2603.04428 (Persistent Q4 KV Cache) | KV flush-to-disk during swap; restore after swap |
| arXiv:2506.24045 (Agent.xpu) | Reactive vs proactive workload classification for n_gpu_layers policy |
| arXiv:2601.14277 (GGUF Quant Evaluation) | Q4_K_M and Q5_K_M as Pareto points; Q2_K degradation |
| SwapServeLLM SC'25 | GPU checkpoint approach; CPU-only fallback rationale |
| llama-swap GitHub | Proxy layer for request buffering during swap |
| arXiv:2603.13110 (AgentRM) | UMBM priority hierarchy; zombie reaping informs IPM concurrency limits |
| arXiv:2603.04443 (AMV-L) | Memory pressure eviction policy priority |
| arXiv:2512.01357 (Tangram) | mmap zero-copy model loading; page-in-on-use strategy |

---

## 9. Comparison Hooks

### Where current system is AHEAD
- **Real hardware validation**: current system has empirically determined `--n-gpu-layers 12` is stable on Renoir. This PRD proposes dynamic policy — but the validated baseline IS the current system's finding.
- **MTP deployment**: current system already runs `--spec-type draft-mtp --spec-draft-n-max 2` with Unsloth MTP model. This is ahead of most deployments.
- **GGUF format commitment**: current system correctly chose GGUF. This PRD agrees. No change needed on format.
- **llama.cpp overlay**: current overlay with `-DLLAMA_BUILD_UI=OFF` and pin-based hash management works correctly for NixOS sandbox.

### Where current system SHOULD CHANGE
- **Static n_gpu_layers**: `--n-gpu-layers 12` should become the dynamic IPM's default, not a hard constant. When RAM is abundant and thermal is cool, 16 layers is safe and faster.
- **No thermal monitoring**: no DVFS integration, no thermal-aware scheduling. This is the highest-severity gap given our hardware.
- **No quant tier ladder**: current system has one model, one quant level. When staging a swap, there is no fallback tier if the new model causes OOM or thermal issues.
- **No MTP acceptance rate tracking**: MTP is on but blindly. If acceptance rate drops (new model, different task mix), we waste draft computation with no benefit.
- **No format validation in catalog**: `defaultModelCatalog` in ai-stack.nix has no `hardware_targets` field. Incompatible model could be downloaded without warning.
- **No UMBM**: model weights, KV cache, and OS memory are uncoordinated. Under load (multiple agents + large context), OOM risk is real.

### Where current system can be PRESERVED
- GGUF format, llama.cpp server, existing overlay structure
- MTP model (`qwen3.6-35b-mtp`) — add acceptance rate tracking, keep rest
- Pin-based model hash management pattern
- `--flash-attn`, `--threads 8` baseline config (good defaults)
- llama.cpp port 8080, embed port 8081 (no conflict)
- Existing model catalog JSON structure (extend, don't replace)

---

## 10. Open Questions for Combined PRD

1. **IPM restart vs in-flight parameter change**: llama.cpp server requires restart for most parameter changes (n_gpu_layers, ctx_size). Does the scheduler need to support zero-downtime parameter tuning, or is a brief restart acceptable? If restart: how are in-flight requests handled?
2. **Quant tier switching without model re-download**: switching quant tier means loading a different model file. We need separate model files per tier staged. Who manages storage budget for tier variants?
3. **MTP draft model in catalog**: is the draft model a separate catalog entry or a sibling entry of the base model? Versioning coupling needs definition.
4. **Thermal sensor permissions on NixOS**: `/sys/class/hwmon` access requires specific udev rules or group membership. Service user must be in `video` or `hwmon` group — needs NixOS module update.
5. **IPM discovery by scheduler**: is IPM a separate systemd service, a library inside the coordinator, or a sidecar? Deployment model affects restart semantics.
6. **Acceptance rate ground truth**: MTP acceptance rate comes from llama.cpp `/metrics` Prometheus endpoint. Is polling that endpoint sufficient, or do we need push-based telemetry?
7. **Swap while thermal is elevated**: if user initiates swap when T > T_warn, do we block the swap (safe, frustrating) or proceed with reduced n_gpu_layers (risky but faster recovery)?

---

## Qwen Sign-Off Checklist (for when model comes back online)

When Qwen3.6-35B model load completes, Qwen should:
- [ ] Review all quantization performance numbers against observed token rates
- [ ] Validate or correct the n_gpu_layers tier ladder (esp. layers 13–20 safety margin)
- [ ] Confirm MTP acceptance rate thresholds match observed behaviour on Renoir
- [ ] Amend any architectural decisions that conflict with llama.cpp internals knowledge
- [ ] Answer Open Questions 1–7 with implementation-level detail
- [ ] Add any edge inference concerns not captured in this proxy PRD
- [ ] Sign off with: `Reviewed by Qwen3.6-35B · [date] · [APPROVE / AMEND]`

---

*PRD proxy-authored by Claude Sonnet 4.6 on behalf of Qwen3.6-35B (offline)*
*Edge AI Specialist / Hardware Optimization Lead · 2026-05-19*
*REQUIRES QWEN REVIEW BEFORE PLAN FINALISATION*
