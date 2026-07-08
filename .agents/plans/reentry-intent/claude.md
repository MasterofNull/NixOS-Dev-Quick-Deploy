# claude (orchestrator expert team) — re-entry intent

## 1. The minimal closed learning loop (grounded in what exists)
The loop has TWO SPEEDS, and conflating them is why we've stalled:
- **FAST loop (per-request, NO retrain, closes in minutes):** constrained decoding + decode-params + template
  fixes. Force-corrects FORMAT/PROTOCOL failures at generation time.
- **SLOW loop (periodic, LoRA fine-tune, closes in days):** accumulate labeled failure corpus → refine the
  weights for capability/stamina gains.

Existing primitives and their state:
- `extract_contribution` (round_contribution.py) — **already DETECTS** the #1 failure (regex fallback fires
  when local emits text-not-tool-call). This is the capture HOOK — currently used only to salvage, never to
  learn. Missing: a write of the labeled pair.
- `grammar_cache.py` (F2.2) — GBNF cache BUILT, **not wired into dispatch requests**. This is the FAST-loop fix.
- `aq-local-training-loop` — has an IMPROVE step + reads registry.jsonl, but DORMANT since 2026-05-27 and
  `samples_added:0` (ingest converts 0 failures to samples — a bug). This is the SLOW loop, broken.
- `bench-local-agent` / `aq-llama-benchmark` — measurement exists. `store_memory`→Qdrant error-solutions is
  RAG (retrieval), not weight-training. `aq-refine` exists.

Minimal closed loop:
CAPTURE (extract_contribution fallback + validate_before_commit failures + tool-JSON-repair events → append
labeled `{prompt, tools_available, bad_output, corrected_output, failure_class}` to `training-samples.jsonl`)
→ FAST-FIX (GBNF enforce + decode/template — redeploy same generation, no retrain) → CURATE/DEDUP → SLOW-FIX
(LoRA on the corpus when it's large enough) → EVAL (bench before/after on an eval pack SEEDED from real
failures) → PROMOTE (only on measured bench gain, per bench-promotion-criteria + eligibility gates) →
REDEPLOY (aq-model-switch).

## 2. Prioritization verdict: CLOSE THE FAST LOOP FIRST (before F2.5/F3)
Argument against the north star (not preference):
- Local's observed failures are **format/protocol, not IQ** — proven by the SAME failure repeating 3× this
  session. Format failures are FAST-loop fixable (GBNF/template), no retrain, high leverage.
- The two hooks already exist: F2.2 grammar_cache (needs wiring) + extract_contribution (needs a write).
  This is small, not a new epic.
- F2.5/F3 are INSULATION (scheduler plumbing, capability leases) — they make the harness tolerant of a weak
  local model. The fast-loop fix REDUCES the need for that insulation (less salvage for F1, better data for
  F2 routing). So doing it first is not a detour — it improves the substrate the rest builds on.
- Sequencing that does BOTH without waste: FAST loop (GBNF wiring + capture hook + reactivate/fix the ingest)
  is ~1 focused slice; land it, MEASURE the invalid-JSON drop, THEN resume F2.5 (the fast-lane will route to a
  now-more-reliable local), F3 last. The SLOW loop accumulates in the background from first capture.

## 3. Failure → cheapest fix (4 of 5 need NO retrain)
| Failure class | Cheapest real fix | Loop |
|---|---|---|
| text-emitted-as-tool-call | **GBNF grammar enforce** in dispatch request | FAST (no retrain) |
| invalid tool-JSON (~15%) | **GBNF** + freq_penalty=0 (known) | FAST |
| role-confusion / self-mislabel "codex" | system-prompt/role-injection + template fix | FAST |
| truncation mid-JSON | token budget + GBNF (grammar completes structure) | FAST |
| multi-edit / multi-site stamina | decompose (orchestration) now; LoRA on multi-step traces later | SLOW/orchestration |
⇒ The dominant, recurring failures are all FAST-loop. That is the whole argument for the fast loop first.

## 4. Proposed PRD + measured metrics
**PRD: "Closed Local-Improvement Loop."** Objective: local's tool_use + code_gen improve run-over-run from
captured LIVE failures — measured, not assumed. Phased:
- P1 (FAST loop): wire GBNF into dispatch; add the capture hook; reactivate + fix training-loop ingest.
- P2: seed the eval pack from captured failures; wire bench before/after.
- P3 (SLOW loop): LoRA refine on the corpus when N samples reached; promote on measured gain.
**Success metrics (all MEASURED):** (a) tool-JSON validity: ~85% → >98% (GBNF); (b) extract_contribution
fallback rate (text-as-tool-call frequency) trending to ~0; (c) `samples_added` per loop run > 0 and dataset
growing; (d) bench-local-agent tool_use/code_gen deltas positive across runs; (e) local landing rate in rounds
without salvage. **Non-goals:** full RLHF, remote/cloud training, swapping the base model (Granite bench is a
separate track).

## 5. Constraint validation (all HARD constraints honored)
never-skip-local = the DATA SOURCE (every local engagement is a training sample) ✅ · NO API keys (GBNF + LoRA
are local) ✅ · NixOS-declarative (GBNF is runtime; any service/timer for the loop is a Nix unit) ✅ · hardware
(GBNF is ~free; LoRA on 8B/4B fits; 35B stays session-mode) ✅ · eligibility gates govern any model swap ✅ ·
automation-first (the loop is the automation; rebuilds batched) ✅ · anti-gaming: promotion is MEASURED bench
gain, and this IS "fix the producer" not salvage ✅.

## Top 3
1. **Wire GBNF enforcement into live dispatch** (F2.2 grammar_cache → dispatch.py request path) — single
   highest-leverage producer-fix; kills the dominant recurring failure class with no retrain.
2. **Add the failure-capture hook** at `extract_contribution` fallback + validate failures →
   `training-samples.jsonl` (the missing data pipe that makes every never-skip-local run a training sample).
3. **Reactivate + fix `aq-local-training-loop` ingest** (`samples_added>0`) + bench before/after; sequence the
   FAST loop BEFORE resuming F2.5, and let the SLOW LoRA loop accumulate from first capture.
