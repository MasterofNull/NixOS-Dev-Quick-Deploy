# Local Model Rebudget Analysis — SMALL_RESIDENT tier + speculative decoding (god-tier prompt 6)

**Date**: 2026-07-09 · **Author**: claude-fable-5 · **For**: operator rebudget decision
**Status**: awaiting decision (the rebudget is genuinely yours — quality tradeoff + nixos-rebuild)

## Evidence first — two premises corrected

**Speculative decoding is ALREADY LIVE.** The running llama-server carries
`--spec-type draft-mtp --spec-draft-n-max 2` (declared in `nix/hosts/hyperd/facts.nix:85-86`).
The model is Qwen3.6-35B **MTP** Q5_K_S — MTP is self-speculative (the draft
head is inside the 22.5GB weights), so it needs **no separate draft model and
zero extra RAM**. Current generation throughput: **2.96–3.45 tok/s** (that number
already includes the MTP gain). So prompt 6's "enable speculative decoding" leg
is done. Only possible follow-up: bench `specDraftNMax 2 → 3` (free, reversible,
helps only if draft-acceptance > 60% — needs a clean-slot bench to confirm).

**The SMALL_RESIDENT tier routes to a model that does not exist.** `model_tier.py`
sends 5 task classes — classification, json_repair, tool_schema_validation,
short_critique, path_grep_summary — to a `SMALL_RESIDENT` tier (concurrency 3,
resident) with no model behind it. These are the highest-waste tasks: today they
bill the 35B at ~3 tok/s and hold the single slot. A 0.6–1.7B model on CPU would
do them at 20–50 tok/s **without touching the big slot** (and unblock parallel
eval + interactive work).

## The constraint (why this is a decision, not a default)

Measured now: 27 GB total, ~16 GB resident (35B), ~10 GB reclaimable page cache.
Budget: **22.5 GB model / 1.0 GB KV / 3.0 GB OS ≈ 26.5 of 27 GB** — under 0.5 GB
true slack. A second resident model would thrash the 35B's page cache unless the
35B shrinks first. So SMALL_RESIDENT cannot be deployed without a rebudget.

## Options (measured tradeoffs)

| Option | Frees | 35B quality cost | Effort | Net |
|--------|-------|------------------|--------|-----|
| **A. Quant-down 35B Q5_K_S → Q4_K_M** | ~2.5–3 GB (fits a 1.5B Q4 resident ≈ 1 GB + headroom) | Q4 vs Q5: typically ~1–2% eval delta, larger on hard reasoning | download Q4 GGUF + small GGUF, set 2 nix options, rebuild | SMALL_RESIDENT live on THIS machine; 5 task classes at 20–50 tok/s; big slot freed; small, measurable 35B quality dip |
| **B. Fleet node** (small model on a Pi/old laptop) | 0 GB local | none | needs WS-EDGE fleet federation (federation_protocol.py unwired) + a second device | no 35B cost, but blocked on unbuilt federation; higher effort |
| **C. Defer** | — | none | none | status quo; 5 task classes stay on the 35B; revisit after fleet federation or a RAM upgrade |

## Recommendation

**A (quant-down)** if you value SMALL_RESIDENT now on this machine and accept a
small 35B-quality dip — it's the only option that ships the tier today, and the
dip is bench-measurable (re-run bench-local-agent before/after; roll back the
one nix option if the delta is unacceptable). **B** is strategically better long
term but blocked on WS-EDGE federation (a later beat). **C** is the honest
choice if 35B quality is sacrosanct until the fleet path exists.

Orthogonal free win regardless of choice: bench `specDraftNMax 2→3`.

## What I've prepped (ready to wire on your decision)
- SMALL_RESIDENT dispatch routing exists (`model_tier.py`); wiring it to a real
  endpoint + the config/model-coordinator `tiers.local` is a bounded slice once
  a model is chosen.
- All of it lands behind an OFF-by-default flag until the model is present, so
  nothing changes the running stack until you rebuild.

## UPDATE (2026-07-09) — made it hardware-driven per your steer

Per operator direction, the rebudget is no longer a one-time manual choice for
this box — it is DERIVED per device by `scripts/ai/lib/model_budget.py` on top of
the E1 hw_probe, so every new environment auto-configures. Run it anywhere:
`python3 scripts/ai/lib/model_budget.py --summary`.

**Policy verdict for THIS host** (measured): at the hardware-recommended quant
(Q4_K_M — note the box currently runs a *heavier* Q5_K_S, above its class
baseline), a **1.7B Q6_K small resident fits with ~4.9 GB slack, no quant-down
below baseline required**. So `deploy_small_resident_now` is the derived
recommendation — the earlier "quant-down" framing overstated the cost, because
aligning to the class-appropriate Q4_K_M already leaves room.

Per hardware class the policy yields: embedded (≤4 GB) → single_model_only;
laptop → usually quant_down_then_small_resident; desktop (this box) →
deploy_small_resident_now; server → fits easily. This is the answer to "should
the rebudget be deployment-hardware-driven": **yes, and it now is.**

Remaining human calls (unchanged in nature, smaller in cost): (1) whether to
align this box's 35B to Q4_K_M (needed to realize the 4.9 GB slack while keeping
Q5 would need a re-measure), (2) approve downloading the small GGUF, (3) run the
rebuild. The wiring + model-coordinator `tiers.local` update is a bounded
follow-up slice, gated OFF until the model file is present.
