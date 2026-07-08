# F2.5 Design Brief — 35B Session-Mode Load/Unload Mechanics

Purpose: settle the UNDER-SPECIFIED hard part of F2 Phase B before writing any Nix. The ratified F2 design
requires the 35B to become SESSION-MODE (load on demand, unload when idle) because a resident fast-lane
small model on :8082 cannot coexist with an always-resident 35B in 27 GB (35B ≈ 26.5 GB used). Design the
swap mechanics rigorously; this shapes the F2.5 Nix + the dispatch wiring.

## Hard constraints (grounding)
- 27 GB usable RAM; 35B UMBM ≈ 22.5 GB model + 1.0 GB KV + 3.0 GB OS reserve ≈ 26.5 GB. n_gpu_layers ≤ 12
  (Renoir APU, 4 GB VRAM). parallel=1 on the gen slot.
- VRAM Pool rule (ratified, antigravity): NEVER 35B + 8B concurrently in VRAM.
- EXISTING PRIMITIVE to build on: `useSymlink` (/var/lib/llama-cpp/models/active.gguf) + `aq-model-switch <key>`
  already stops the llama-cpp service, atomically updates the symlink, and restarts — a model swap with NO
  rebuild. The F1 scheduler (scripts/ai/lib/scheduler.py), backpressure.py (LOCAL_DELAYED), and model_tier.py
  (SMALL/MID/LARGE_SESSION) are DONE and pure — this design wires the LARGE_SESSION tier to a swap.

## Design questions (answer each concretely)
1. **Who triggers 35B load/unload?** The scheduler? dispatch.py? A dedicated swap-controller service? What is
   the authority + the exact trigger condition (a LARGE_SESSION job dequeued while 35B unloaded → load; idle
   timeout → unload)?
2. **In-flight request handling on P1 preemption.** A P1 interactive job arrives on the fast-lane while the
   35B is mid-generation. The fast-lane (:8082, small model) and 35B (:8080) are SEPARATE processes/ports —
   so does a P1 job even need to preempt the 35B, or only when VRAM/RAM contention forces an unload? Define
   precisely when the 35B must be evicted vs when both can run, given the RAM ceiling.
3. **30s swap-cooling as REAL back-pressure** (not a sleep). How does the cooling gate integrate with
   backpressure.py's LOCAL_DELAYED signal? A swap-in-progress → new LARGE_SESSION requests get LOCAL_DELAYED
   (admissible, never dropped — never-skip-local) until the swap settles.
4. **Unload-when-idle policy.** Idle timeout value? What counts as idle (no LARGE_SESSION job queued AND no
   in-flight 35B request for N s)? Who unloads (frees RAM so the fast-lane small model + 8B mid can be resident)?
5. **State machine for the gen slot.** Model the slot as states: UNLOADED / LOADING / RESIDENT_35B /
   RESIDENT_SMALL / SWAPPING. Legal transitions + who drives them. (Mirror the F1 round_state.py rigor.)
6. **Failure/recovery.** Swap fails mid-way (load OOMs, process crashes) → how do we recover without wedging
   the slot? Tie to the orphan/watchdog lessons.
7. **Reuse vs new.** Can aq-model-switch be extended (add unload = stop service, free RAM) or do we need a new
   swap-controller? Prefer reuse. What's the minimal Nix (a fastLaneServer service + a swap trigger) vs a
   full new scheduler service?

## Output
Write YOUR OWN file .agents/plans/f2-session-mode/<AGENT>.md (codex | local | antigravity | claude). Give the
gen-slot state machine, the trigger/authority model, the LOCAL_DELAYED integration, the idle/unload policy,
and the minimal-Nix recommendation. Rank your top 3 design decisions. Cite the existing primitives (aq-model-
switch, scheduler.py, backpressure.py) — build on them, don't reinvent.
