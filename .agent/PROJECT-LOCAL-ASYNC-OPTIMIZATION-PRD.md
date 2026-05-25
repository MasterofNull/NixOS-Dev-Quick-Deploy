# PRD — Local-First Asynchronous Optimization

**Domain tag:** `systems-software` / `mlops-engineering`
**Status:** Proposed — Phase 61 Performance Hardening
**Authors:** Gemini (Orchestrator)
**Date:** 2026-05-24

---

## 1. Objective
Transform the AI harness from a synchronous, blocking architecture into a modular, asynchronous pipeline optimized for the Renoir APU (integrated GPU/shared memory). This will eliminate "ReadTimeout" errors, prevent system freezes during inference, and maximize local hardware utility.

## 2. Problem Statement
The current harness treats local LLM inference as a synchronous task. On hardware with shared memory (ThinkPad P14s), long inference cycles block the event loop, causing:
1.  **Coordinator Timeouts:** The orchestrator drops connections while waiting for a stalled APU.
2.  **UI Freezing:** The dashboard becomes unresponsive during token generation.
3.  **Handoff Penalties:** Unoptimized context windows create massive memory bandwidth pressure.

## 3. Proposed Solution: The "Local-First" Pipeline

### 3.1. Asynchronous Agent Runtime
Refactor `local_agent_runtime.py` to use `asyncio` and `httpx`.
- **Logic:** The agent must yield control to the loop while waiting for the LLM.
- **Benefit:** Allows the harness to perform background tasks (telemetry, memory indexing) while the LLM generates tokens.

### 3.2. Llama Router (Queuing & Throttling)
Finalize the `llama-router.nix` service to sit between the Coordinator and llama.cpp.
- **Logic:** Implement a request queue with a 202 Accepted / 503 Busy status pattern.
- **Benefit:** Decouples the coordinator from the inference engine's physical latency spikes.

### 3.3. Context Memory Compression
Implement a "Sliding Window" manager in the MLOps domain.
- **Logic:** Automate the summarization of conversation history before it reaches the hardware's "K-Handoff" threshold.
- **Benefit:** Reduces prompt tokens, speeding up TTFT (Time To First Token) and reducing memory bus contention.

---

## 4. Phased Execution Plan

### Slice 1: The "Async Runtime" (Execution)
- [ ] Research `local_agent_runtime.py` imports and dependencies.
- [ ] Replace `requests` with `httpx.AsyncClient`.
- [ ] Wrap inference calls in `asyncio.wait_for` with graceful timeout handlers.

### Slice 2: The "Memory Relief" (Logic)
- [ ] Implement `context_compressor.py` in the MLOps toolkit.
- [ ] Add a "Compression Gate" to the coordinator that triggers when history > 8192 tokens.

### Slice 3: The "Resilient Infrastructure" (NixOS)
- [ ] Enable `mySystem.aiStack.llamaRouter` in the host configuration.
- [ ] Implement the thermal-zone monitor to adjust `n_gpu_layers` dynamically.

---

## 5. Acceptance Criteria
1.  **No Blocking:** The dashboard remains responsive (interactive) during a 2048-token generation cycle.
2.  **No Timeouts:** End-to-end inference completes without HTTP 504 or ReadTimeout errors.
3.  **Hardware Efficiency:** Memory bandwidth pressure is reduced via smaller prompt footprints.
