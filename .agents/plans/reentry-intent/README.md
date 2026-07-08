# Collaborative Round — reentry-intent

Opened: 2026-07-08T06:43:41Z
Target artifact (if a review round): .agents/plans/reentry-intent/INTENT.md

## Task
INTENT / PRD-FORMULATION ROUND (the intent is inlined above — read it). Form your expert team and work the intent: the NORTH STAR is a local-first harness whose purpose is to continuously IMPROVE the locally-hosted models over time; the DRIVING FINDING is that this improve-from-failure loop is currently broken (training loop dormant since 2026-05-27, 0 samples ingested, local repeats identical failures within a session) — we have built resilience, not fixes/closed-loop. Produce: (1) the MINIMAL CLOSED LEARNING LOOP design for THIS harness, grounded in real existing primitives (aq-local-training-loop, aq-refine, bench-local-agent, store_memory, RAG error-solutions, the extract_contribution regex-fallback hook where we DETECT local emitting text-instead-of-tool-call, F2.2 grammar_cache) — what works vs what is missing/broken (e.g. samples_added:0 is a bug); (2) your PRIORITIZATION VERDICT with argument: CLOSE-THE-LOOP (failure->dataset capture + reactivate training + wire GBNF enforcement into live dispatch + before/after bench) vs CONTINUE F2.5/F3 scaffolding — which first and WHY vs the north star, and any sequencing that does both without waste; (3) a FAILURE->CHEAPEST-FIX map (text-as-tool-call, role-confusion, truncation, multi-edit stamina -> GBNF/decode/prompt/template no-retrain vs fine-tune); (4) the PRD(s) to write (objective, MEASURED success metrics incl. a local-improvement-over-time metric, scope, non-goals) + phased plan; (5) constraint validation (HARD: never-skip-local, NO API keys, NixOS declarative-only, 27GB/4GB-VRAM/n_gpu_layers<=12/parallel=1/1-4tok-s, eligibility gates in config/local-model-requirements.md, automation-first, anti-gaming fix-the-producer). Rank your top 3. Write your OWN file .agents/plans/reentry-intent/<AGENT>.md only.

## Protocol
Each agent writes its OWN file here — `codex.md`, `local.md`, `antigravity.md`, `claude.md`.
NEVER append to a shared file. The orchestrator aggregates into `AGGREGATE.md`.
- local[Qwen] runs long — the round stays OPEN for it; never skipped.
- antigravity (Antigravity IDE, real Gemini via its OWN OAuth) picks up the task from the inbox
  `.agent/collaboration/antigravity-inbox/reentry-intent.md` and writes `antigravity.md`. No API keys.
