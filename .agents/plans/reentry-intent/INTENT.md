# Created Intent — Canonical Workflow Re-entry (2026-07-07)

This is the seed intent for a full lifecycle pass (intake → intent → fan-out → per-agent expert teams →
research/ground/debate → consensus → consolidated PRD + plan). Every agent (codex, local, antigravity,
claude) forms an expert team, works the intent, and proposes consolidated next steps + PRD structure.

## North star (original design + engineering intent — do not drift from this)
This is a LOCAL-FIRST AI harness whose PURPOSE is to **continuously improve the locally-hosted models**
by leveraging remote agents — not merely to route work to whichever agent is strongest. "Never skip local"
exists because every local engagement is a training/refinement opportunity. Success = the local models get
MEASURABLY better over time at reasoning, tool use, research, and code. The harness also improves HOW it
builds (the flat-collaborative factory). Both matter; the model-improvement goal is the one currently at risk.

## Where we are (committed state)
- **F1 round.json state machine — COMPLETE + live** (33/33). Typed rounds, never-skip-local extractor,
  idempotent aggregation, durable AMEND; aq-collab-round migrated non-breaking.
- **F2 Phase A — COMPLETE** (27/27): scheduler (MLFQ+aging), grammar_cache (canonical GBNF key), backpressure
  (never-skip-local mechanized via F1 quorum), model_tier (3-tier routing). Pure, rebuild-free.
- **Ratified designs (not yet built):** F2 session-mode (35B load/unload swap), F3 (CapabilityLease + OTel +
  signed A2A envelope).
- **Model selection requirements + eligibility gates CODIFIED**; **Granite 4.1 8B** added as first candidate.
- HELD (user-gated): F2.5 Nix + rebuild, F2.6 A/B bench, F3 impl, Granite download+bench.

## The driving finding (why we are re-entering)
**Local is NOT improving from its failures — the loop is open, not closed.**
- The learning loop is dormant: `training-loop-results.jsonl` last ran 2026-05-27; 3 runs total; every run
  `ingest={samples_added:0, dataset_total:0}` — ZERO training samples ever captured; checkpoint is `{}`.
- This session local emitted the IDENTICAL text-instead-of-tool-call failure 3× + truncation + scaffolding-only.
  A working loop learns after the first.
- We have been building RESILIENCE (extract_contribution salvage, never-skip-local inclusion) rather than
  FIXING the producer or CLOSING the improve-from-failure loop. This partially violates "fix the producer".
- The one genuine producer-fix in flight (F2.2 GBNF constrained decoding) is only the CACHE, not wired into
  live dispatch requests.
⇒ The build order is not currently serving the north star.

## The intent (what each expert team must produce)
Given the north star, the committed state, and the finding — formulate the **consolidated next steps and the
PRD(s) we should write.** Concretely, each team must:
1. **Research + ground** (cite real files/primitives + external technique/papers where relevant): what is the
   MINIMAL closed learning loop for THIS harness? (failure-capture hook → labeled dataset → fine-tune/refine →
   eval → promote). What existing pieces already work (aq-local-training-loop, aq-refine, bench-local-agent,
   store_memory, RAG error-solutions, the extract_contribution fallback hook, F2.2 GBNF) vs what is missing/broken?
2. **Debate the prioritization:** CLOSE-THE-LOOP (failure→dataset capture + reactivate training + wire GBNF
   enforcement into live dispatch + before/after bench) vs CONTINUE the F2.5/F3 scaffolding. Which first, and
   WHY — argue it against the north star, not preference. Is there a sequencing that does both without waste?
3. **Producer-fix vs resilience:** which of local's failure classes (text-as-tool-call, role-confusion,
   truncation, multi-edit stamina) are fixable by GBNF/decode-params/prompt/template (no retrain) vs require
   fine-tuning? Map each failure → the cheapest real fix.
4. **Define the PRD(s):** name the PRD(s) to write (objective, success metrics that are MEASURED not assumed,
   scope, non-goals), and the phased plan. Success metrics must include a local-improvement metric over time.
5. **Validate against constraints (HARD):** never-skip-local; NO API keys; NixOS declarative-only; hardware
   envelope (27 GB RAM, 4 GB VRAM, n_gpu_layers≤12, parallel=1, 1–4 tok/s); the eligibility gates
   (config/local-model-requirements.md); automation-first (batch rebuilds for review); anti-gaming (fix the
   producer, never fake passing). Flag anything that violates these.

## Output
Write YOUR OWN file `.agents/plans/reentry-intent/<AGENT>.md` (codex | local | antigravity | claude). Give:
the grounded minimal-closed-loop design, your prioritization verdict (close-loop vs scaffolding, with the
argument), the failure→fix map, the proposed PRD(s) + phased plan + MEASURED success metrics, and constraint
validation. Rank your top 3 recommendations. This consolidates into the PRD(s) and the plan for our next steps.
