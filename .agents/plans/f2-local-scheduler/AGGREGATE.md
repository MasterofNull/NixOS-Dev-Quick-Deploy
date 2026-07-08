# F2 (Local Scheduler) — Aggregate (4/4 landed — RATIFIED)

Last Updated: 2026-07-07

## Contributors
- **claude** ✅ · **codex** ✅ (112L) · **local[Qwen]** ✅ (salvaged — see note) · **antigravity[Gemini]**
  ✅ (71L, via IDE OAuth inbox).

## Interim reading (3/4 landed)
Strong convergence on the design direction (matches claude's seed): **resident small model(s)
(4B/phi-4-mini + 8B) + 35B session-mode**, a **measured slot scheduler** (queue classes + MLFQ),
**VRAM-aware** swap management on the 4GB APU, **GBNF + grammar cache**, and declarative Nix wiring.
Local[Qwen] independently reached the same model-tier + VRAM-aware-scheduling design — convergence
confirmed even through a messy emission.

## local[Qwen] note (a live F2/reliability data point)
Its dispatch (`9ydtl2`) completed (1003s) but emitted its `write_file` as TEXT (0 tool calls) and
mislabeled itself "codex" in-body — the known local-model-review-lane-reliability quirks. Design
salvaged to `local.md`. This is itself evidence FOR F2 (fast-lane routing + GBNF would make local's
structured tool-emission reliable) and for the F1 typed-sidecar + collect-time extraction (so a
text-only local answer still yields a usable contribution).

## antigravity[Gemini] — folded (adds the concrete VRAM/queue/back-pressure mechanics)
1. **Explicit VRAM Pool Manager for the 4GB APU** — the sharpest new content: small+mid resident
   (~7.5GB RAM/VRAM), and a hard rule "never run 35B concurrently with 8B in VRAM." Proposes flipping
   residency — pin small/8B at `n_gpu_layers=12`, spawn 35B `large-session` at **`n_gpu_layers=0`
   (pure CPU, threads=8)** with a 30s swap-cooling gate. ⚠️ CAVEAT: current 35B runs at 12 GPU layers;
   moving it to CPU trades 35B throughput for resident small-model GPU residency — must be A/B measured
   on-host before adoption (do not assume it's a win). The *structure* (pool manager + swap gate +
   preempt-and-cache) is adopted; the specific layer split is a tunable to benchmark.
2. **Typed `local-delayed` back-pressure with an SLO trigger** — emit `local-delayed` when MLFQ wait
   > 15s OR expected inference exceeds remaining deadline, so consensus pauses/downgrades instead of
   timeout-crashing. Concretizes the "back-pressure, never silently move on" requirement.
3. **GBNF grammar LRU cache keyed by `sha256(schema_json + zero_trust_state)`** — same key shape codex
   proposed; antigravity quantifies the cost avoided (~250ms compile/ call) and ties the cache key to
   the zero_trust state so F2 and F3 (CapabilityLease/zero_trust) share one cache namespace.

Also contributes: a 3-tier routing matrix (small-resident/mid-resident/large-session with concurrency
limits), MLFQ aging (promote after 30s) + preemption (cancel + KV-cache the preempted prompt), and a
declarative `nix/modules/services/local-model-scheduler.nix` sketch reading ports from options.nix.

## Status
**4/4 landed — RATIFIED.** All four converge: resident small (phi-4-mini/4B) + 8B mid + 35B session-mode,
MLFQ+aging slot scheduler, VRAM-aware swap on the 4GB APU, GBNF + grammar cache, typed back-pressure,
declarative Nix wiring. The claude seed's headline move — a **resident fast-lane server `:8082`** to end
single-slot serialization — was demonstrated live this very epic (4 local dispatches serialized behind
the one 35B slot). Antigravity's VRAM Pool Manager + `local-delayed` SLO + shared GBNF/zero_trust cache
key are adopted; the 35B-on-CPU layer split is flagged as an A/B-measure-before-adopt tunable.
