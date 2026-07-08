# claude (orchestrator) — 35B session-mode design

## The tension the round must resolve (state it plainly)
"Resident fast-lane small model on :8082" AND "resident 35B" are **RAM-mutually-exclusive** at 27 GB
(35B ≈ 26.5 GB; a small model needs 2–3 GB). So one of two things is true, and the design must pick:
- **(A) Mutual exclusion (safe, no measurement needed):** ONE gen slot, two possible residents — small OR
  35B — never both. Default resident = the small model (responsiveness for the many cheap ops); swap to 35B
  on demand for LARGE_SESSION work; swap back when idle. There is no permanently-up :8082 alongside a live
  35B — the "fast-lane" is the small model occupying the slot while the 35B is unloaded.
- **(B) True co-residency (needs F2.6 first):** small model on GPU (n_gpu_layers) + 35B on CPU
  (n_gpu_layers=0). This is antigravity's flip — trades 35B throughput for genuine concurrency. It is
  MEASURE-BEFORE-ADOPT (F2.6); do NOT bake it into the first rebuild.

**My recommendation: ship (A) first.** It's the lower-risk realization of the ratified design and needs no
benchmark to be safe. (B) becomes an option after the F2.6 A/B numbers justify the 35B-on-CPU throughput hit.

## Gen-slot state machine (mirror round_state.py rigor)
States: `RESIDENT_SMALL` · `SWAPPING_TO_35B` · `RESIDENT_35B` · `SWAPPING_TO_SMALL` · `UNLOADED` (cold/failed).
Transitions (who drives = the swap-controller, see below):
- RESIDENT_SMALL → SWAPPING_TO_35B: a LARGE_SESSION job dequeued (model_tier route) while small is resident.
- SWAPPING_TO_35B → RESIDENT_35B: 35B health-probe passes.
- RESIDENT_35B → SWAPPING_TO_SMALL: idle timeout (no LARGE_SESSION in-flight AND none queued for N s).
- SWAPPING_TO_SMALL → RESIDENT_SMALL: small health-probe passes.
- any SWAPPING → UNLOADED: swap failure (OOM/crash) → recovery.
Persist the state to a small JSON (like round.json) so a crash/restart reconciles, not wedges.

## Answers to the 7 questions
1. **Trigger authority:** dispatch.py already owns local dispatch — it consults `model_tier.route(task_class)`;
   a LARGE_SESSION route checks the gen-slot state file and calls the swap-controller. No new always-on
   service required for (A); the swap-controller is a thin CLI/lib, not a daemon.
2. **In-flight/preemption:** because (A) is mutual-exclusion, a P1 cheap job NEVER preempts a running 35B —
   cheap jobs only run when small is resident. The real event is: a LARGE job arrives while small is resident
   → the swap itself is the "preemption" (drain the slot, swap). No mid-generation eviction of the 35B for a
   cheap job (cheap jobs wait as LOCAL_DELAYED during a 35B session, or better: are cheap enough to also run
   on the 35B without swapping — decide in consensus).
3. **30s swap-cooling = real back-pressure:** while state ∈ {SWAPPING_*}, `backpressure.assess(...)` returns
   LOCAL_DELAYED for new jobs needing the *other* model → they wait, admissible, never dropped
   (never-skip-local). A min-interval between swaps prevents thrash (don't swap back to small if another LARGE
   job is likely within the cooling window).
4. **Unload-when-idle:** after a LARGE job completes, if no LARGE job is queued/in-flight for `idle_swap_s`
   (propose 60–90 s), swap back to RESIDENT_SMALL so cheap ops are fast again. Configurable; off = stay on 35B.
5. **State machine:** above.
6. **Failure/recovery:** swap = stop(current) → update active.gguf symlink → start(target) → health-probe with
   timeout. On failure: retry once; on second failure → UNLOADED + surface an alert; reuse the orphan/watchdog
   + `aq-agent-reap` lessons (don't leave a half-loaded process holding RAM).
7. **Reuse, not new:** EXTEND `aq-model-switch` — it already does stop→symlink→restart. Add an `unload` verb
   (stop, free RAM, no restart) and a `swap <key>` that records the gen-slot state file. Minimal Nix for (A):
   the 35B service stays as-is (already symlink-swappable); add a small-model catalog entry + a default-off
   `fastLane.enable` flag that, when on, makes the DEFAULT resident model the small one and lets the
   swap-controller promote to 35B on demand. No new systemd daemon needed for (A).

## Top 3
1. **Adopt (A) mutual-exclusion first** — small default, 35B on demand, swap-back on idle. (B) co-residency is
   F2.6-gated. This is the safe, no-benchmark-needed realization.
2. **Gen-slot state machine as a persisted JSON + a thin swap-controller extending aq-model-switch** — reuse,
   not a new daemon; mirror round_state.py (durable, reconciles on restart).
3. **Swap-cooling = LOCAL_DELAYED via backpressure.py** — swaps never drop a job (never-skip-local), and a
   min-swap-interval prevents thrash.
