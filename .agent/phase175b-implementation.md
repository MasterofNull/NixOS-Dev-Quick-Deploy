---
title: "Phase 175-B: Switchboard SSOT Guards, Circuit Breaker, Token Budget Fix — Implementation Evidence"
doc_type: plan
id: phase175b-implementation
parent_prd: phase175-PRD-CONSOLIDATED
phase: "Phase 175-B"
date: 2026-06-17
status: complete
files_changed:
  - ai-stack/switchboard/switchboard.py
  - ai-stack/local-agents/tool_registry.py
  - ai-stack/agents/runtimes/local_agent_runtime.py
  - scripts/testing/test-switchboard-profile-catalog-contract.py
---

# Phase 175-B: Implementation Evidence

5 of 8 plan items implemented (B4, B5, B7 deferred — more invasive changes).
All items require nixos-rebuild to activate in the running switchboard service.

## B1 — Switchboard proxy() SSOT guards (_apply_local_ssot_guards)
New function called from proxy() after _apply_local_thinking_profile.
- stream_options.include_usage=True: actual token counts to telemetry instead of estimator
- frequency_penalty=0.0 for tool profiles: prevents JSON truncation from cumulative " penalty
- repeat_penalty=1.08, repeat_last_n=64 for tool profiles: loop protection

## B2 — llama.cpp circuit breaker
_call_upstream_with_resilience: LOCAL_CIRCUIT_BREAKERS.get("llama") instead of breaker=None.
When llama.cpp crashes, circuit opens after 5 failures; cascading retries blocked.
Remote providers had circuit breakers (Phase 56.1); local path now has parity.

## B3 — local-tool-calling token budget 12000→6000
maxInputTokens default: 12000→6000 (env SWB_LOCAL_TOOL_MAX_INPUT_TOKENS).
Prior: 12000+2048=14048 > n_ctx=8192. Fixed: 6000+2048=8048 ≤ 8192.
Wrong comment "16384 ctx headroom" corrected.

## B6 — local_agent_runtime.py fallback bypass removed
_post_completion_with_fallback: raises RuntimeError instead of falling back to
direct llama.cpp. Silent bypass was skipping telemetry, circuit breakers, hint injection.

## B8 — _sanitize_json control char catch-all
tool_registry.py: added `elif ord(ch) < 0x20: result.append(f"\\u{ord(ch):04x}")`.
Covers \\x08 (backspace) and all other low-order control chars that Qwen3 emits.
Prior code only handled \\n \\r \\t; \\x08 caused json.loads to reject tool call JSON.

## Deferred
- B4: Think-tag state machine in streaming path (streaming chunk rewrite, high risk)
- B5: Grammar-constrained generation (build_llama_payload json_schema injection)
- B7: Zombie subprocess SIGTERM/SIGKILL (ai_coordinator_handlers.py subprocess management)
