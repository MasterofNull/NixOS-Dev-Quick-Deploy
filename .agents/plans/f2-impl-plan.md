# F2 Implementation Plan — Local Model-Stacking + Measured Slot Scheduler

Status: CONSENSUS-RATIFIED (f2-plan-consensus 3/4 decisive; antigravity late-admissible)
Owner: claude (orchestrator)
Last Updated: 2026-07-07
Design SSOT: `.agents/plans/f2-local-scheduler/AGGREGATE.md` (4/4 ratified)
Plan-consensus corrections: `.agents/plans/f2-plan-consensus/AGGREGATE.md` (folded below)
Builds on: F1 (round.json state machine) — F2 schedules typed work against F1 rounds.

## Plan-consensus corrections (RATIFIED — supersede conflicting detail below)
1. **Phase-A guardrails (HARD).** F2.1–F2.4 MUST NOT modify `dispatch.py`, Nix modules, ports, services, or
   live llama.cpp request paths. Pure `scripts/ai/lib/` modules + unit tests ONLY. Any live routing = F2.5.
2. **F2.1 starvation bound.** Concrete configurable max-wait bound (not only "promote after N s"); tests
   assert the bound holds under load.
3. **F2.3 quorum contract test.** An F1-integration test proving consensus CANNOT proceed while a local lane
   is `local-delayed` (never-skip-local, mechanized). `local-delayed` is a typed ADMISSIBLE lane state, not
   a failure/abstain/timeout.
4. **F2.2 canonical versioned cache key.** `sha256("gbnf:v1\0" + canonical_schema_json + "\0zt:" +
   canonical_zero_trust_namespace_digest)` — canonical JSON both inputs, explicit separators + version prefix;
   `zero_trust_state` = namespaced canonical policy digest (shared with F3), not a mutable blob.
5. **F2.5 REQUIRES 35B session-mode.** A resident :8082 small model CANNOT coexist with an always-resident
   35B in 27 GB (35B ≈ 26.5 GB). F2.5 must convert the 35B to session-mode (load/unload) and specify:
   load/unload latency, swap-trigger authority, in-flight-request handling on P1 preemption, and the 30s
   swap-cooling gate as REAL back-pressure. This is the crux of Phase B.

## Objective
End the single-slot serialization that had 4 local dispatches queue for hours behind the one 35B gen slot.
Give the local agent a MEASURED scheduler: resident small models for cheap/bounded work, the 35B in
session-mode only for architecture/consensus, an MLFQ+aging queue so nothing starves, GBNF-constrained
decoding to kill the ~15% invalid-tool-JSON repair loop, VRAM-aware swap on the 4GB APU, and typed
`local-delayed` back-pressure so consensus never silently moves on without local. Realizes the ratified
F2 design and the "never skip local, but don't wastefully single-slot the 35B on trivial work" policy.

## Problem
- `parallel=1` on the Renoir APU: ALL generation serializes on one 35B slot (1–4 tok/s). Trivial work
  (classification, JSON repair, short critiques) competes with architecture on the same slot.
- Only `active.gguf` (35B) is loaded; 5 smaller models (Qwen3 4B/8B, phi-4-mini, …) sit unused.
- No GBNF grammar gate → ~15% invalid tool-JSON → repair loops burn the slot.
- No back-pressure: a slow local lane is handled by timeout/crash, not a typed signal.

## Design (from the 4/4-ratified AGGREGATE; antigravity's VRAM/back-pressure mechanics folded)
Three model tiers (small-resident phi-4-mini/4B · mid-resident 8B · large-session 35B), an MLFQ+aging
scheduler (3 priority bands + aging promotion + preemption), a VRAM Pool Manager enforcing "never 35B+8B
concurrent in VRAM," a GBNF grammar LRU cache keyed `sha256(schema_json + zero_trust_state)`, typed
`local-delayed` SLO back-pressure, and declarative Nix wiring for a resident fast-lane server on a new port.

## Phasing — rebuild-FREE logic first (autonomous), rebuild-GATED infra second (user-reviewed)

### PHASE A — pure, testable Python modules (no rebuild; codex-authored slices, orchestrator-integrated)
Location: `scripts/ai/lib/` (reuse point, same as F1) — importable by dispatch.py + a future scheduler service.

- **F2.1 — MLFQ + aging scheduler core.** `scheduler.py`: 3 priority bands (interactive P1 / consensus+
  validation P2 / background+batch P3) with per-band max slot time; aging (promote after N s in a lower
  band — no starvation); preemption decision (P1 arrival preempts P3, cache the preempted prompt context).
  Pure decision functions over an in-memory queue model — NO real inference. Tests: enqueue/dequeue order,
  aging promotion, preemption, no-starvation invariant, deterministic tie-breaks.
- **F2.2 — GBNF grammar LRU cache.** `grammar_cache.py`: `get_or_build(schema_json, zero_trust_state)`
  keyed `sha256(schema_json + zero_trust_state)`; bounded LRU; a pluggable builder (real GBNF-from-JSON-
  schema conversion, or a stub the test injects). Tests: cache hit/miss, LRU eviction, key stability,
  zero_trust state changes the key (shares F3's namespace).
- **F2.3 — typed `local-delayed` back-pressure.** `backpressure.py`: `assess(queue_wait_s, expected_infer_s,
  remaining_deadline_s) -> Signal` returning `ok | local-delayed | reject` per the SLO rule (wait >15s OR
  expected infer > remaining deadline → `local-delayed`). Pure. Tests: each threshold path; integrates with
  F1's quorum (a `local-delayed` lane stays admissible — never-skip-local).
- **F2.4 — model-tier routing matrix.** `model_tier.py`: `route(task_class) -> Tier` mapping the ratified
  matrix (classification/json-repair/short-critique → small-resident; bounded-edit/diff/single-file-plan →
  mid-resident; architecture/consensus/multi-file → large-session), with concurrency limits per tier.
  Pure classifier. Tests: each task class → expected tier; unknown → safe default (mid or large).

### PHASE B — rebuild-GATED infra (BATCHED for end-of-cycle review; NOT auto-applied)
These need `nixos-rebuild` and touch services — per automation-first, I will PREPARE the declarations and
STOP for your review before any rebuild.

- **F2.5 — resident fast-lane server + VRAM Pool Manager + Nix wiring.** A small llama.cpp instance on a
  NEW port (add `fastLanePort` to `nix/modules/core/options.nix`, default 8082) hosting a resident small
  model; `nix/modules/services/local-model-scheduler.nix` declaring residentTiers + gpuLayersCeiling=12 +
  the VRAM pool rule (never 35B+8B concurrent). Wire the scheduler (F2.1-F2.4) into dispatch.py so cheap
  ops route to :8082 and only architecture/consensus hits the 35B slot. Requires rebuild.
- **F2.6 — 35B-on-CPU A/B benchmark (MEASURE before adopt).** A harness to compare the current 35B@12-GPU-
  layers vs antigravity's proposed 35B@n_gpu_layers=0 (CPU) + resident small on GPU. The design FLAGGED
  this as measure-before-adopt — do NOT flip layer allocation without the A/B numbers.

## Agent roles (flat — all engaged)
- codex (architect/impl): F2.1-F2.4 slice authoring under scope discipline (the F1 pattern that worked).
- claude (orchestrator): plan, per-slice validation + commits, Phase-B declarations, integration.
- local[Qwen]: the scheduler's own subject — bench/validate that cheap ops actually route off the 35B slot.
- antigravity (reviewer): VRAM/back-pressure fidelity vs its ratified design (its VRAM Pool Manager is the
  Phase-B baseline); via IDE inbox, no keys.

## Validation (per slice)
```bash
python3 -m pytest scripts/testing/test-scheduler.py scripts/testing/test-grammar-cache.py \
  scripts/testing/test-backpressure.py scripts/testing/test-model-tier.py -q
scripts/governance/tier0-validation-gate.sh --pre-commit
# Phase B (only after your review): nixos-rebuild dry-build .#hyperd-ai-dev, then switch in a terminal.
```

## Evidence requirements
Per commit: pytest summary + tier0 PASS + which ratified design element it implements. Phase B: dry-build
output + explicit user go-ahead before switch (rebuilds are terminal-gated + batched per automation-first).

## Rollback
Phase A modules are additive libraries (not yet wired into the live dispatch until F2.5) — revert = git
revert the slice. Phase B is gated behind review + a rebuild; the fast-lane is opt-in via a feature flag in
`nix/modules/profiles/ai-dev.nix` (default off until benched), so a bad rebuild is revertible by flag + switch.

## Sequencing
F2.1 → F2.2 → F2.3 → F2.4 (autonomous, rebuild-free) → **STOP + report** → F2.5 → F2.6 (user-reviewed,
rebuild-gated). Then F3 (CapabilityLease + OTel) instruments both F1 and F2.

## Progress log
- **F2.1 — DONE (2026-07-07).** `scripts/ai/lib/scheduler.py` + `scripts/testing/test-scheduler.py`.
  codex-authored (task ezee1p), orchestrator-integrated. PURE MLFQ+aging scheduler (clockless — `now` passed
  into every decision): Band enum (P1_INTERACTIVE/P2_CONSENSUS_VALIDATION/P3_BACKGROUND_BATCH), Job +
  SchedulerState/Config (DEFAULT_MAX_WAIT_S, DEFAULT_STARVATION_CEILING_S); enqueue / next_job (band→FIFO→id
  deterministic) / age (concrete configurable starvation bound — promotes before the ceiling) / preempt (P1
  evicts P3, stashes context; P1 never evicted by lower bands) / no_starvation_invariant. 7/7 pytest green;
  purity verified (no internal clock). Phase-A guardrail held (only the 2 files). NEXT: F2.2 (grammar_cache.py).
- **F2.2 — DONE (2026-07-07).** `scripts/ai/lib/grammar_cache.py` + `scripts/testing/test-grammar-cache.py`.
  codex-authored (task s7d5y2), orchestrator-integrated. GBNF LRU cache with the RATIFIED canonical versioned
  key `sha256("gbnf:v1\0"+canonical(schema)+"\0zt:"+canonical_zt_digest)` — VERIFIED: reorder/whitespace →
  same key, different zero_trust_state → different key (shares F3 namespace), version prefix present. Bounded
  LRU (get_or_build hit/miss, eviction counted, stats), pluggable builder (test injects counting stub). Pure.
  8/8 pytest green. Phase-A guardrail held. NEXT: F2.3 (backpressure.py + F1 quorum contract test).
- **F2.3 — DONE (2026-07-07).** `scripts/ai/lib/backpressure.py` + `scripts/testing/test-backpressure.py`.
  codex-authored (task cyri2o), orchestrator-integrated. Signal enum (OK/LOCAL_DELAYED/REJECT); pure
  `assess(queue_wait_s, expected_infer_s, remaining_deadline_s)` per the SLO rule (expected>remaining →
  LOCAL_DELAYED; wait>15s → LOCAL_DELAYED; deadline≤0 → REJECT; else OK — all verified); `is_admissible`
  (LOCAL_DELAYED admissible, REJECT not). **The ratified F1 quorum CONTRACT TEST passes: never-skip-local is
  now MECHANIZED** — a manifest with claude+codex submitted but a REQUIRED local lane pending (min_lanes=3,
  required_agents includes local) → quorum_met False → aggregate does NOT reach CONSENSUS_LOCKED (locked_at
  None). Consensus cannot silently proceed while local is delayed. 7/7 pytest green. NEXT: F2.4 (model_tier.py).
