# Slice 3 design — switchboard KV-stable semantic prune

**Author:** fable-5. **Status:** DESIGNED, not built (higher-risk; see constraints).
**Source:** Antigravity's verified finding — the switchboard's dynamic semantic
prune re-orders the prompt prefix per query, defeating llama.cpp prefix-cache reuse
→ full re-eval every turn.

## Current behavior (ai-stack/switchboard/switchboard.py)
- `_semantic_scores` (embed cosine via :8081) + `_lexical_scores` → RRF fusion →
  select `SEMANTIC_TOP_K` (default 8) non-system messages, and the selected set
  REPLACES the history, re-ordered by relevance. Because the physical prefix
  changes across turns, llama.cpp's cached prefix no longer matches → full
  prompt re-evaluation.

## Target (KV-stable)
Keep a STATIC contiguous prefix (system + core instructions + the most-recent N
turns, in original order) so the prompt's leading bytes are stable across turns.
Move the semantically-selected OLDER messages OUT of the main history stream into a
dedicated "## Relevant earlier context" scratchpad block placed AFTER the stable
prefix (same pattern as Slice 2b's agent scratchpad). Net: prefix-cache matches up
to the injection point; only the (short) scratchpad + newest turn re-evaluate.

## Constraints (why this is the careful slice)
1. **Double-frozen:** switchboard.py is hash-pinned in BOTH
   `local-delegation-reliability-golden.json` AND `local-inference-l2b-payload-golden.json`.
   The edit must re-pin switchboard's sha256 in BOTH + regenerate BOTH
   `stable_digests.source_manifest` self-consistency digests (the value each test's
   own execute_golden recomputes — see the Slice 2b lesson where a missed
   source_manifest caused a golden_digest_mismatch). Preserve switchboard's
   characterizations (defect D9).
2. **Live service:** activation needs `sudo systemctl restart ai-switchboard`
   (operator-only — Claude cannot restart). So the slice ships as
   built+reviewed+committed, ACTIVATION deferred to an operator restart cycle
   (Rule 15 — a dated deferral until restart).
3. **Refactor of working chat behavior:** higher regression risk than a new module.
   Must preserve: SEMANTIC_PRUNE_ENABLED / LEXICAL_ENABLED kill-switches, the
   circuit-breaker + retry around embed, the RRF fusion math, TOP_K semantics,
   and fail-open (embed down → current lexical/recency behavior). Behind a flag
   (e.g. SWB_KV_STABLE_PRUNE) defaulting OFF until validated, so the restart can't
   regress chat.

## Open design questions (resolve before build)
- Exact selection/assembly function that consumes the fused scores + produces the
  outgoing message list (read it fully — the excerpt shows scoring, not final
  assembly). Where in the payload build is the pruned list placed?
- N for the static recent-turn window (start N=3–4 pairs; measure).
- Does the scratchpad count against the model's context window enough to matter vs
  the KV-reuse win? (measure prefill time before/after.)

## Plan
Design-complete this doc (fill the open questions from the assembly function) →
careful implementer with the flag + double re-pin + both source_manifest regens →
independent review (live chat path) → commit with SWB_KV_STABLE_PRUNE=off →
operator enables flag + restarts switchboard → measure prefill time → default on.

## Acceptance
Flag-off = byte-identical current behavior. Flag-on = stable prefix bytes across
turns (measured), semantic context still available via scratchpad, fail-open
preserved, both golden manifests consistent (reliability + L2B tests green modulo
the pre-existing task_registry drift). Prefill-time reduction measured post-restart.
