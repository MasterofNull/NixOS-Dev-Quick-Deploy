# claude (orchestrator) — F2 impl-plan review (self-review + risks for the team)

Verdict: APPROVE_WITH_CHANGES. The Phase-A/B split and F2.1–F2.4 module decomposition faithfully realize
the ratified design. Three things need the team's call before Phase B, and one is a hard hardware constraint.

## HARD constraint the team must confront — RAM budget for a resident fast-lane (F2.5)
Current envelope (from INFRASTRUCTURE-CONSTRAINTS): 27 GB usable RAM; the 35B UMBM ≈ 22.5 GB model + 1.0 GB
KV + 3.0 GB OS reserve ≈ 26.5 GB. That leaves ~0.5 GB — **a resident small model on :8082 (phi-4-mini ~2–3 GB)
CANNOT coexist with an always-resident 35B.** So the ratified "resident small + 35B session-mode" is not
optional framing — it REQUIRES the 35B to become **session-mode (loaded on demand, unloaded when idle)**,
not permanently resident. That is a real operational change to how llama-cpp is run today (active.gguf is
always loaded). F2.5 must account for: 35B load/unload latency, who triggers the swap, and what happens to an
in-flight 35B request when a P1 interactive job arrives. This is the crux risk — flag it, don't gloss it.

## Open questions for consensus
1. **Phase-A "dead code" until F2.5?** F2.1–F2.4 are pure modules validated in isolation but deliver zero
   runtime value until F2.5 wires them into dispatch.py. Accept that (clean, testable, low-risk increments)
   or should a THIN wiring land earlier so we measure real routing sooner? I lean: keep Phase A pure; wire in
   F2.5 behind a default-off flag.
2. **GBNF builder dependency.** The F2.2 CACHE is pure. But the real builder (JSON-schema→GBNF) + actually
   sending `grammar` to llama.cpp — does that need anything rebuild-gated, or does the current llama.cpp
   already accept a `grammar` field at runtime? If runtime-only, F2.2 stays fully Phase A; confirm.
3. **Scheduler authority vs the coordinator.** Does the F2 scheduler live IN dispatch.py, as a new sidecar
   service, or inside the fast-lane server? The plan implies a lib used by dispatch; codex should confirm the
   ownership boundary so F2.5 doesn't build a competing scheduler.

## Risks I flag
- **VRAM Pool Manager swap cost.** Unloading 8B / loading 35B via systemd or process control is heavy on the
  APU; the "30s swap cooling gate" from the design must be real back-pressure, not a sleep. Ties to F2.3.
- **35B-on-CPU (n_gpu_layers=0) is NOT assumed** — the plan correctly gates it as F2.6 measure-before-adopt.
  Keep it that way; do not let F2.5 bake in the CPU flip without the A/B numbers.
- **Never-skip-local must survive scheduling.** A `local-delayed` lane (F2.3) must stay quorum-admissible in
  F1 (AMEND path) — the scheduler must never let a delayed local drop out of a round. This is the whole point.

## Top 3 plan changes I'm proposing
1. Make explicit in F2.5 that enabling the fast-lane REQUIRES converting the 35B to session-mode (load/unload);
   add the load/unload + in-flight-preemption design to F2.5 (it's the real hard part, currently under-specified).
2. Confirm F2.2's real GBNF path is runtime-only (no rebuild) so the cache stays Phase A; if llama.cpp needs a
   build flag for grammars, move that sliver to Phase B.
3. Pin the scheduler ownership boundary (lib used by dispatch.py, default-off flag) before F2.1 so the modules
   are built to the right integration seam.
