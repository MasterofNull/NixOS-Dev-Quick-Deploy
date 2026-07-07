# F2 Design: Local Model-Stacking + Measured Slot Scheduler

## Position

Keep "never skip local" as policy, but make local contribution typed and measured: every round must either receive a local result before consensus lock or receive an explicit `local-delayed` / `local-saturated` state with queue reason, ETA class, and downgrade decision. The scheduler, not the caller, owns model selection and back-pressure.

## Model-Tier Routing

Routing should live in a small local scheduler service behind the switchboard local lane. Switchboard classifies intent and forwards request metadata; the scheduler chooses model tier, slot, grammar, and queue class. This avoids scattering model policy across `aq-agent-loop`, `delegate-to-local`, and direct switchboard clients.

| Tier | Residency | Task classes | Route signals | Default limits |
|---|---:|---|---|---|
| `small-resident` = Qwen3 4B or phi-4-mini | Always resident when local stack is enabled | classification, task typing, tool-arg validation, schema repair, short critique, risk score, grep/file summary, route confidence, prompt shrink | `task_type in {classify, validate, repair, summarize, score}`, low prompt tokens, strict schema, high fanout | low context, grammar required for JSON, highest concurrency |
| `mid-resident` = 8B | Preferred resident control-loop model | bounded reasoning, slice critique, test failure diagnosis, small plan, code review on narrow diff, structured extraction | complexity tier 2-3, prompt medium, caller needs reasoning but not architecture | medium context, grammar for structured outputs, preemptable queue |
| `large-session` = 35B / 35B-MTP | Session-mode, not default resident | architecture, multi-file planning, dissent reviews, hard synthesis, ambiguous failures, final local vote where quality matters | complexity tier 4-5, large prompt, explicit `needs_large_local`, failed smaller-tier confidence gate | one session slot, swap-throttled, admission-controlled |

Fallback cascade:
1. Run `small-resident` first for task classification and schema/grammar selection.
2. Use `mid-resident` for most local round contributions.
3. Escalate to `large-session` only when the classifier predicts high value or when mid-tier confidence is below threshold.
4. If large is unavailable and consensus cannot wait, return typed `local-delayed`; never silently omit local.

## Slot Scheduler

Use MLFQ with aging and per-class SLOs. Jobs carry `queue_class`, `task_type`, `complexity_tier`, `prompt_tokens`, `deadline_ms`, `requires_grammar`, `requires_large`, and `round_id`.

| Queue | Examples | Priority | SLO behavior |
|---|---|---:|---|
| `interactive` | CLI/user-visible request, active collaborative round | 0 | Fast path to small/mid; large only with admission check |
| `validation` | schema repair, GBNF validation, consensus vote, review gate | 1 | Runs before background; strict grammar required |
| `background` | discovery, enrichment, RAG summaries, deferred critiques | 2 | Can be downgraded or delayed |
| `batch` | eval suites, benchmarks, prewarming, non-urgent analysis | 3 | Runs only under idle budget |

Rules:
- Aging promotes waiting jobs one queue level after `age_threshold_ms`; repeated promotion caps at `validation` unless interactive metadata is present.
- Preemption is cooperative at request boundaries; do not kill active llama.cpp generation unless service health is at risk.
- Admission control estimates `prefill_ms + decode_ms` from per-tier rolling metrics and rejects large-tier admission when it would violate interactive SLO.
- Back-pressure actions are ordered: shrink prompt via stable prefix references, downgrade to smaller tier with confidence tag, defer as `local-delayed`, then shed only batch work.
- `local-delayed` payload: `{state, reason, queue_class, tier_requested, tier_assigned, queue_depth, eta_ms_bucket, retry_after_ms, round_id}`.

## VRAM Pool Manager

Treat 4GB APU VRAM as a measured pool, not a fixed model list.

Rules:
- `n_gpu_layers` ceiling is 12 for every llama.cpp service.
- Prefer resident small + resident 8B for control-loop throughput; make 35B session-mode unless measurements prove resident 35B improves high-value completion without starving small/mid.
- Keep embeddings isolated on the embedding service; never let text-generation swaps disturb it.
- Swap only when projected VRAM/RAM headroom crosses threshold; throttle model swaps with a 30s minimum interval and expose `swap_blocked` as scheduler state.
- Before enabling concurrent small+large generation, run a calibration suite measuring VRAM, RAM, tok/s, p95 latency, and desktop pressure. If concurrency hurts p95 or causes swap churn, use small/mid instead of large during large-session occupancy.
- Maintain a warm idle policy: small always warm, 8B warm when memory permits, 35B loaded only for session windows with TTL.

## GBNF + Grammar Cache

The scheduler selects constrained decoding for all tool JSON, routing decisions, validation responses, and acceptance metric records.

Design:
- Generate grammars from final post-filter schemas only; never from untrusted model output.
- Cache compiled grammars by `(schema_hash, zero_trust_state, model_family, grammar_version)`.
- Store cache under the AI stack data directory declared by Nix, not the repo.
- On schema mismatch, fail closed to `validation` queue repair on small tier; do not pass malformed tool args downstream.
- Metrics: grammar cache hit rate, compile latency, constrained decode latency delta, invalid JSON rate by tier.

## Prefix / KV Reuse

Make the local prompt layout stable:
1. Harness grounding hash.
2. Tool schema bundle hash.
3. task classifier rubric.
4. short task payload.

Scheduler should pass stable prefix IDs to llama.cpp where supported and track cold prefill vs reused prefill. Tool schemas and grounding should be versioned so cache invalidation is explicit. If a request includes volatile logs or large diffs, put those after the stable prefix and summarize first with small/mid tier.

## Acceptance Metrics

Golden suite gates:
- Invalid tool JSON repair loop reduced by at least 90%.
- Local landing rate: percent of collaborative rounds with local result or typed local state before consensus lock.
- p50/p95 latency by queue class and tier.
- Slot occupancy by model tier.
- Queue depth and aging promotions by class.
- Tok/s by tier, prompt tokens, decode tokens.
- Percent of 35B time spent on high-value tasks vs trivial validation/classification.
- Swap count, swap throttle hits, VRAM/RAM headroom, OOM or desktop-pressure events.
- Prefix cache hit rate and prefill savings.
- Grammar cache hit rate and constrained decode failure rate.
- Back-pressure distribution: shrink, downgrade, delayed, shed.

Minimum acceptance: local no longer serializes four collaborative dispatches behind one 35B slot; at least trivial validation/classification/repair work lands on resident small/mid tiers while any 35B session is occupied.

## Declarative Nix Wiring

Add declarative options under the AI stack module rather than runtime drift:
- `localScheduler.enable`
- `localScheduler.models.small`, `.mid`, `.largeSession`
- `localScheduler.queuePolicy` with class weights, aging thresholds, SLOs, and max depths
- `localScheduler.vramPool` with GPU-layer ceiling, swap throttle, headroom thresholds, and session TTL
- `localScheduler.grammarCache.dataDir`, `maxEntries`, `schemaVersion`
- `localScheduler.prefixCache.enable`, `maxBytes`, `stablePrefixIds`

Systemd shape:
- `ai-local-scheduler.service` owns queueing, metrics, routing, grammar cache, and typed back-pressure.
- Existing llama.cpp generation services become declared model slots behind scheduler-managed endpoints or Unix sockets.
- `active.gguf` symlink swaps are performed only by scheduler-controlled activation logic generated from Nix declarations.
- Switchboard local route points to scheduler endpoint using the port option from `nix/modules/core/options.nix`; callers do not hardcode ports.
- Dashboard and `aq-qa` get scheduler health, queue depth, landing rate, and tier occupancy in the same slice as service introduction.

## Top 3

1. **Introduce scheduler-owned model routing and typed `local-delayed` back-pressure.** This fixes the core correctness bug: local must be accounted for without letting consensus silently proceed after local starvation.
2. **Keep small + 8B resident and demote 35B to measured session-mode.** This removes trivial work from the 35B slot and gives collaborative rounds a fast local contribution path.
3. **Enforce GBNF with schema-hash grammar cache.** This attacks the 15% repair loop directly and frees scarce local slots for useful reasoning instead of JSON cleanup.
