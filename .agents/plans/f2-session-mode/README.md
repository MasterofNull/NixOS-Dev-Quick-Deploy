# Collaborative Round — f2-session-mode

Opened: 2026-07-08T06:06:51Z
Target artifact (if a review round): .agents/plans/f2-session-mode/BRIEF.md

## Task
DESIGN ROUND — 35B session-mode load/unload mechanics (the brief is inlined above). This is the under-specified hard part of F2 Phase B; design it before any Nix. Answer the 7 questions concretely: (1) who triggers 35B load/unload + exact conditions; (2) in-flight request handling on P1 preemption given :8080 (35B) and :8082 (fast-lane small) are SEPARATE processes — when must the 35B actually be evicted vs when can both run under the 27GB ceiling; (3) 30s swap-cooling as REAL back-pressure via backpressure.py LOCAL_DELAYED (never-skip-local: delayed, never dropped); (4) unload-when-idle policy + timeout; (5) a gen-slot STATE MACHINE (UNLOADED/LOADING/RESIDENT_35B/RESIDENT_SMALL/SWAPPING) with legal transitions + who drives them, mirroring F1 round_state.py rigor; (6) failure/recovery on a mid-swap crash (tie to orphan/watchdog lessons); (7) reuse aq-model-switch (extend with unload) vs a new swap-controller — prefer reuse, minimal Nix. Build on the DONE primitives (aq-model-switch, scripts/ai/lib/scheduler.py, backpressure.py, model_tier.py) — do not reinvent. Rank your top 3 decisions. Write your OWN file .agents/plans/f2-session-mode/<AGENT>.md only.

## Protocol
Each agent writes its OWN file here — `codex.md`, `local.md`, `antigravity.md`, `claude.md`.
NEVER append to a shared file. The orchestrator aggregates into `AGGREGATE.md`.
- local[Qwen] runs long — the round stays OPEN for it; never skipped.
- antigravity (Antigravity IDE, real Gemini via its OWN OAuth) picks up the task from the inbox
  `.agent/archive/antigravity-inbox-20260709/f2-session-mode.md` and writes `antigravity.md`. No API keys.
