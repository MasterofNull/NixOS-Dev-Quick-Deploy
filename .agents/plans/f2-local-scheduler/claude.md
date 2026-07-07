# claude — F2 Design: Local Model-Stacking + Slot Scheduler

## Model tiers → task routing
| Tier | Model | Task classes | Where |
|------|-------|--------------|-------|
| fast (resident) | phi-4-mini / Qwen3-4B | classification, JSON/tool-arg validation, schema repair, risk scoring, grep-summary, short critiques | resident 2nd llama.cpp server `:8082` |
| mid | Qwen3-8B | bounded reasoning, routine tool-steps, review-of-small | resident `:8082` (swap 4B↔8B) or a 2nd slot |
| heavy (session) | Qwen3-35B-A3B(-MTP) | architecture, multi-file planning, dissent reviews | main `:8080`, session-mode |
Routing at the **switchboard** by task-class + complexity tier (`model-coordinator.json`) + prompt size.

## Key architectural move (biggest win, cheap)
**A second resident llama.cpp server `:8082` for the fast lane** (phi-4-mini/4B — small VRAM), ALWAYS
up, separate from the 35B slot on `:8080`. This DECOUPLES trivial work (classification/validation/
repair) from the scarce 35B slot — the current single-slot serialization (4 round-dispatches queued
behind the 35B right now) largely disappears: fast tasks go to `:8082`, planning to `:8080`. The
35B-A3B is MoE (3B active) so its footprint may allow this; MEASURE VRAM headroom on the 4GB APU.

## Slot scheduler (in front of the gen slots)
Queue classes **interactive > validation/consensus > background > batch**, **MLFQ + aging** (no
starvation). Back-pressure: over-SLO → shrink prompt / downgrade tier / return typed `local-delayed`
(round stays OPEN — never silently skip local). A `local-scheduler` service owns the queue + routing.

## VRAM pool manager (4GB APU)
Prefer a resident SMALL (phi-4-mini/4B/8B) permanently; the 35B is swapped into `:8080` for planning
sessions via the `active.gguf` symlink pattern; unload-before-load; ~30s swap throttle; embeddings stay
on `:8081`. Never run two heavy models.

## GBNF + cache · KV reuse · metrics
- GBNF constrained decode at the switchboard on the FINAL post-filter tool schemas → valid tool JSON at
  the source; cache compiled grammars by `schema_hash + zero_trust`. Biggest reliability win — put it
  on the fast lane first.
- Keep grounding + tool schemas as a stable PREFIX; measure cache-hit vs cold prefill (the SWA no-KV-
  reuse issue). Consider a smaller n_ctx on the fast lane.
- Metrics (golden suite, measure FIRST): repair −≥90%, local landing rate, p50/p95, slot occupancy,
  queue depth, tok/s by tier, % rounds local contributes before lock, 35B time high-value vs trivial.

## Declarative wiring (Nix, no drift)
New `llama-cpp-small.service` (`:8082`, resident phi-4-mini/4B) + a `local-scheduler` service; the
35B swapper is systemd-managed against `active.gguf`. Ports from `options.nix`. All in the ai-stack role.

## Top 3
1. **Resident fast-lane server `:8082`** — decouples trivial work from the 35B slot; kills the
   serialization; cheap. [FrugalGPT cascade]
2. **Switchboard task-class→tier routing + MLFQ scheduler + back-pressure** [RouteLLM / MLFQ].
3. **GBNF on the fast lane** — valid tool JSON at the source, ends the repair loop [Outlines/XGrammar].
