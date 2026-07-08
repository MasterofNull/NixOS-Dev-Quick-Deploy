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

## Open (fold when local lands)
local[Qwen]'s own contribution about its failure loop — pending; folds as an amendment. Antigravity's late
f1/f2-plan-consensus views fold into those rounds' aggregates (now 4/4).
