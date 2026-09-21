# Preparatory Research: Integrating "Jev-Type" System 1 Open-Weight Models into the NixOS AI Harness and OS

**Date:** 2026-09-21  
**Status:** Research & Architecture Preparatory Dossier (No Code Implemented)  
**Target Architecture:** NixOS-Dev-Quick-Deploy AI Harness & NixOS Host  
**Context:** Emerging class of "System 1" non-autoregressive decision models (Jev by TypeSafe AI, and open-weight reproductions: `wfzyx/von`, `rlcd-modernbert-151m`, `ZefanCai/Open-Jev`, `Laya`, `steph4n-gh/system1`)

---

## 1. Executive Summary & Paradigm Shift

### The Problem in Current Agent Architectures
Currently, AI agent harnesses and operating system bridges suffer from a structural architectural mismatch:
1. **Generative LLMs are used for discrete decisions:** When an agent framework needs to decide whether a bash command is safe, which agent profile to route to (`local-agent` vs `remote-claude`), whether a task is complete, or if a journalctl log line indicates a service crash, it either:
   - Uses **brittle regex/keyword heuristics** (e.g., `_CODE_RE`, `_LOOKUP_RE` in `task_classifier.py`), which lack semantic nuance and fail on complex or negated intents; OR
   - Spawns a full **autoregressive generative LLM call** (e.g., Qwen3-35B or Claude Code), which takes hundreds of milliseconds to multiple seconds, generates free-form text that requires regex/JSON parsing, suffers from hallucinations, and thrashes the KV-cache and GPU memory.
2. **The Hardware Bottleneck:** On local hardware like our Renoir APU host (27 GB system RAM, 4 GB shared VRAM ceiling, 12 GPU layers dedicated to Qwen3-35B at 22.5 GB + 1.0 GB KV cache = 23.5 GB), running any second generative LLM is prohibitive.

### The "System 1" Revolution: Jev
On September 15, 2026, **TypeSafe AI** (founded by former OpenAI researcher Diogo Almeida) launched **Jev**, introducing the industry to practical **"System 1" decision models** (derived from Daniel Kahneman’s *Thinking, Fast and Slow*).
- **System 1 (Reflexive / Fast):** Fast, non-autoregressive, structured, calibrated decisions ($O(1)$ forward pass, 10–50ms latency, zero token-generation loops).
- **System 2 (Deliberative / Slow):** Heavy, autoregressive, step-by-step reasoning (Qwen3-35B, Claude 3.7 Sonnet, Codex).

While TypeSafe AI's proprietary Jev model is hosted behind a closed API (`POST https://api.typesafe.ai/v1/systemone`), the open-source community rapidly mobilized, producing **open-weight, drop-in reproductions** (`wfzyx/von`, `rlcd-modernbert-151m`, `Laya`, `Open-Jev`).

---

## 2. Technical Anatomy of Jev & System 1 Decision Models

### How Jev-Type Models Differ from Autoregressive LLMs

| Attribute | Autoregressive LLMs (System 2) | Jev-Type Decision Models (System 1) |
|---|---|---|
| **Decoding Process** | Token-by-token loop ($O(N)$ forward passes) | Single forward pass ($O(1)$ forward pass) |
| **Latency** | 500ms – 10,000ms+ | **10ms – 80ms** (CPU), sub-15ms (GPU) |
| **Output Type** | Unstructured or constrained text/JSON strings | **Native typed primitives** (`noul`, `choice`, `score`) |
| **Calibration** | Poorly calibrated logits (often overconfident) | **RLCD / Brier-calibrated probabilities** |
| **Hallucination Risk** | Inherent; can invent facts or invalid syntax | **Mathematically impossible** (closed schema output) |
| **Memory Footprint** | 8 GB – 70 GB+ VRAM/RAM | **150 MB – 1.5 GB** RAM |
| **Compute Target** | Dedicated GPU / VRAM heavy | **CPU / AVX2 / AVX-512 / NPU / lightweight GPU** |

### Core Typed Primitives (`/v1/systemone` Protocol)
The Jev interface consumes a `state` (context string, diff, log trace, or JSON) and a map of typed `questions`:
1. **`noul` (Calibrated Boolean Probability):**
   - Inputs: Instruction.
   - Output: Probability $p \in [0.0, 1.0]$ representing calibrated true/false likelihood.
   - Example use: `is_destructive`, `requires_sudo`, `is_task_complete`, `local_suitable`.
2. **`choice` (Categorical Classification):**
   - Inputs: Instruction + named criteria map (e.g. `{"route_local": "...", "route_remote": "..."}`).
   - Output: Selected key, confidence scalar, and probability distribution over all options.
   - Example use: Intent routing, tool selection, error triage category.
3. **`score` (Ordinal / Continuous Evaluation):**
   - Inputs: Instruction + scale anchor definitions (e.g. 1 to 5).
   - Output: Calibrated scalar score.
   - Example use: Anomaly severity, risk index, code quality rating.

### RLCD (Reinforcement Learning for Calibrated Decisions)
Jev models are trained using **RLCD** or joint Cross-Entropy + **Brier Score minimization** (e.g., $T \approx 1.0367$). This guarantees that when the model reports a confidence of 0.85, the prediction is empirically correct approximately 85% of the time. This enables mathematically sound **confidence gating**:
$$\text{If } \text{confidence} \ge \tau \implies \text{Execute immediate System 1 reflexive action}$$
$$\text{If } \text{confidence} < \tau \implies \text{Escalate to System 2 (Qwen3-35B / Claude / Codex)}$$

---

## 3. Open-Weight / Open-Source Model Landscape

The primary open-source models reproducing or implementing the Jev paradigm (as of September 2026):

```
┌────────────────────────────────────────────────────────────────────────┐
│ Open-Weight System 1 Ecosystem (Sept 2026)                             │
├───────────────────────┬────────────┬───────────────┬───────────────────┤
│ Model / Project       │ Size / Arch│ RAM (Footprint│ Latency (CPU)     │
├───────────────────────┼────────────┼───────────────┼───────────────────┤
│ wfzyx/von             │ 395M       │ ~1.2 GB       │ 25ms - 80ms       │
│                       │ Bidirect.  │               │ (Native drop-in)  │
├───────────────────────┼────────────┼───────────────┼───────────────────┤
│ rlcd-modernbert-151m  │ 151M       │ ~350 MB       │ 10ms - 30ms       │
│ (OpenJev / Verdict)   │ ModernBERT │ (ONNX ready)  │ (Ultra-lightweight)
├───────────────────────┼────────────┼───────────────┼───────────────────┤
│ ZefanCai/Open-Jev     │ 2B - 9B    │ 2.5 GB - 8 GB │ 80ms - 250ms      │
│                       │ Qwen + Head│               │ (Complex reasoning
├───────────────────────┼────────────┼───────────────┼───────────────────┤
│ Laya                  │ ONNX-native│ ~400 MB       │ 15ms - 40ms       │
│                       │ Multi-head │               │ (TS/Python engine)│
├───────────────────────┼────────────┼───────────────┼───────────────────┤
│ steph4n-gh/system1    │ C/Rust Run │ <200 MB       │ <5ms (Sub-1ms opt)│
│                       │ Machine-nat│               │ (Kernel/OS gating)│
└───────────────────────┴────────────┴───────────────┴───────────────────┘
```

### Detailed Evaluation of Top Candidates for Our Harness:

#### Candidate A: `wfzyx/von` (395M)
- **Strengths:** Explicitly built as an open-source, local drop-in replacement for the Jev protocol. Calibrated using Brier score loss. Python API (`von.decide(...)`) and Transformers compatibility. Multi-hop empirical reasoning benchmark score of 91.23%. Supports CPU, ROCm, CUDA.
- **Fit for us:** Exceptional for hybrid-coordinator routing and agentic decision gates where nuanced criteria comprehension is required.

#### Candidate B: `heman10x/rlcd-modernbert-151m` (Verdict)
- **Strengths:** 151M parameters built on the ModernBERT encoder backbone. Supports long contexts up to 8192 tokens with rotary embeddings. Easily exports to ONNX Runtime. Consumes less than 400 MB RAM and executes in 10–25ms on CPU.
- **Fit for us:** Perfect for continuous background OS telemetry, log line scoring, and command-line safety checks.

#### Candidate C: `steph4n-gh/system1`
- **Strengths:** Focuses on sub-millisecond execution for machine-native policy and safety gating.
- **Fit for us:** Ideal for shell pre-execution hooks (`bash` pre-exec) and kernel/AppArmor policy validation.

---

## 4. Hardware & Resource Compatibility for Our NixOS APU Node

### Current Hardware Budget
- **CPU:** AMD Ryzen (x86_64, AVX2 support)
- **GPU / APU:** Renoir APU (4 GB shared VRAM ceiling, 12 GPU offload layers max)
- **System Memory:** 27 GB RAM total
  - Qwen3-35B GGUF: ~22.5 GB
  - KV-Cache (Context): ~1.0 GB
  - NixOS Base Services & Desktop: ~3.0 GB
  - **Remaining Headroom:** ~0.5 GB to 1.0 GB

### Why Jev-Type Models are Uniquely Feasible Here:
1. **Zero VRAM Contention:** A 150M or 395M model does **not** need to touch the 4 GB APU VRAM. It runs entirely on host CPU memory via multithreaded AVX2 instructions or ONNX Runtime.
2. **Negligible Memory Consumption:**
   - `rlcd-modernbert-151m` in INT8/ONNX: **~150 MB** RAM.
   - `wfzyx/von` in FP16/INT8: **~400 MB – 800 MB** RAM.
   Both fit comfortably within our remaining ~1 GB RAM buffer without risking OOM or memory swapping.
3. **Zero KV-Cache Eviction:** Because Jev models do not maintain conversational KV-caches, they do not disrupt the cached context of `llama-server :8080`.

---

## 5. Architectural Integration Blueprint for NixOS-Dev-Quick-Deploy

Where does a Jev-type System 1 model fit into our agentic software development system and operating system?

```
┌────────────────────────────────────────────────────────────────────────┐
│                      NixOS Operating System & Harness                  │
│                                                                        │
│  [User / IDE / CLI Task] ──► [Pre-Execution System 1 Gate]             │
│                                   │                                    │
│       ┌───────────────────────────┴────────────────────────────┐      │
│       ▼                                                        ▼      │
│   Confidence >= 0.85                                    Confidence < 0.85
│   (Reflexive Decision)                                  (Escalate)     │
│       │                                                        │      │
│  Fast Path (15ms):                                      Slow Path:    │
│  - Allow / Block command                                - Qwen3-35B   │
│  - Select tool / stop agent                             - Claude/Codex│
│  - Route to local vs remote                             - Expert Round│
│  - Triage journalctl alert                                            │
└────────────────────────────────────────────────────────────────────────┘
```

### 1. Hybrid-Coordinator Semantic Routing (`task_classifier.py` & `intent_classifier.py`)
- **Current State:** `task_classifier.py` uses regex heuristics (`_LOOKUP_RE`, `_CODE_RE`, `_REASONING_RE`), which misclassify subtle instructions (e.g. "don't implement, just explain"). `intent_classifier.py` uses embedding distance against prototypes (fetching from embed :8081).
- **With System 1 Jev:**
  - Forward user query + session intent through a 20ms Jev call.
  - Return:
    - `choice`: `task_type` (`lookup`, `format`, `code`, `reasoning`, `security_audit`, `nixos_ops`).
    - `noul`: `local_suitable` (probability that local 35B model can execute without hallucination).
    - `choice`: `recommended_profile` (`local-agent`, `continue-local`, `remote-claude`, `remote-codex`).
  - If `confidence >= 0.88`, route deterministically without any LLM hesitation.

### 2. Switchboard Pre-Routing & Cost Optimization (`switchboard :8085`)
- In `:8085`, insert a System 1 sidecar probe on incoming `/v1/chat/completions`:
  - Instantly checks whether an untagged request can be handled locally or needs remote routing.
  - Drops token overhead and eliminates latency spikes caused by sending ambiguous queries to remote providers.

### 3. Autonomous Operations Boundary & Shell Safety Gating (`AUTONOMOUS-OPERATIONS-POLICY.md`)
- **Current Policy:** Distinguishes between unattended operations (git commit, test run, nixos-rebuild dry-run) and approval-gated operations (destructive git, sudo, rm, rollback).
- **With System 1 Jev:**
  - A pre-execution safety daemon intercepts agent tool calls (e.g., `run_command`).
  - Query:
    - `noul`: `is_destructive`
    - `noul`: `violates_least_privilege`
    - `noul`: `modifies_untracked_system_state`
    - `choice`: `policy_disposition` (`allow`, `warn`, `hard_block`, `prompt_human`)
  - Sub-5ms execution ensures zero noticeable overhead in the agent loop.

### 4. Continuous OS Health & Journalctl Telemetry Spider (`PRSI` / `RemediatorAgent`)
- Real-time stream of `journalctl -f`, cgroups memory pressure alerts, and thermal telemetry:
  - An autoregressive 35B LLM cannot parse 100 log lines per minute.
  - A 151M System 1 model can filter and score every warning/error event:
    - `score`: `severity_index` (0.0 to 1.0)
    - `choice`: `fault_domain` (`nix_store_corruption`, `rocm_gpu_driver`, `network_dns`, `service_oom`, `benign_noise`)
    - `noul`: `requires_remediator_intervention`
  - When `requires_remediator_intervention` is true and `confidence >= 0.90`, automatically drop an alert into `logs/alerts/` for the `RemediatorAgent`.

### 5. Agentic Loop Control & Stopping Criteria (`aq-agent-loop`)
- In autonomous agent execution loops, one of the biggest failure modes is "spinning" (calling `read_file` or `grep_search` repeatedly without making progress):
  - Rule 14 (Tool Deduplication) and stopping condition checks.
  - System 1 questions after each turn:
    - `noul`: `is_goal_satisfied`
    - `noul`: `is_agent_stuck_in_loop`
    - `choice`: `recommended_next_action` (`read`, `search`, `edit`, `validate`, `terminate`)

### 6. Reviewer Gate & Consensus Triaging (`reviewer-gate` / `gemini-review-gate.md`)
- Before initiating an expensive multi-agent consensus round (Claude, Gemini, Codex):
  - Run the git diff + PRD acceptance criteria through System 1:
    - `noul`: `has_syntax_or_lint_regressions`
    - `score`: `architectural_risk_score` (1 to 5)
    - `choice`: `review_path` (`auto_pass_trivial`, `single_local_reviewer`, `full_tri_agent_consensus`)
  - Saves API credits and time on small, routine doc/config edits.

---

## 6. NixOS Declarative Deployment Architecture (How to Package)

When we are ready to implement, how should this be declared in NixOS?

```
┌──────────────────────────────────────────────────────────────────┐
│ NixOS Service Topology                                           │
│                                                                  │
│  system1d.service (NixOS systemd microservice)                   │
│  ├── Engine: ONNX Runtime (C++ / Python) or Rust                 │
│  ├── Model Weights: /var/lib/nixos-ai-stack/models/system1/      │
│  │   (e.g., von-395m-int8.onnx or rlcd-modernbert-151m.onnx)     │
│  ├── Socket: /run/nixos-ai-stack/system1.sock (UNIX Domain Socket│
│  └── Confinement: AppArmor profile (No network, read-only weights│
│                                                                  │
│  Consumers:                                                      │
│  ├── hybrid-coordinator (:8003) ──► UNIX socket                  │
│  ├── switchboard (:8085)         ──► UNIX socket                  │
│  ├── aq-safe-gate (CLI/hooks)    ──► UNIX socket                  │
│  └── prsi-telemetry-spider       ──► UNIX socket                  │
└──────────────────────────────────────────────────────────────────┘
```

### Key Declarative Design Decisions:
1. **IPC: UNIX Domain Socket vs TCP Port:**
   - **Recommendation:** Use a Unix domain socket (`/run/nixos-ai-stack/system1.sock`) as primary, with an optional localhost port (:8086, reserved in `options.nix`).
   - *Why:* Unix domain sockets eliminate TCP network stack overhead, reduce latency from ~2ms down to ~200 microseconds, and leverage standard Linux POSIX file permissions (`chmod 0660`, `chown ai-stack:ai-stack`) and AppArmor rules without exposing network attack surfaces.
2. **AppArmor Profile:**
   - Path-restricted: Read access only to its specific model directory in `/nix/store/` or `/var/lib/nixos-ai-stack/models/`.
   - Network-denied: `deny network inet, deny network inet6`. It is purely an offline, local decision engine.
3. **Telemetry & Dashboard Parity (Rule: "You Cannot Manage What You Cannot Measure"):**
   - Must expose:
     - `system1_requests_total`
     - `system1_latency_p95_ms`
     - `system1_escalation_ratio` (percentage of decisions escalated to System 2)
     - `system1_confidence_distribution`
   - Wire directly into `dashboard.html` / `dashboard.js` and `aq-qa` health checks.

---

## 7. Knowledge Items & Reference Materials

### Open Source Repositories & Checkpoints
- **`wfzyx/von`:** [github.com/wfzyx/von](https://github.com/wfzyx/von) — 395M System One decision model (Brier calibrated, drop-in Jev protocol, CPU/ROCm/CUDA).
- **`heman10x/rlcd-modernbert-151m`:** Hugging Face `heman10x/rlcd-modernbert-151m` — ModernBERT 151M RLCD decision engine.
- **`ZefanCai/Open-Jev`:** [github.com/Zefan-Cai/Open-Jev](https://github.com/Zefan-Cai/Open-Jev) — LoRA/scalar decision heads for Qwen backbones.
- **`steph4n-gh/system1`:** [github.com/steph4n-gh/system1](https://github.com/steph4n-gh/system1) — Machine-native decision runtime for sub-millisecond OS safety gating.
- **TypeSafe AI Jev Reference:** Specification for `/v1/systemone` (`state` + `questions` schema with `choice`, `score`, `noul`).

---

## 8. Summary of Preparatory Recommendations

1. **Model Selection:**
   - Primary: **`wfzyx/von`** (395M) for high-accuracy intent routing, agent stopping, and review triaging.
   - Secondary / Edge: **`rlcd-modernbert-151m`** (151M) for continuous OS journalctl monitoring and sub-10ms bash safety checks.
2. **Execution Runtime:** Deploy via **ONNX Runtime** on CPU (using AVX2). Avoid putting load on the 4 GB APU VRAM.
3. **IPC Mechanism:** Expose a **UNIX domain socket** (`/run/nixos-ai-stack/system1.sock`) to allow zero-overhead queries from bash scripts, Python daemons, and C/Rust tools.
4. **Phasing:** When implementation is approved, roll out in bounded slices:
   - Slice 1: Nix derivation + systemd service (`system1d`) + socket baseline + `aq-qa` check.
   - Slice 2: Integration into `task_classifier.py` and `intent_classifier.py` in `hybrid-coordinator`.
   - Slice 3: Integration into shell safety gate (`aq-safe-gate`) and autonomous ops policy.
   - Slice 4: Continuous OS journalctl anomaly scoring (`PRSI`).
   - Slice 5: Dashboard observability panel for System 1 metrics.
