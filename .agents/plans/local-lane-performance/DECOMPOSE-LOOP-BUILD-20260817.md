---
doc_type: plan
id: decompose-loop-build-20260817
title: Decompose-condense loop — local works past its context limit
status: complete
parent_prd: local-lane-performance
date: 2026-08-17
---

# Decompose-condense loop build

Lets local Qwen (5,200-tok input budget) chew through problems larger than its context via chunk +
embed-backed recall. Sonnet lane (Rule 17), orchestrator-reviewed PASS (independent). NOT wired into the
live path yet + NOT activated — this is the capability primitive.

- `ai-stack/local-agents/decompose_loop.py` — `decompose()` (deterministic, structure-aware bin-pack under
  budget) + `run_decomposed()` (per-bite `context_cache.retrieve_ctx` recall → `build_llama_payload` → local
  → `cache_evicted` accumulation → synthesis). Fail-open: failed bites recorded in `failed_bites`, loop
  continues, never raises. Reuses context_cache + llm_config SSOT (no reimplementation); agent_executor untouched.
- `scripts/testing/test-decompose-loop.py` — 9 tests (real cache round-trip vs live :8081/:6333, no stubs):
  no-op, split-under-budget, retrieval, accumulation, failed-bite-continues, budget-never-exceeded. 9/9 + tier0 26/0.

## Next (not done): wire into the local execution path; then the guarded dogfood queue (local proposes,
## remote disposes) + config re-tuning (timeouts/slot-queue deadlines to APU pace).
