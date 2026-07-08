# Antigravity — F2 Design: Local Model-Stacking + Measured Slot Scheduler

## 1. Top 3 Design Decisions

1. **Static Resonance vs On-Demand Session Swapping**: To respect the 4GB APU VRAM limits, keep the `small-resident` (phi-4-mini/4B, Q4_K_M) and `mid-resident` (8B, Q4_K_M) models resident as they occupy ~7.5GB of RAM/VRAM combined. The `35B` model is loaded only as a session-bound swap-throttled process for architecture and consensus voting, with n_gpu_layers set to 0 to prevent APU VRAM exhaustion.
2. **SLO-Driven back-pressure with `local-delayed` State**: When the MLFQ queues have a wait time exceeding 15 seconds, or a task's expected inference time exceeds the remaining session deadline, returning a typed `local-delayed` state tells the consensus loop to pause or downgrade its request instead of waiting for a timeout crash.
3. **GBNF Grammar Compilation cache by Hash**: Generating GBNF grammars for tool calling on the fly can add up to 250ms of blocking latency. We cache compiled GBNF grammars in an LRU cache using `sha256(schema_json + zero_trust_state)` as the primary key.

---

## 2. Model-Tier Routing Matrix

| Model Tier | Active Model / Quant | Task Classes | Concurrency Limit | Residency Strategy |
| :--- | :--- | :--- | :--- | :--- |
| **`small-resident`** | `phi-4-mini` (Q4_K_M) | classification, tool schema validation, json syntax repair, path/grep summary | Concurrency = 3 | Always warm in VRAM / RAM |
| **`mid-resident`** | `Qwen-2.5-8B-Instruct` | bounded coding edits, git diff analysis, single-file plans, test error triage | Concurrency = 1 | Resident; preempted only when 35B session is active |
| **`large-session`** | `Qwen-2.5-35B-Instruct` | architecture planning, consensus voting, complex multi-file refactoring | Concurrency = 1 | Off-loaded; spawned in system RAM on-demand; 30s swap cooling gate |

---

## 3. Slot Scheduler (MLFQ + Aging)

We implement a Local Scheduler service operating three priority queue bands:
1. **Interactive** (Priority 1): User chat, quick status queries, classification. Max slot time = 10s.
2. **Consensus & Validation** (Priority 2): Tool-validation, agent consensus reviews. Max slot time = 30s.
3. **Background & Batch** (Priority 3): RAG indexes, logs analysis, cold evaluations. Max slot time = 120s.

### Queue Aging & Preemption Rules
- **Aging Rule**: Any queue item residing in Priority 2/3 for longer than `30s` is promoted up 1 priority band to prevent starvation.
- **Preemption**: If a Priority 1 task arrives while a Priority 3 task is compiling KV tokens on the `mid-resident` lane, the scheduler issues a cancel signal to the llama.cpp endpoint, caches the priority 3 prompt context, and executes Priority 1.

---

## 4. VRAM Pool Manager (APU Rules)

Our hardware limit is **4GB shared APU VRAM** (Renoir APU) and **27GB Total RAM**.
- **GPU Floor**: Lock `phi-4-mini` and `8B` to `n_gpu_layers=12` (max APU ceiling).
- **RAM Protection**: Never run `35B` concurrently with `8B` in VRAM. When a `large-session` task enters the queue:
  1. Scheduler halts the `8B` service via systemd or command terminate.
  2. Spawns `35B` with `n_gpu_layers=0` (pure CPU inference) and `threads=8` to avoid RAM spikes.
  3. Holds `35B` active until queue of Priority 2 architecture tasks is empty AND a `30s` inactivity cooldown passes.
  4. Swaps the `8B` model back into resident warm state.

---

## 5. Prefix & KV Cache Reuse
- Wumbology guidelines, active tool layouts, and general prompt formatting are kept as static prefixes.
- We run individual models with `--slot-save-path` enabled, or reuse KV prefix caches inside llama.cpp.
- The scheduler matches request prefixes to identify cache-friendly slots, reducing cold prefill times by up to 80% on sequential planning.

---

## 6. Acceptance Metrics
- **JSON Validation Failures (Target: <2%)**: Percentage of tool calls rejected by syntax checkers.
- **Local Landing Rate (Target: >95%)**: Fraction of active tasks where a local slot responds before cloud timeout.
- **Slot Swapping Latency (Target: <45s)**: Total duration from preemption lock to next-tier model readiness.
- **Queue Depth & TTFT**: p50/p90 metrics reported to the Grafana metrics client.

---

## 7. Declarative NixOS Wiring
- Wires the local scheduler service as a Nix module under `nix/modules/services/local-model-scheduler.nix`.
- Declares the model parameters, paths, and ports using Single Source of Truth (`nix/modules/core/options.nix`):
  ```nix
  services.local-model-scheduler = {
    enable = true;
    port = config.services.aistack.ports.scheduler;
    residentTiers = [ "small" "mid" ];
    gpuLayersCeiling = 12;
  };
  ```
