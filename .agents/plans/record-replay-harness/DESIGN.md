---
doc_type: design
title: Record/Replay harness for local-agent inference — deterministic, instant A/B validation
status: in-progress
owner: hyperd
date: 2026-08-21
companion: .agent/research/maturity-gap-analysis-2026-08.md
---

# Record/Replay harness (velocity multiplier #1)

## Problem (owner-directed, evidence-backed)
Every dogfood validation is a 30-40 min LIVE run on the APU, subject to transient variance. This
session hit FOUR consecutive different failures live (silent-server-timeout, run_command artifact
reject, grammar, budget) — each cost a full cycle to discover serially. The field standard is *"one
command reconstructs any reported score."* We need deterministic, instant replay so config/format/
model A/Bs (grammar on/off, write_region, PTC, the Qwen-37B swap) are seconds not hours, and so ALL
tool-call bugs surface in one deterministic pass.

## The seam (single interception point — verified)
`LocalAgentExecutor._call_llama(messages, role, max_tokens, task_type, ...) -> (content, tokens)` in
`ai-stack/local-agents/agent_executor.py` (line ~2328) is the ONE place inference leaves the loop:
it builds `payload = build_llama_payload(...)` and POSTs to `{endpoint}/v1/chat/completions` (streaming
SSE or legacy). Record/replay wraps THIS method — nothing else in the loop changes.

## Design — a cassette keyed by request identity

**New: `ai-stack/local-agents/llm_cassette.py`**
- `request_key(payload) -> str`: stable sha256 over the SEMANTIC request — messages (role+content),
  max_tokens, temperature, grammar, task_type, tools. Excludes volatile fields (timestamps, request
  ids). This is the replay lookup key.
- `Cassette(path)`: a JSONL file of `{key, payload_digest, content, tokens, meta}` rows.
  - `.record(key, payload, content, tokens, meta)` — append.
  - `.lookup(key) -> (content, tokens) | None`.
  - Ordered fallback: exact key → (optional) nth-call positional (for nondeterministic sampling, a
    cassette can store an ordered list per key and pop in call order).

**Modes (env `AQ_LLM_CASSETTE_MODE`, default `off`):**
- `off` — normal live behavior, zero overhead (default; never changes prod).
- `record` — live call happens AND the (key → content,tokens) is appended to the cassette at
  `AQ_LLM_CASSETTE` path. Builds the corpus from real runs.
- `replay` — NO network. `_call_llama` returns the cassette's recorded content for the key. Miss
  behavior: `AQ_LLM_CASSETTE_ON_MISS` = `error` (default — a miss is a test failure, deterministic) |
  `passthrough` (fall back to live) | `empty` (return "" — simulate a silent model).
- `replay-record` — replay hits when present, live+append on miss (grow a cassette incrementally).

**Wrapping (minimal, in agent_executor):** at the TOP of `_call_llama`, compute `payload` early enough
to derive the key OR (cleaner) factor the payload-build up and consult the cassette before the HTTP
block; on replay-hit, return recorded `(content, tokens)` immediately (skip both streaming and legacy
paths). On record, tee the live result into the cassette before returning. All gated so `off` is a
no-op. Fail-safe: any cassette error in a live mode → proceed live.

## What this unlocks (the A/B runner)
**New: `scripts/testing/aq-replay-bench`** — given a cassette + a matrix of config flags
(AQ_LOCAL_GBNF, AQ_WRITE_REGION, AQ_READ_FILE_GATE, interventions, grammar variants) and a task set,
runs each config in REPLAY mode against recorded model outputs and reports a metrics table:
edit-landed %, correct % (compile/lint the diff — catches lucky-pass), tool-call-valid %, calls,
rejections, per-failure-mode counts. Deterministic + seconds, not live.

Two complementary uses:
1. **Fix-validation without live runs:** record ONE live run per task; then replay it against the
   harness fixes (artifact-strip, write_region wiring, interventions) deterministically — proves the
   LOOP handles the recorded model output correctly, in seconds. (Catches all the tool-call/parser/
   guard bugs — those are loop-side, not model-side, so replay reproduces them exactly.)
2. **Model/format A/B:** record model A and model B (or grammar-on vs -off) once each; compare loop
   outcomes offline.

## Boundary / honesty
Replay validates the HARNESS (loop, parser, guards, interventions, edit application) against fixed
model outputs — deterministic and complete for that layer. It does NOT re-measure the MODEL's live
reliability (that still needs periodic live sampling). So: replay for harness-correctness + fast
iteration; a small LIVE sample per cycle for the model-capability number. Both feed the metrics.

## Validation / DoD
- integrated: `_call_llama` consults the cassette in record/replay modes behind default-off env.
- ON: a recorded cassette for the dogfood tasks exists; `aq-replay-bench` runs against it.
- real-world: replay reproduces this session's run_command-artifact failure from a recorded cassette,
  and shows the committed artifact-strip fix RESOLVES it — deterministically, offline, in seconds.
- observable: metrics table (edit%, correct%, valid-toolcall%, failure-mode histogram) per config.
- intervenable: `AQ_LLM_CASSETTE_MODE=off` kill switch; cassette path configurable.
- test: `scripts/testing/test-llm-cassette.py` — key stability, record round-trip, replay hit/miss
  modes, fail-safe, and a golden end-to-end (record a stub, replay it through `_execute_with_tools`).

## Guardrails
Default-OFF (prod unaffected). Fail-safe to live on any cassette error. No secrets in cassettes
(payloads may contain prompts — cassette files are gitignored by default like other run artifacts;
a curated golden-cassette set can be committed deliberately after review).
