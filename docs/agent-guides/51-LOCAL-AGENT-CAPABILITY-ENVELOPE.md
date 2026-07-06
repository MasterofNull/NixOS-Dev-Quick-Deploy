# 51 — Local Agent Capability Envelope (measured)

Shared, all-agent reference. Where the LOCAL agentic loop (`aq-agent-loop` /
`delegate-to-local --mode agent`, Qwen3.6-35B on the single-slot Renoir APU)
actually succeeds vs fails — established by controlled experiments, not anecdote.

## The measured envelope

| Task shape | Result | Evidence |
|---|---|---|
| Bounded single-command (e.g. `aq-wiki --section`) | ✅ completes | 1 tool call |
| Single edit, even on a large (550-line) file | ✅ completes | EXP3: 4 reads, 2 edits, compiles |
| Raw multi-edit / multi-site over a large file | ❌ read-loops, 0 edits | EXP1 (4 reads), EXP2 (15 reads) |
| Multi-edit **via decomposer** (`aq-sequential-edit`) | ✅ completes | Live demo: both steps pass, 0→2 edits |

## The key result (counter-intuitive)
The multi-edit failure is **NOT** the stagnation guard and **NOT** file size:
- Relaxing the guard (`AI_AGENT_REPEATED_READ_PATH_LIMIT` 4→15) just made it
  read-loop longer — 15 reads, still 0 edits (EXP2). The guard was protecting the
  single slot from a doomed run.
- The same model edited the same 550-line file fine for ONE change (EXP3).

So the boundary is **multi-edit working memory**: Qwen drowns planning ~6 edit
sites at once and never transitions read→edit.

## How to work within it (routing rules)
1. **Decompose** multi-edit slices into single-edit sub-tasks for local. Use
   `scripts/ai/aq-sequential-edit run <manifest.json>` — dispatches one atomic edit
   per run with `py_compile` validation between steps. Each step is inside the
   proven envelope.
2. Or **route** whole multi-edit slices to the remote lane (Gemini, once the SOPS
   key is a Google AI Studio key) or orchestrator-direct.
3. Reserve raw local `delegate-to-local --mode agent` for bounded single-edit /
   single-command / analysis-with-checkpoint work.
4. **Do NOT** just relax the stagnation guards — measured to waste the slot.

## Instrumentation (for further capability testing)
Stagnation guards are env-tunable (defaults unchanged): `AI_AGENT_REPEATED_READ_PATH_LIMIT`
(4), `AI_AGENT_IMPL_MAX_READS_WITHOUT_EDIT` (8), `AI_AGENT_IMPL_READS_HARD_LIMIT`
(12), `AI_AGENT_ANALYSIS_MAX_READS` (24), `AI_AGENT_ANALYSIS_READS_HARD_LIMIT` (80).
Vary one, hold the rest, measure completion + read/edit tool trace.

## In-loop mitigation
`agent_executor.py` emits a single-edit-first nudge when reads-without-edit hits the
soft limit: "make exactly ONE edit now, others later" — reframing the stuck task to
a step inside the envelope instead of an overwhelming "do all edits."
