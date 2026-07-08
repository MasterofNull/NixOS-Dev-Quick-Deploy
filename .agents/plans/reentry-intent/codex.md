# Codex Contribution — Re-entry Intent PRD Formulation

## Verdict

Close the learning loop first. F2.5/F3 scaffolding is useful only after the harness can capture local failures, convert them into training or decode/prompt fixes, run before/after evals, and promote only measured improvements. The north star is local model improvement, so the next PRD should target the dormant producer loop, not more routing resilience.

## Grounded Minimal Closed Loop

Existing primitives:
- `scripts/ai/aq-local-training-loop` already defines the intended stages: ingest, eval, score, improve, validate, commit. It writes `training-loop-results.jsonl`, serializes direct evals with `Semaphore(1)`, checkpoints per case, and records `ingest.samples_added` / `dataset_total`.
- `ai-stack/local-agents/training_ingest.py` already reads `hybrid-events.jsonl`, `.agents/telemetry/hybrid-events.jsonl`, `delegation-feedback.jsonl`, and `optimization_proposals.jsonl`, then writes positive samples to the fine-tuning dataset and prompt rules to `config/harness-prompt-extensions.yaml`.
- `scripts/ai/aq-refine` already implements dispatch -> quality_check -> retry with refinement hints.
- `scripts/testing/bench-local-agent.py` already measures reasoning/tool-use/code/coherence and directly tests the known protocol hazards: `frequency_penalty=0.0`, `role:"tool"` vs `role:"function"`, tool-call JSON, and no thinking leak.
- `scripts/ai/lib/round_contribution.py` already detects and salvages text-only local output through `extract_contribution()` instead of only sidecar JSON.
- `scripts/ai/lib/grammar_cache.py` already builds a deterministic schema-to-GBNF cache keyed by schema plus zero-trust state.
- `config/local-model-requirements.md` already makes protocol/runtime adherence and trainability hard gates.

Missing or broken:
- The loop is not closed: `aq-local-training-loop` validation is explicitly a placeholder and proposals are only logged as pending review, not applied and re-evaluated.
- `samples_added:0` / `dataset_total:0` means the ingest path is either not receiving usable events, filtering too aggressively, writing to the wrong path, lacking permissions, or never being scheduled against the right telemetry window.
- Failure capture is incomplete: `extract_contribution()` can detect text-only/local prose fallback, but that signal is not guaranteed to become a labeled negative example with the prompt, expected tool call, actual text, failure class, and repair target.
- F2.2 grammar cache is pure and tested but not yet wired into live llama.cpp dispatch for tool-call / contribution / strict JSON requests.
- No promotion gate ties a local model or prompt/template change to a before/after delta on the same eval pack plus repeated-session failure recurrence.

Minimal design:
1. Capture every local failure at the producer boundary: prompt, system prompt hash, model/provenance, decode params, expected schema/tool, raw output, parser result, failure class, and recovery path.
2. Convert captured events into two datasets: positive SFT examples from successful local traces and preference pairs for failed->repaired outputs. Use LoRA/QLoRA for small local adaptation; use DPO-style preference optimization only after paired data is reliable.
3. Apply cheap producer fixes before training: live GBNF for strict JSON/tool calls, `frequency_penalty=0.0`, bounded max tokens, `repeat_penalty≈1.08`, correct `role:"tool"`, and `enable_thinking:false` in `chat_template_kwargs` for structured/tool lanes.
4. Run `bench-local-agent.py` before and after every candidate fix, plus a focused regression pack for the exact repeated failure class.
5. Promote only when the measured local delta is positive across two consecutive runs and failure recurrence drops over time.

External anchors:
- LoRA is the right first fine-tune mechanism because it freezes base weights and trains low-rank adapters with far fewer trainable parameters: https://arxiv.org/abs/2106.09685
- DPO is appropriate once the harness has paired preferred/rejected outputs because it avoids a separate reward model/RL loop: https://arxiv.org/abs/2305.18290
- Toolformer supports the idea of training tool-use behavior from API-call traces, but this harness should start narrower with deterministic tool-call schemas and local traces: https://arxiv.org/abs/2302.04761

## Prioritization

Do close-the-loop now:
- It directly serves the north star: local models measurably improve from local failures.
- It uses the primitives already built instead of adding another abstraction layer.
- It creates the eval/provenance signal F3 needs; OTel and signed envelopes are more valuable after events represent real learning transitions.

Sequencing that avoids waste:
- First: failure capture + ingest bugfix + live GBNF enforcement + before/after bench.
- Then: minimal prompt/template/decode fixes and focused eval packs.
- Then: LoRA/DPO smoke only when the dataset is non-empty and quality-gated.
- Then: F2.5 session-mode and F3 CapabilityLease/OTel, using the closed-loop telemetry schema as their event substrate.

## Failure -> Cheapest Fix Map

| Failure | Cheapest real fix | Retrain needed? |
|---|---|---|
| Text-as-tool-call / write_file-as-prose | Live GBNF/tool schema enforcement, require `tool_choice` where supported, reject prose-only parser output, capture negative sample from `extract_contribution()` fallback | No first; fine-tune only if constrained decode still fails |
| Role confusion (`function` vs `tool`) | Template/request fix: emit tool results as `role:"tool"` only; add bench regression; capture dropped-result traces | No |
| JSON truncation / early EOS | `frequency_penalty=0.0`, `repeat_penalty≈1.08`, `repeat_last_n=64`, smaller schemas, max-token budgeting, streaming completeness check | No unless model cannot complete under sane decode |
| Thinking leak / empty structured output | Put `enable_thinking:false` in `chat_template_kwargs` for strict/tool lanes; keep thinking on only for large-session prose/reasoning | No |
| Multi-edit stamina loss | Workflow decomposition, checkpoint/resume, smaller agent steps, training pairs from successful read->edit->validate traces | Partly; fine-tune after enough high-quality traces |
| Repeated same failure within session | Session-local failure memory injected into retry prompt plus negative dataset write on first occurrence | Prompt now; train later |

## PRDs To Write

### PRD 1: Local Closed Learning Loop

Objective: make every local failure become an auditable training/eval signal and make every local improvement measurable before promotion.

Measured success metrics:
- `training-loop-results.jsonl` shows `samples_added > 0` and `dataset_total` increases on fresh eligible telemetry.
- Failure-capture coverage: at least 95% of local parser/tool/contribution failures produce a labeled JSONL event.
- Local improvement over time: rolling 7-day `bench-local-agent.py` score improves or holds while repeated failure recurrence for top 3 classes decreases by at least 30%.
- Promotion gate: two consecutive passing bench runs before any prompt/template/model promotion.
- Anti-gaming: no synthetic pass without preserved raw failure, repair, and eval evidence.

Scope:
- Fix telemetry ingest and dataset path/permission/filter issues.
- Add labeled negative/preference capture for text-as-tool-call and parser fallback.
- Add focused eval pack for observed failure classes.
- Wire dashboard/telemetry fields for samples, dataset total, top failures, pass rate, and promoted fix id.

Non-goals:
- Model download or default model replacement.
- F3 signed envelope implementation.
- Unbounded RL training or remote API use.

### PRD 2: Live Structured Output Enforcement

Objective: wire F2.2 `GrammarCache` into live local dispatch for tool-call, contribution, and strict JSON requests.

Measured success metrics:
- Tool-call bench tests B1-B3 show valid `tool_calls` instead of prose across two consecutive runs.
- Strict JSON truncation failures are zero in the focused pack under `frequency_penalty=0.0`.
- Grammar cache hit/miss/eviction counters are emitted to telemetry.

Scope:
- Dispatch-time schema selection.
- GBNF request payload wiring.
- Strict parser rejection with failure capture.
- No new ports, no API keys, no service rewrite.

Non-goals:
- General grammar generation for arbitrary schemas beyond known harness schemas.
- Fine-tuning.

### PRD 3: Local Adapter Promotion Gate

Objective: once data exists, run a hardware-respecting LoRA/QLoRA smoke path and promote adapters only on measured harness-task gains.

Measured success metrics:
- Fine-tune smoke clears `config/local-model-requirements.md` Tier 2.2.
- Adapter candidate beats baseline on focused failure pack and does not regress full bench beyond tolerance.
- Inference remains within 27 GB RAM / 4 GB VRAM / `n_gpu_layers<=12` / `parallel=1` / 1-4 tok/s envelope.

Scope:
- Dataset manifest, train/eval split, adapter provenance, rollback metadata.
- Bench comparison and promotion record.

Non-goals:
- Full base-model training.
- GPU layer increases.
- Cloud training or external API dependence.

## Constraint Validation

- Never-skip-local: preserved; every round/eval still includes local, but failures become training signals instead of only salvage targets.
- No API keys: required; local telemetry, local fine-tuning data, and local benches only.
- NixOS declarative-only: service scheduling and env/path changes must land through Nix/module config, not ad hoc daemon edits.
- Hardware: design assumes 27 GB RAM, 4 GB shared VRAM, `n_gpu_layers<=12`, `parallel=1`, and slow 1-4 tok/s local inference. Eval packs must be short and serialized.
- Eligibility gates: `config/local-model-requirements.md` remains the gate; trainability and protocol adherence are preconditions, not optional bench dimensions.
- Automation-first: training loop, ingest, bench, dashboard, and promotion records must run without manual inspection except HITL review of risky proposals.
- Anti-gaming: resilience extraction is allowed only as a detector and dataset source; passing requires producer fixes demonstrated by raw-output evals.

## Top 3 Recommendations

1. Write and implement PRD 1 first: fix `samples_added:0`, capture labeled local failures, and make local improvement a dashboard/bench metric.
2. Wire F2.2 GBNF into live dispatch before any fine-tune so the cheapest producer fix is tested against the dominant tool/JSON failures.
3. Defer F2.5/F3 implementation until the closed-loop event schema exists, then use F3 observability/provenance to certify real learning transitions.
