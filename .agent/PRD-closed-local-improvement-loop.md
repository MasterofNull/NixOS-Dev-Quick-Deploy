---
Status: DRAFT — awaiting user go-ahead before implementation
Owner: "hyperd (orchestrator claude)"
Last Updated: 2026-07-08
Source: "reentry-intent round — 3/4 ratified (claude, codex, antigravity); local pending-fold"
---

# PRD — Closed Local-Improvement Loop

## Problem / North star
This is a local-first harness whose PURPOSE is to continuously IMPROVE the locally-hosted models by leveraging
remote agents. That purpose is currently not served: the improve-from-failure loop is dormant
(`training-loop-results.jsonl` last ran 2026-05-27; `samples_added:0`/`dataset_total:0` every run) and local
repeats the identical text-instead-of-tool-call failure within a single session. We have built RESILIENCE
(salvage, never-skip-local) instead of FIXING the producer or CLOSING the loop. This PRD closes it.

## Objective
Make every local failure an auditable training/eval signal, and every local improvement MEASURED before
promotion — so local's tool_use + code_gen improve run-over-run. Two speeds: a FAST per-request producer-fix
loop (no retrain) and a SLOW LoRA/DPO loop (weights).

## Success metrics (MEASURED — the definition of done)
- tool-JSON validity: ~85% → **>98%** (via live GBNF); extract_contribution text-as-tool-call fallback rate → ~0.
- **`samples_added > 0`** per loop run; `dataset_total` grows; ≥95% of local parser/tool/contribution failures
  produce a labeled JSONL event.
- rolling 7-day `bench-local-agent` tool_use/code_gen delta **≥ 0** while top-3 failure recurrence drops **≥30%**.
- promotion gate: **2 consecutive** passing bench runs before any prompt/template/adapter promotion.
- anti-gaming: no synthetic pass without preserved raw failure + repair + eval evidence.

## Non-goals
Full RLHF; remote/cloud training or any API key; base-model replacement (Granite bench is a separate track);
GPU-layer increases; unbounded RL.

---

## Phase 1 (PRD1) — Closed Learning Loop  [lead: claude/codex]
Fix the data pipe and reactivate the loop.
- **P1.1 — DONE (2026-07-08):** `ai-stack/local-agents/training_capture.py` + `scripts/testing/test-training-capture.py`
  (5/5). The missing DATA PIPE: `capture_failure(prompt, bad_output, failure_class, tools_available,
  corrected_output, ...)` appends a labeled training sample to a spool (`.agents/telemetry/training-samples.jsonl`,
  env AQ_TRAINING_SAMPLES). Best-effort + append-only + secret-scrubbed; a failed capture NEVER breaks the
  caller. FIRST wire live: `agent_executor` captures the unambiguous truncated/malformed tool-JSON failure
  (`{"function"...` that the parser rejects) as `failure_class=invalid_tool_json` before its repair. Diagnosis
  recorded: today `training_ingest` writes ONLY positive samples from hybrid-events and merely SUMMARIZES
  failures — it never turns them into training data (a root cause of `samples_added:0`).
- **P1.2 — DONE (2026-07-08):** EXTENDED `training_ingest` with `_ingest_failure_samples` — reads the
  `training-samples.jsonl` spools and turns each captured failure that has a `corrected_output` into an SFT
  **repair pair** (user:prompt → assistant:correct-output, source `failure-repair:<class>`), deduped against
  the dataset; failures without a correction are counted `failure_repair_pending`. Wired into `run()`:
  the report now has `failure_repair_samples_added` + `failure_repair_pending` + a combined `samples_added`.
  Verified END-TO-END (`scripts/testing/test-training-ingest-failure.py`, 3/3): capture_failure → ingest →
  dataset repair pair; uncorrected → pending; rerun dedupes. **The capture→ingest loop is CLOSED** for the
  repair case. Fixed a scope bug (TRAINING_SAMPLES constants now unconditional across the harness_paths
  try/except).
- **P1.3 — DONE (2026-07-08):** the CORRECTION step — `ai-stack/local-agents/failure_correction.py` (pure:
  `is_pending`, `build_correction_prompt` [asks a remote TEACHER for the correct output], `corrected_record`
  [validates the teacher output — for tool-call classes requires parseable JSON naming an available tool])
  + driver `scripts/ai/aq-correct-failures` (reads pending, POSTs the teacher prompt to the switchboard
  remote lane, writes back corrected failure_samples that P1.2 ingests as repair pairs; `--dry-run`, `--max`,
  `--profile`). 5/5 pure tests + dry-run validated. **The full loop now LEARNS:** local fails → capture
  (pending) → aq-correct-failures (remote teacher) → corrected → training-ingest → dataset repair pair → LoRA.
- **P1.4 — DONE (2026-07-08):** DIAGNOSED the positive `samples_added:0` — NOT a filter bug: hybrid-events.jsonl
  has 58,750 events but they're dominated by RAG/search (hybrid_search 34.8k, agent_memory_recall 14.3k,
  route_search 8.8k); only ~19 (local_inference 10 + agent_step_complete 9) are inference completions. The
  positive path is STARVED of source data. FIX (mirrors the failure architecture): `capture_success` in
  training_capture — captures good completions AT the point they happen (reliable), wired live in
  agent_executor at successful tool-call execution (context → the valid tool-call the model emitted).
  training_ingest now ingests `success_sample` records as positive pairs (source `success-capture:*`) alongside
  the `failure-repair:*` pairs. 19/19 closed-loop tests green.
- **P1.5 — NEXT (partly rebuild-gated):** reactivate `aq-local-training-loop` with a real before/after bench
  gate + wire it to run aq-correct-failures + ingest; a Nix systemd timer to schedule correct+ingest
  (rebuild-gated — batch for review); optionally a 2nd failure capture point (extract_contribution fallback).
- **Failure-capture hook** at `round_contribution.extract_contribution` regex-fallback (the exact moment we
  detect local emitted text-not-a-tool-call) + `validate_before_commit` failures + tool-JSON-repair events →
  append labeled `{prompt, tools_available, bad_output, corrected_output, failure_class, model_provenance}` to
  `training-samples.jsonl`. Each sample is **OTel-span-linked** to the failure's parent span and
  **cryptographically signed** (host/agent key) — unsigned/untraceable data is REJECTED at ingest [antigravity].
- **Fix `training_ingest.py`** — diagnose why `samples_added:0` (source path / filter / permission / window /
  not-scheduled) so ingest converts captured failures to samples.
- **Seed a focused eval pack** from real observed failure classes (not only the static harness-gap pack).
- **Reactivate `aq-local-training-loop`** (dormant since 2026-05-27); replace the placeholder `validation` with
  a real before/after bench gate; surface samples/dataset_total/top_failures/pass_rate/promoted-fix-id to the dashboard.
- **Validate:** a live local failure produces a signed, OTel-linked labeled sample; a loop run reports `samples_added>0`.

## Phase 2 (PRD2) — Live Structured-Output Enforcement  [lead: claude]
The FAST producer-fix — highest leverage, no retrain.
- **P2.1 — DONE (2026-07-08):** `ai-stack/local-agents/tool_grammar.py` + `scripts/testing/test-tool-grammar.py`
  (5/5). Pure GBNF construction for the local tool-call envelope `{"function": <enum of leased tools>,
  "arguments": {...}}` via F2.2's grammar_cache (constrains the function name to the AVAILABLE tools — kills
  prose-as-tool-call + calls to non-existent tools). Verified: produces real GBNF (`root ::= ...`), cache
  hits on repeat, stable across tool-order, keyed with the zero_trust namespace.
- **P2.2 — DONE (2026-07-08, flag-gated, default OFF):** wired `tool_grammar` into agent_executor's
  `_call_llama` (both non-streaming + streaming build_llama_payload sites) via a cached `_tool_call_grammar()`
  helper (keyed by the enabled-tool set, hot-swap-aware). `AQ_LOCAL_GBNF` unset → grammar None → **zero
  behavior change** (verified); set → passes `grammar=` (GBNF over the tool-call envelope) to llama.cpp.
  Compiles clean; 5/5 grammar tests green.
- **P2.3 — NEXT (bench, then repair-retry enablement):** a tool-call-ONLY grammar on EVERY turn would break
  final-answer turns, so DO NOT flip AQ_LOCAL_GBNF on globally. First bench on the freed slot to measure
  tool-JSON validity with/without the grammar; then enable it as a **repair-retry** (unconstrained first; on a
  failed `parse_tool_call_from_llama`, retry that turn WITH the grammar) so normal turns are untouched. That
  surgical enablement is the actual producer-fix; P2.2 is the safe mechanism it builds on.
- Wire F2.2 `grammar_cache.GrammarCache` into `ai-stack/local-agents/dispatch.py` (and the aq-agent-loop tool
  path): dispatch-time schema selection → build/lookup GBNF → attach `grammar` to the llama.cpp request payload
  for tool-call / contribution / strict-JSON lanes. Reject prose-only parser output (→ capture a negative sample).
- Apply the known decode fixes on the same lanes: `frequency_penalty=0.0`, `repeat_penalty≈1.08`,
  `role:"tool"`, `enable_thinking:false` in `chat_template_kwargs`, bounded max tokens.
- Emit grammar cache hit/miss/eviction to telemetry.
- **Validate:** bench tool-call tests B1–B3 emit valid `tool_calls` (not prose) across 2 runs; strict-JSON
  truncation → 0 in the focused pack. No new ports, no keys, no service rewrite.

## Phase 3 (PRD3) — Bounded Adapter Promotion Gate  [lead: codex/antigravity]
The SLOW loop — only once data exists.
- Hardware-respecting **LoRA/QLoRA** under a **Nix-declared systemd training slice** [antigravity]:
  `MemoryHigh=8G`, `MemoryMax=12G` (protect Postgres/Qdrant/Switchboard + 4 GB VRAM), target `q_proj`/`v_proj`,
  ctx 2048, batch 1 + gradient accumulation. DPO once paired preferred/rejected data is reliable [codex].
- Dataset manifest + train/eval split + adapter provenance (signed) + rollback metadata.
- Promote an adapter ONLY when it beats baseline on the focused failure pack AND does not regress full bench
  beyond tolerance AND clears `config/local-model-requirements.md` Tier 2.2 — via `aq-model-switch`.
- **Validate:** fine-tune smoke passes within 27 GB RAM / 4 GB VRAM / n_gpu_layers≤12 / parallel=1; a promoted
  adapter shows a measured positive delta with recurrence drop.

---

## Sequencing
Phase 2 (GBNF wiring) + Phase 1 (capture + ingest-fix + bench) land FIRST and together (fast loop) → measure
the invalid-JSON drop → Phase 3 (LoRA/DPO) only when the dataset is non-empty + quality-gated → THEN resume
F2.5 session-mode + F3 (which instrument REAL learning transitions on the closed-loop event schema). The SLOW
loop accumulates from first capture.

## Rollback / safety
Phase 1 capture is additive (append-only dataset). Phase 2 GBNF wiring behind a default-on-but-revertible flag;
prose-only rejection is fail-open to capture, never blocks a lane silently. Phase 3 training runs isolated in
the systemd slice; adapters are opt-in via aq-model-switch and revertible. All rebuild-gated pieces (the Nix
loop timer + training slice) batch for user review per automation-first.

## Constraint validation
never-skip-local = the data source · NO API keys (GBNF + LoRA local) · NixOS-declarative (timer + slice are Nix
units) · hardware envelope respected · eligibility gates govern model changes · anti-gaming: fix-the-producer +
measured promotion with preserved evidence.

## Folded — local (4/4) + a PRD-shaping finding
local[Qwen] FOLDED (salvaged): it engaged ~52 min researching the closed-loop design (get_hint "closed
learning loop design") but its run DIED before synthesis, killed by the pre-fix progress-unaware reaper.
Convergent, no dissent. Two fixes already shipped from this run — progress-aware reap (483a1873, never kills
a progressing run) + matrix thought-stream visibility (3bb7f7fd). It adds one concrete requirement to this
PRD: **local dispatches must receive a COMPRESSED prompt, not a large inlined artifact** (csza5f re-prefilled
a 6.8k-token context ~14 min/turn × 7 turns and never finished) — so P1/P2 should include prompt-size
discipline for the local lane (summarize/point, don't inline) as part of closing the loop efficiently.
