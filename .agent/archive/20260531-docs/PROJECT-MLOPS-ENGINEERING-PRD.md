# PRD — mlops-engineering Domain Activation (Local-First)

**Domain tag:** `mlops-engineering`
**Status:** Implemented — Phase 61 Capability Expansion
**Authors:** Gemini 2.0 Pro (Orchestrator)
**Date:** 2026-05-24

---

## 1. Goal
Establish a dedicated `mlops-engineering` domain to automate the health, performance, and efficiency of local LLM systems. This domain addresses the "Renoir Bottleneck" by implementing proactive context management and model state monitoring.

## 2. Problem Statement
Local AI systems on hardware with shared memory (APUs) suffer from:
1.  **Performance Decay:** KV cache fragmentation and context window bloat lead to latency spikes.
2.  **Static Constraints:** Blocking I/O and unoptimized prompt sizes exhaust memory bandwidth.
3.  **Black-Box State:** Lack of real-time telemetry on model health and token throughput.

## 3. Core Capabilities

### 3.1. Context Weaver (Dynamic Memory Management)
Implements a "Context Firewall" to keep prompt sizes within the 4096-8192 token "Sweet Spot" for the Renoir APU.
- **Algorithm:** Uses LLMLingua-2 (extractive token pruning) and recursive summarization.
- **Priority:** Protects System Instructions and the last 3 turns; compresses everything else.

### 3.2. Proactive Health Monitoring
Polls llama.cpp `/metrics` and `/props` to track:
- `llamacpp:n_busy_slots_per_decode` (KV cache occupancy).
- `llamacpp:predicted_tokens_seconds` (Throughput).
- Thermal state of the APU.

### 3.3. Continuous Learning Bridge
Processes `.agent/collaboration/PULSE.log` and AIDB interactions to generate fine-tuning datasets in **ShareGPT** format for **LLaMA-Factory**.

---

## 4. Technical Specifications
- **Pillar Algorithm:** LLMLingua-2 (Task-agnostic).
- **Optimization Baseline:** **Q8_0 KV Cache** (50% memory savings, near-zero quality loss).
- **Hardware Profile:** ROCm 7.2 with `HSA_OVERRIDE_GFX_VERSION=9.0.0` (Vega 10).

## 5. Acceptance Criteria
1.  `mlops_optimize` tool successfully reports llama.cpp health.
2.  `context_weaver` reduces an 8192-token prompt to 4096 tokens with <5% reasoning loss.
3.  Automated trigger detected when KV cache occupancy > 90%.
