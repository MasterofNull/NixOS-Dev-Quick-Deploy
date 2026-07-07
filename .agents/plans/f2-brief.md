# F2 Design Brief — Local Model-Stacking + Measured Slot Scheduler

Source: factory-critique #2 (all 3 teams) + the local-utilization evidence. "Never skip local is the
right POLICY but a wrong scheduler." Design the local inference layer so local is FULLY used but not
wastefully single-slotting the 35B on trivial work. Design only; no implementation yet.

## Evidence (the problem)
Only the 35B is loaded (of 6 models: Qwen3 4B/8B/35B-A3B/35B-MTP, phi-4-mini); `parallel=1` single gen
slot; no GBNF → ~15% repair loop; n_ctx=8192 + no KV reuse; embeddings already offloaded to :8081.
Right now 4 collaborative-round local dispatches SERIALIZE behind one 35B slot (this brief is F2 of 4).

## Design targets
1. **Model tiers + routing.** Which task classes → which model: resident **4B/phi-4-mini** (classification,
   JSON/tool-arg validation, schema repair, short critiques, risk scoring, grep-summary) · **8B**
   (bounded reasoning) · **35B session-mode** (architecture, multi-file planning, dissent reviews).
   Where does routing live (switchboard? a scheduler service?) and on what signal (task-type, complexity
   tier from model-coordinator.json, prompt size)?
2. **Slot scheduler.** Queue classes (interactive / validation / background / batch) with **MLFQ +
   aging** (no starvation). Priority: interactive > consensus/validation > background. Back-pressure:
   over-SLO → shrink prompt, downgrade task, or return a typed `local-delayed` state (never silently
   let consensus move on).
3. **VRAM pool manager (4GB APU).** Unload/swap llama.cpp slots only when headroom exceeded; gate swaps
   with a throttle (~30s); prefer a resident 8B over a resident 35B for the control loop. Can we run a
   small-gen slot CONCURRENTLY with (or instead of) the 35B given 4GB? Measure.
4. **GBNF + grammar cache.** Constrained decode on the final post-filter tool schemas (valid tool JSON
   at the source); cache compiled grammars by schema-hash + zero_trust state.
5. **Prefix/KV reuse.** Keep grounding + tool schemas as a stable prefix; measure cache-hit vs cold prefill.
6. **Acceptance metrics (measure first — golden suite).** invalid-tool-JSON repair −≥90%; local landing
   rate; p50/p95 latency; slot occupancy; queue depth; tok/s by tier; % rounds where local contributes
   before consensus lock; 35B time on high-value vs trivial.
7. **Interfaces.** How this wires to `active.gguf` symlink swap, `llama.cpp`/`llama-cpp-embed`, the
   switchboard route, `aq-agent-loop`, and delegate-to-local — declaratively (NixOS), no runtime drift.

## Constraints
Renoir APU: n_gpu_layers ≤12, 4GB shared VRAM, ~27GB RAM. Declarative-only (Nix). NEVER skip local.
Study: FrugalGPT (cascade), RouteLLM/Hybrid-LLM (difficulty routing), MLFQ+aging, LLMCompiler
(parallel DAG), continuous batching (vLLM/Orca — note VRAM limits), constrained decoding (GBNF/Outlines/XGrammar).

## Output
`.agents/plans/f2-local-scheduler/<agent>.md`: the tier→task routing table, the scheduler design
(queues/priority/back-pressure), the VRAM pool-manager rules, the GBNF+cache design, the metric set,
and the declarative wiring. Rank your top 3.
