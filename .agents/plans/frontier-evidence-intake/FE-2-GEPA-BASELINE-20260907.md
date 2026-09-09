# FE-2 GEPA baseline — local-agent prompt (measured 2026-09-07)

**Loop step:** the "baseline BEFORE" gate for FE-2 (GEPA build-time prompt compile). Per the intake loop,
no optimizer is adopted without a measured baseline; this run establishes it — and surfaces a blocker.

## What was measured
- Target: `aider_task_systems_code` — the local-agent code-generation prompt in
  `ai-stack/prompts/registry.yaml` (tagged `code_generation, measurement_target`).
- Harness: `scripts/ai/aq-prompt-eval --id aider_task_systems_code --dry-run --verbose`
  (llama.cpp on the resident Qwen3.6-35B-A3B, one call, 95.7s).
- Result: **100.0% (1/1 pass).**

## The finding (why this baseline blocks GEPA as-is)
The 100% is **not** a functional score. `aq-prompt-eval` sends `code_generation`-tagged prompts a single
**meta-quality probe** — it asks the model "is the rendered prompt clear and complete?" and scores the
"yes". So the metric is a one-case self-assessment with:
- **no headroom** (already 100% — GEPA's reflective optimization has nothing to push against), and
- **no functional signal** (nothing is generated, applied, run, or checked against `aq-qa`).

GEPA (natural-language-reflection optimization, ICLR 2026) improves a prompt *against a metric*. A ceilinged
self-grade cannot be that metric — GEPA would "optimize" toward a number that is already maxed and unrelated
to real code quality. This is the intake loop working: FE-2 is **not ready to schedule** until the metric is real.

Corroboration that the harness CAN produce meaningful scores: registry prompts with real keyword assertions
show headroom (e.g. `route_search_synthesis` = 0.667, `prsi_pessimistic_cycle_orchestrator` = 0.000). The
gap is specific to the code-prompt's meta-probe methodology, not the harness.

## Corrected FE-2 plan (metric-first, then GEPA)
**FE-2a (prerequisite slice) — functional local-agent eval metric.** Build a scored eval whose metric is a
real, checkable outcome, reusing what exists:
- Substrate: the **dogfood task set** (`.agents/delegation/dogfood-*` — real tasks with expected patches
  and known-correct diffs) rather than a meta-probe.
- Metric: generated patch **applies cleanly + passes the task's `aq-qa` / behavioral-verify check** (this is
  also FE-1, PRM-as-verify — the two slices share the same verifier signal). Pass-rate over N tasks, with
  headroom (current prompt should NOT already be at 100%).
- Acceptance: a reproducible score in (0,1) with variance bounds, cheap enough to run on the APU (bounded
  task count; cache where possible).

**FE-2b — GEPA compile, gated.** Only after FE-2a: run GEPA **offline/build-time** to reflect-optimize the
local-agent prompt against the FE-2a metric; adopt the compiled prompt **only if** it beats the measured
baseline on that metric AND passes tier0. Never a runtime dependency (DSPy's known production gap).

## Baseline record (for GEPA before/after)
| Metric | Value | Note |
|---|---|---|
| aq-prompt-eval meta-probe (current) | 1.000 | ceilinged self-assessment — unusable as a GEPA target |
| functional dogfood pass-rate (FE-2a) | TBD | to be established by the FE-2a slice; THIS is the GEPA baseline |

## Next
Schedule **FE-2a** (functional eval metric) before any GEPA run. Owner-visible outcome: today's baseline
proved the current code-prompt metric is a self-grade with no headroom — so the honest next step is a real
metric, not an optimizer. Recorded so the finding survives session resets.
