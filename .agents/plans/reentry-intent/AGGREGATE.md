# Re-entry Intent — Consolidated Aggregate (3/4 decisive — RATIFIED; local pending-fold)

Last Updated: 2026-07-08

## Contributors
- **claude** ✅ (fast/slow two-speed loop; close-fast-loop-first) · **codex** ✅ (the 3-PRD structure +
  training_ingest.py discovery + LoRA/DPO/Toolformer grounding) · **antigravity** ✅ (provenance/signing + OTel
  spans + resource-bounded LoRA systemd slice) · **local[Qwen]** ⏳ pending — running 49 min (re-prefill
  pathology on the oversized inlined prompt); slot kept OPEN, folds as a late amendment (never-skip-local).

## Unanimous verdict: CLOSE THE LOOP FIRST (before F2.5/F3 scaffolding)
All three landed teams independently reached the same conclusion, argued against the north star (improve local
over time), not preference: F2.5/F3 are INSULATION that make the harness tolerant of a weak local model;
closing the improve-from-failure loop is what actually serves the purpose. Local's failures are format/protocol
(proven by identical repeats), so most are fixable at generation time with NO retrain. The build order was not
serving the north star; this corrects it.

## The two-speed loop (claude) — the framing everyone's design fits into
- **FAST loop** (per-request, NO retrain, closes in minutes): GBNF constrained decoding + decode-params +
  template fixes force-correct FORMAT/PROTOCOL failures at generation time.
- **SLOW loop** (periodic, LoRA/DPO, closes in days): accumulate a labeled failure corpus → refine weights.

## Consolidated design (codex 3-PRD structure + antigravity substrate, folded)
CAPTURE (at the `extract_contribution` regex-fallback — the exact point we DETECT local emitting text-not-tool-
call — + validate_before_commit failures + tool-JSON-repair events → append a labeled
`{prompt, tools_available, bad_output, corrected_output, failure_class}` to `training-samples.jsonl`, **OTel-
span-linked to the failure's parent** and **cryptographically signed** before it can be ingested [antigravity:
no unsigned/untraceable data into local weights]) → FAST-FIX (GBNF enforce + decode/template — redeploy, no
retrain) → CURATE/DEDUP → SLOW-FIX (**resource-bounded LoRA** under a Nix systemd slice MemoryHigh=8G/
MemoryMax=12G, q_proj/v_proj, ctx 2048, batch 1 [antigravity], DPO once paired data is reliable [codex]) →
EVAL (`bench-local-agent` before/after on an eval pack SEEDED from real failures) → PROMOTE (only on measured
delta ≥0 across 2 consecutive runs + failure-recurrence dropping, per bench-promotion-criteria + eligibility
gates) → REDEPLOY (aq-model-switch).

Existing primitives (grounded): `aq-local-training-loop` (stages defined, DORMANT since 2026-05-27, `validation`
is a placeholder), `ai-stack/local-agents/training_ingest.py` (already reads hybrid-events/delegation-feedback/
optimization_proposals + writes to the fine-tune dataset + config/harness-prompt-extensions.yaml — but
`samples_added:0` is a bug), `aq-refine` (dispatch→quality_check→retry), `bench-local-agent.py` (measures +
tests the exact protocol hazards), `round_contribution.extract_contribution` (the capture HOOK, currently
salvage-only), `grammar_cache.py` (F2.2, built, NOT wired into dispatch). External anchors: LoRA
(arXiv 2106.09685), DPO (2305.18290), Toolformer (2302.04761), OpenTelemetry.

## Failure → cheapest fix (4 of 5 need NO retrain — the argument for the fast loop)
| Failure | Cheapest real fix | Retrain? |
|---|---|---|
| text-as-tool-call / write_file-as-prose | **live GBNF** enforce + reject prose-only + capture negative sample | No |
| role confusion (`function` vs `tool`) | template/request: emit results as `role:"tool"` + bench regression | No |
| JSON truncation / early EOS | `frequency_penalty=0.0`, `repeat_penalty≈1.08`, max-token budget, GBNF completes structure | No |
| thinking leak / empty structured output | `enable_thinking:false` in `chat_template_kwargs` for strict/tool lanes | No |
| multi-edit stamina | decompose + checkpoint now; LoRA on successful read→edit→validate traces later | Partly |

## The PRD(s) to write (codex structure, adopted) → .agent/PRD-closed-local-improvement-loop.md
- **PRD1 — Closed Learning Loop:** fix the ingest (`samples_added>0`), add labeled failure capture at the
  extract_contribution hook (signed + OTel-linked), seed a focused eval pack, dashboard the metrics.
- **PRD2 — Live Structured-Output Enforcement:** wire F2.2 GrammarCache into dispatch.py tool-call/strict-JSON
  requests (the FAST producer-fix; no retrain).
- **PRD3 — Bounded Adapter Promotion Gate:** hardware-respecting LoRA/QLoRA under antigravity's Nix systemd
  slice; promote adapters only on measured harness-task gains + signed provenance.

## Measured success metrics (all MEASURED, not assumed)
- tool-JSON validity ~85% → >98% (GBNF); extract_contribution fallback rate (text-as-tool-call) → ~0.
- `samples_added>0` per loop run; `dataset_total` grows; ≥95% of local parser/tool/contribution failures
  produce a labeled JSONL event.
- rolling 7-day `bench-local-agent` tool_use/code_gen delta ≥0 while top-3 failure recurrence drops ≥30%.
- promotion gate: 2 consecutive passing bench runs before any prompt/template/adapter promotion.
- anti-gaming: no synthetic pass without preserved raw failure + repair + eval evidence.

## Sequencing (no waste)
FAST loop (PRD2 GBNF wiring + PRD1 capture/ingest-fix + before/after bench) → prompt/template/decode fixes +
focused eval packs → PRD3 LoRA/DPO smoke only when the dataset is non-empty + quality-gated → THEN resume F2.5
session-mode + F3 (which now instrument REAL learning transitions via the closed-loop event schema). The SLOW
loop accumulates in the background from first capture.

## Constraint validation (all HARD honored)
never-skip-local = the DATA SOURCE ✅ · NO API keys (GBNF + LoRA local) ✅ · NixOS-declarative (loop timer +
training slice are Nix units) ✅ · hardware (GBNF ~free; bounded LoRA fits; 35B session-mode) ✅ · eligibility
gates govern any model change ✅ · automation-first (the loop IS the automation; rebuilds batched) ✅ ·
anti-gaming: this IS "fix the producer"; promotion is measured bench gain with preserved evidence ✅.

## Status
**3/4 decisive — RATIFIED.** claude + codex + antigravity converge (close-the-loop-first) and their additions
are complementary, not conflicting → consolidated cleanly. local pending-fold (slot open; folds as amendment —
its take on its OWN failure loop is captured when it lands). NEXT: PRD written; present to user for go-ahead
before implementing (touches dispatch.py + training_ingest.py + aq-local-training-loop + a Nix training slice).
