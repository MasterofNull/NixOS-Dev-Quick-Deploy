---
Status: Active
Owner: hyperd (orchestrator: claude)
Last Updated: 2026-07-07
---

# Local Model Selection Requirements (SSOT)

What we TRULY need from a locally hosted inference model — derived from actual workloads, empirical
failure modes, the harness meta-goal (we TRAIN these models), tokenomics on this hardware, trust/governance
boundaries, and the llama.cpp integration surface. These are ELIGIBILITY gates: a candidate must clear them
to even enter the performance bench (`config/bench-promotion-criteria.json`, which scores reasoning/tool_use/
code_gen/coherence). Eligibility = pass/fail preconditions; performance = scored. A model can ace benchmarks
and still be ineligible here.

Key reframing from the passes: the capability axes (reasoning, tool use, research, code) are NECESSARY but
NOT the binding constraint. The binding constraints are **protocol/runtime adherence** (Tier 0) and
**trainability** (Tier 2) — that is where real models fail in THIS harness. And because the harness exists to
refine local models, we select the most *improvable, protocol-compliant base*, not the top-benchmark model.

## Tier 0 — Protocol / runtime (NON-NEGOTIABLE; these are why models fail here)
0.1 **llama.cpp arch support in our PINNED build.** The model architecture must run on the llama.cpp version
    we ship (new arches lag support by weeks). If it doesn't load, nothing else matters. GATE: loads +
    serves /v1/chat/completions on our pinned llama.cpp.
0.2 **Native, reliable tool-calling with a llama.cpp-parseable chat template.** Must emit valid tool calls
    that our parser + `agent_executor` consume (`role:"tool"` results; Qwen3 template drops `role:"function"`).
    Empirically our #1 failure (write_file-as-text, 0 tool calls). GATE: ≥ threshold valid tool-JSON on the
    B-suite WITHOUT prompt-coaxing, and no template-dropped tool results.
0.3 **Toggleable thinking via `chat_template_kwargs`.** Reasoning ON for LARGE_SESSION, OFF for the SMALL
    fast-lane — without empty responses (we hit thinking-tokens→empty-output). GATE: `enable_thinking:false`
    yields non-empty structured output; `true` yields reasoning; both parse.
0.4 **Structured-output discipline under our decode params.** No JSON truncation under `frequency_penalty=0.0`
    + `repeat_penalty≈1.08`; survives GBNF constraint (F2.2 grammar cache) without quality collapse. GATE:
    structured/JSON tasks complete without early-EOS truncation; grammar-constrained decode holds.
0.5 **Offline + deterministic.** Runs fully local (no runtime phone-home, no remote tokenizer fetch);
    seedable/deterministic decode for reproducible eval, audit (F3 OTel), and zero-trust sandboxing. GATE:
    runs air-gapped; same seed+input → same output.

## Tier 1 — Capability portfolio (the four axes, mapped to TIERS — not one model)
1.1 **SMALL (fast-lane):** fast, terse, reliable classification / json-repair / schema-validation / short
    critique. Thinking OFF. Highest-VOLUME tier → reliability + speed dominate.
1.2 **MID:** bounded coding (edits, diff analysis, single-file plans, test triage). Coding strength is the
    selection axis here (e.g. HumanEval).
1.3 **LARGE (session):** deep reasoning + research/synthesis + multi-file planning + dissent review.
    Thinking ON. Long-context + grounding/citation discipline.
1.4 **Multi-step tool sequencing stamina** (MID/LARGE): sustain a read→edit→validate→commit sequence without
    losing the thread (our measured multi-edit boundary). GATE: completes a bounded multi-step agent task.
1.5 **Controllable output economy** (tokenomics): steerable to terse output for cheap tasks; reasoning depth
    is BUDGETED per tier, not always-on. GATE: cheap-task output does not emit unbounded thinking tokens.

## Tier 2 — Lifecycle / meta (because we TRAIN these models — the harness's reason to exist)
2.1 **Open license** (Apache-2.0 / MIT) for a PUBLIC repo + Nix-store redistribution. Gemma's custom license
    is a conscious-decision caveat, not an auto-yes. GATE: license ∈ {Apache-2.0, MIT, permissive-OSI}.
2.2 **Trainable in our pipeline** (LoRA/QLoRA; arch + tokenizer our training loop supports) — else it cannot
    be improved by the learning loop, violating the meta-goal. GATE: fine-tune smoke passes.
2.3 **Good GGUF quants with FIXED chat templates** (bartowski / unsloth / ggml-org). unsloth specifically for
    corrected templates, given our template gotchas. GATE: a trusted Q4_K_M/Q5 quant exists + template verified.
2.4 **Pinnable version + hash** for provenance (F1 contribution provenance, F3 CapabilityLease). GATE: model
    has a stable version tag + sha256 recorded in `config/llama-cpp-models.sha256`.
2.5 **Improvement headroom** on OUR task distribution — prefer an improvable base over a benchmark-saturated
    one (soft/advisory, informs selection not a hard gate).

## Tier 3 — Governance
3.1 **Acceptable dual-use / security-task behavior.** The harness does authorized security/CTF/pentest work;
    over-alignment that refuses dual-use tasks is a functional failure. GATE: passes a dual-use refusal probe.
3.2 **Reproducible bench scores** (anti-gaming: fix the producer, never fake passing). GATE: 2 consecutive
    runs within variance (already enforced by `required_consecutive_runs`).

## How this is enforced
- Encoded as `eligibility_gates` in `config/bench-promotion-criteria.json` — checked BEFORE the scored bench.
- A candidate (e.g. IBM Granite 4.1 8B for MID) must clear Tier 0–2 gates, THEN win the performance bench
  against the incumbent, THEN be promoted into a `model_tier.py` tier default. No tier default changes on a
  YAML edit alone.
- Cross-links: [[project-qwen3-promotion]] (why Qwen3 is the incumbent — it clears these), F2 `model_tier.py`
  (tier defaults = bench winners), F1/F3 provenance (2.4).
