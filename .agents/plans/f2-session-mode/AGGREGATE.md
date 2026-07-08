# F2 Session-Mode — Aggregate (3/4 decisive — RATIFIED; antigravity IDE pending, admissible)

Last Updated: 2026-07-07

## Contributors
- **claude** ✅ (orchestrator — the A-vs-B RAM tension + state machine) · **codex** ✅ (the most complete
  design — controller/authority split, eviction rules, failure recovery) · **local[Qwen]** ⚠️ (0 tool calls,
  emitted role-confusion meta-text instead of a design — folded thin per never-skip-local; no usable content
  this run) · **antigravity** ⏳ IDE inbox pending.

## Verdict: RATIFIED (codex + claude converge; this is the F2.5 spec)
codex's design is adopted as the baseline — it subsumes claude's A-vs-B framing with a more robust
memory-pressure model. The two agree on every structural decision.

## Ratified design (the F2.5 implementation spec)

### Authority split (codex — adopted)
- `scheduler.py` (F2.1): tier decisions only (emits `model_tier.LARGE_SESSION`).
- `dispatch.py`: admission point — asks the controller whether the slot can serve LARGE_SESSION; else returns
  `LOCAL_DELAYED`.
- **gen-slot-controller** (new, MINIMAL): the ONLY writer of slot state — owns state, cooling deadline, idle
  timer, swap lock, watchdog. NOT a second scheduler (no queue ownership, no policy duplication).
- **`aq-model-switch`** (extend): the ONLY mutation primitive — existing atomic symlink-swap + restart, PLUS a
  new `unload` verb (stop the gen-slot llama service, wait for process exit / RSS release) + optional `--json`.

### A-vs-B resolution (claude tension → codex memory-pressure rule)
claude framed it as A (mutual exclusion) vs B (GPU-small/CPU-35B co-residency, F2.6-gated). codex's rule
GENERALIZES and is adopted: default = no forced preemption; the :8082 fast-lane small and :8080 35B **may
coexist only when memory pressure is below the hard threshold AND the 8B mid tier is NOT resident** (the
ratified VRAM Pool rule: never 35B + 8B in VRAM). Given 27 GB and 35B ≈ 26.5 GB, coexistence with a small
model is the RARE case — so in practice this collapses to claude's mutual-exclusion, but expressed as a
memory-pressure policy that is robust to smaller quants and future headroom. Option B (CPU-35B flip) stays
F2.6 measure-before-adopt.

### Gen-slot state machine (codex — adopted; mirrors round_state.py rigor)
States: `UNLOADED` · `LOADING` · `RESIDENT_35B` · `RESIDENT_SMALL` · `SWAPPING`.
Legal transitions: UNLOADED→LOADING (LARGE admitted + cooling expired) · LOADING→RESIDENT_35B (switch ok +
health) · LOADING→UNLOADED (fail/watchdog) · RESIDENT_35B→SWAPPING (idle/evict/unload) · SWAPPING→UNLOADED
(unload ok + RSS released) · SWAPPING→RESIDENT_SMALL (small target health ok) · RESIDENT_SMALL→SWAPPING
(LARGE needs 35B) · SWAPPING→LOADING (collapsed small→35B, but record the SWAPPING event first).
Illegal: any resident state without a health check; RESIDENT_35B→LOADING without SWAPPING; concurrent
transitions. Controller is sole writer; **persist state to a small JSON** (like round.json) so restart/reboot
reconciles from systemd + health probe, never guesses.

### The 7 questions — resolved
1. **Trigger:** LARGE_SESSION reaches dispatch while UNLOADED/RESIDENT_SMALL + no active swap + cooling
   expired → controller takes swap lock, LOADING, `aq-model-switch 35b`, health on :8080, RESIDENT_35B.
2. **P1 in-flight:** a P1 fast-lane job does NOT preempt an in-flight 35B (separate :8082/:8080 processes).
   Eviction only on: 8B-coexistence violation, memory-pressure/OOM telemetry, or a higher-priority local lane
   needing unreclaimable RAM. If eviction is mandatory mid-generation → `evict_pending=true`, new LARGE →
   LOCAL_DELAYED, let the bounded request finish, THEN unload. Kill only on watchdog/crash/critical pressure.
3. **30s cooling = stateful admission control** (not sleep): `cooling_until = last_swap_completed + 30s`;
   while cooling or LOADING/SWAPPING, LARGE → `backpressure.LOCAL_DELAYED` (reason `swap_cooling`, remaining
   seconds, retry-after) — never dropped, never rerouted off local (never-skip-local). Adds a controller
   reason-source to the EXISTING backpressure.py LOCAL_DELAYED path (no new status).
4. **Idle/unload:** 180 s idle timeout (no in-flight :8080 request AND no queued LARGE AND no pending
   continuation AND no transition) — long enough to avoid multi-turn churn, short enough to return ~26.5 GB
   quickly. Controller owns the timer + unload; dispatch/scheduler never stop the service directly.
5. **State machine:** above.
6. **Failure/recovery** (idempotent, watchdog lessons): non-zero swap → SWAPPING cleanup, stop service, kill
   only confirmed :8080 orphan, verify port, mark UNLOADED + cooldown. Health-fail → UNLOADED + LOCAL_DELAYED
   `load_failed` + failure count. OOM/crash → watchdog → orphan cleanup → UNLOADED, block reload until
   cooldown. Symlink-at-35B-but-service-down → state follows PROCESS HEALTH not symlink. Stale lock on boot →
   lock carries pid/start-time; clear if owner gone + reconstruct. After 3 consecutive load failures → keep
   LOCAL_DELAYED with diagnostics + require operator intervention (no tight OOM loop).
7. **Reuse, minimal Nix:** extend `aq-model-switch` (+`unload`, +`--json`); add a MINIMAL controller unit
   (systemd or dispatch-adjacent daemon) with permission to `systemctl stop/restart` ONLY the gen-slot
   service + read health — NOT a second scheduler. Keep `useSymlink` for :8080; add `fastLaneServer` on :8082
   as the resident small-model service.

## Minimal Nix for F2.5 (derived — for the user's dry-build review, NOT yet applied)
1. `fastLaneServer` option block in options.nix (mirror embeddingServer: port 8082, small model, **default-off**).
2. Dormant `fastLaneServer` systemd unit gated `mkIf (roleEnabled && fastLane.enable)`.
3. Extend `aq-model-switch` (Python, NO rebuild) with `unload` + `--json`.
4. `gen-slot-controller` (Python lib + a small systemd unit later) reading scheduler/backpressure, writing the
   slot-state JSON, calling aq-model-switch — behind the same default-off flag.
Rebuild lands it DORMANT (flag off → nothing changes); enable + 35B-session-mode conversion is a later,
measured step. Model-tier defaults obey the eligibility gates + bench (config/local-model-requirements.md).

## Status
**3/4 decisive — RATIFIED.** codex baseline + claude converge; local folded thin (never-skip); antigravity
late-admissible (folds as AMEND if material). This is the F2.5 spec. NEXT: author the minimal-Nix F2.5
declarations behind a default-off flag, dry-build, then hand the user a validated `nixos-rebuild switch`.
