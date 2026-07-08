# Codex Design — F2.5 35B Session-Mode Load/Unload

## Position

Use a small dedicated gen-slot swap controller as the authority for slot state, but reuse `aq-model-switch` as the only mechanism that mutates the `useSymlink` target and restarts/stops llama.cpp. The F1 scheduler decides when a job needs `LARGE_SESSION`; dispatch consults backpressure/state and either starts the controller transition or returns `LOCAL_DELAYED`.

## 1. Load/Unload Trigger Authority

Authority split:
- `scripts/ai/lib/scheduler.py`: classifies/adjudicates work and emits `model_tier.LARGE_SESSION`.
- `dispatch.py`: admission point; asks the controller whether the gen slot can serve `LARGE_SESSION`.
- `gen-slot-controller`: owns state, cooling deadlines, idle timer, swap lock, watchdog, and calls `aq-model-switch`.
- `aq-model-switch`: performs the existing atomic symlink switch and service restart; extend it with `unload` to stop the gen-slot llama service and leave the symlink untouched.

Exact load condition:
- A `LARGE_SESSION` job reaches dispatch while slot state is `UNLOADED` or `RESIDENT_SMALL`.
- No swap is currently active.
- Cooling deadline has expired.
- Controller obtains the swap lock, marks `LOADING`, calls `aq-model-switch 35b`, waits for health on `:8080`, then marks `RESIDENT_35B`.

Exact unload condition:
- Slot is `RESIDENT_35B`.
- No in-flight 35B request.
- No queued/admitted `LARGE_SESSION` work.
- Idle deadline has elapsed.
- Controller marks `SWAPPING`, calls `aq-model-switch unload`, waits for process exit/RSS release, then marks `UNLOADED`.

## 2. P1 In-Flight Handling And Eviction Rules

P1 interactive work on the fast lane should not preempt an in-flight 35B generation by default because `:8082` and `:8080` are separate processes and ports. Preemption is only required when memory or VRAM residency policy makes coexistence unsafe.

Both may run when:
- The fast-lane small model is already resident on `:8082`.
- The 35B is resident on `:8080`.
- The mid/8B model is not resident in VRAM.
- System memory pressure remains below the hard threshold and swap is not growing.

The 35B must be evicted when any of these are true:
- The scheduler needs to admit a resident 8B/mid tier that would violate the ratified VRAM Pool rule: never 35B + 8B concurrently in VRAM.
- The controller observes memory pressure above threshold, OOM-risk telemetry, or llama.cpp instability while 35B is resident.
- A higher-priority local lane requires memory that cannot be reclaimed without unloading 35B.
- The 35B request completes and the idle timeout expires.

Do not kill an active 35B request solely because a P1 fast-lane job arrived. If eviction becomes mandatory while a 35B request is in-flight, mark `evict_pending=true`, reject new `LARGE_SESSION` admissions with `LOCAL_DELAYED`, let the current request finish if bounded, then unload. Only kill on watchdog timeout, process crash, or critical memory pressure.

## 3. 30s Swap Cooling As Back-Pressure

Cooling is stateful admission control, not `sleep`.

Controller maintains `cooling_until = last_swap_completed_at + 30s`. While `now < cooling_until`:
- New `LARGE_SESSION` requests return `backpressure.LOCAL_DELAYED`.
- Requests are never dropped and never rerouted away from local solely due to cooling.
- Response includes reason `swap_cooling`, remaining seconds, current slot state, and retry-after metadata if the API supports it.

While state is `LOADING`, `SWAPPING`, or health is not settled:
- `LARGE_SESSION` returns `LOCAL_DELAYED`.
- P1 fast-lane requests continue on `:8082` unless memory pressure crosses the eviction threshold.

This integrates with existing `backpressure.py` by adding a controller-backed reason source to the existing `LOCAL_DELAYED` path rather than inventing a new status.

## 4. Idle/Unload Policy

Idle timeout: 180 seconds initially.

Idle means all are true continuously for the timeout window:
- No in-flight request on `:8080`.
- No queued/admitted `LARGE_SESSION` job.
- No pending continuation/chunk for the active session.
- No controller transition in progress.

Why 180s:
- Long enough to avoid unload/reload churn during interactive multi-turn 35B use.
- Short enough to return about 26.5 GB to the system quickly after a session ends.
- Easy to tune with telemetry later.

The controller owns the idle timer and unload. Scheduler/dispatch should not perform direct service stops.

## 5. Gen-Slot State Machine

States:
- `UNLOADED`: no gen-slot llama process; 35B not resident.
- `LOADING`: controller is switching symlink/service toward 35B and waiting for health.
- `RESIDENT_35B`: `:8080` serves the 35B session model.
- `RESIDENT_SMALL`: `:8080` serves a non-35B fallback/small gen model, if configured.
- `SWAPPING`: controller is stopping or changing the gen-slot process.

Legal transitions:
- `UNLOADED -> LOADING`: `LARGE_SESSION` admitted and cooling expired.
- `LOADING -> RESIDENT_35B`: `aq-model-switch 35b` succeeded and health passed.
- `LOADING -> UNLOADED`: switch failed, health failed, or watchdog expired after cleanup.
- `RESIDENT_35B -> SWAPPING`: idle timeout, mandatory eviction, explicit unload, or switch request.
- `SWAPPING -> UNLOADED`: unload succeeded and process/RSS released.
- `SWAPPING -> RESIDENT_SMALL`: switch to small gen-slot target succeeded and health passed.
- `RESIDENT_SMALL -> SWAPPING`: `LARGE_SESSION` requires 35B or explicit unload.
- `SWAPPING -> LOADING`: optional collapsed implementation for small-to-35B, but persistently record the intermediate `SWAPPING` event first.

Illegal transitions:
- `UNLOADED -> RESIDENT_35B` without `LOADING`.
- `RESIDENT_35B -> LOADING` without `SWAPPING`.
- Any transition into resident state without health confirmation.
- Concurrent transitions under separate callers.

Driver:
- Controller is the only writer of state.
- Dispatch reads state and requests transitions.
- Scheduler supplies tier decisions only.
- `aq-model-switch` changes process/symlink state but does not decide policy.

## 6. Failure And Recovery

Failure cases and recovery:
- `aq-model-switch` exits non-zero: mark state `SWAPPING` while cleanup runs, stop the gen-slot service, verify no orphan llama.cpp process for `:8080`, then mark `UNLOADED` and set cooldown.
- Health check fails after restart: stop service, mark `UNLOADED`, return `LOCAL_DELAYED` with reason `load_failed`, and record failure count.
- OOM/process crash mid-generation: controller detects via watchdog/service status, marks `UNLOADED` after orphan cleanup, releases swap lock, and blocks immediate reload until cooldown expires.
- Symlink points at 35B but service is down: state is `UNLOADED`, not resident. Runtime state follows process health, not symlink alone.
- Stale lock on boot: lock file must include pid/start time; if owner is gone, controller clears it and reconstructs state from systemd + health probe.

Watchdog lessons:
- Always make recovery idempotent: stop service, kill only confirmed orphan for the gen slot, verify port closed or healthy, then write state.
- Persist state to a small JSON file under runtime/state storage so reboot or controller restart can reconstruct without guessing.
- After three consecutive load failures, keep returning `LOCAL_DELAYED` with diagnostic reason and require operator/remediator intervention rather than tight-looping OOM.

## 7. Reuse Vs New And Minimal Nix

Reuse `aq-model-switch`; extend it with:
- `aq-model-switch unload`: stop gen-slot llama.cpp service and wait for process exit.
- Optional `--json` status output for controller diagnostics.
- Existing symlink swap remains the only model-selection primitive.

Add a minimal controller rather than a full new scheduler:
- A small systemd service or dispatch-adjacent daemon maintaining slot state and locks.
- No queue ownership and no scheduling policy duplication.
- It exposes local status/transition commands or a small Unix-socket/localhost API for dispatch.

Minimal Nix recommendation:
- Keep existing `useSymlink` model path for `:8080`.
- Add/configure `fastLaneServer` on `:8082` as a separate resident small-model service.
- Keep gen-slot `:8080` service stoppable/restartable via `aq-model-switch`.
- Add the controller unit with permission to call `systemctl stop/restart` only for the gen-slot service and read service health.
- Do not introduce a second scheduler service.

## Top 3 Design Decisions

1. Separate policy from mutation: controller owns state/policy; `aq-model-switch` remains the process/symlink primitive.
2. P1 arrival does not automatically preempt active 35B work; eviction is driven by VRAM/RAM safety and 8B coexistence rules.
3. Swap cooling is represented as `LOCAL_DELAYED` admission back-pressure with retry metadata, never as blocking sleeps or dropped local work.
