# Frontier reference library — what our models check against

This directory is the **local reference library** for gap + parity research: the
distilled, verified frontier corpus our models query offline. It is deliberately
small, curated, and evidence-backed — not a link dump.

## The three layers (and what each is for)

1. **The source catalog — `../sources.yaml`** (27 sources, 24 primary).
   *What we watch.* Curated per parity pillar (agent-architecture, context-memory,
   local-inference, os-security, evaluation), each tagged primary vs secondary and a
   scan cadence. The owner edits this file to add/remove sources — never re-prompted.

2. **The verified backlog — `../BACKLOG.jsonl`** (append-only, deduped).
   *What we found and decided.* Each record = one verified technique → the AQ-OS
   measurement it maps to → a proposed bounded slice + acceptance goal → an HITL
   status (new/approved/deferred/dropped/scheduled) → the `source_ids` that surfaced
   it. This is the index a model checks to answer "have we already evaluated X?"

3. **Distilled technique notes — files in THIS directory.**
   *What the evidence actually says.* One short note per adopted/monitored technique
   (corrected claim + primary source + our mapping), written so the local model can
   RAG over it during parity research without re-reading whole papers. Seeded from
   the verified evidence map in `../DESIGN.md §2`; grows as the loop runs.

## How a model "checks against" it (offline, local-first)
- Structured lookups: `scripts/ai/aq-frontier list|digest|source-metrics` and reading
  `BACKLOG.jsonl` directly — deterministic, no model call needed.
- Semantic lookups: these notes + the backlog are intended to be ingested into the
  existing RAG / Understand-Anything knowledge graph (FA-2 integration) so a model
  can ask "what's the frontier state on speculative decoding for our model?" and get
  our *verified, corrected* answer (e.g. "no gain on Qwen3.6-35B-A3B") instead of a
  hallucinated or stale one.

## How we assess + refine the library (metrics)
- `aq-frontier source-metrics` scores each source by **surfaced** (candidates it
  produced) and **adopt_rate** (fraction we chose to adopt). High adopt_rate = keep
  and prioritize; surfaced-but-zero-adopt = watch for noise; surfaced 0 over several
  cycles = candidate for pruning.
- `aq-frontier sources` reports **coverage** — sources per pillar and any pillar
  lacking a primary source (a coverage risk to fix by adding a source).
- Every adopt still passes the **benchmark gate** (baseline before/after on our
  hardware) before it reaches production — the library informs decisions, it never
  bypasses measurement.

## Adding a distilled note
Name it `<technique-slug>.md`, keep it to: corrected claim (1–3 lines), primary
source (dated), our AQ-OS mapping, and the backlog id. Link related notes with
`[[slug]]`. Keep it short — this is a reference the model loads on demand, not a paper.
