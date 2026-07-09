# Model/Agent Stacking Audit — What We Use vs. What We Leave on the Table

**Date**: 2026-07-09 · **Author**: claude-fable-5 · **Status**: input to round `aqos-v1`
**Question**: are we fully leveraging agent/model stacking across remote and local? **Answer: no — roughly a third.** Horizontal fan-out is real; vertical composition (models feeding models) is mostly absent.

## What we DO leverage today

| Pattern | Where | State |
|---------|-------|-------|
| Horizontal fan-out (same task → all lanes, consensus) | aq-collab-round, aq-loop --fanout | LIVE — the strongest capability |
| Teacher-student (remote corrects local failures → training data) | closed loop: codex teacher → HITL → ingest → train | LIVE — the crown jewel; rare in the wild |
| Retrieval stacking (embed → RAG → generate) | hybrid-coordinator, :8081 embeddings, Qdrant | LIVE |
| Context pre-fetch stacking (cheap profile prepares context for coding profile) | embedded-assist → local-coding | PARTIAL (wired, utilization unmeasured) |
| Payload/context compression before model calls | lean-ctx, headroom, RTK | PARTIAL (Claude-side mostly; not systematic on delegation payloads) |
| Tiered model routing (task class → tier) | model_tier.py, model-coordinator tiers | **JUST ACTIVATED** (F2.5 slot_queue, 2026-07-09) — but see gap 1 |

## What we DON'T leverage (ranked by value-per-effort)

1. **Small resident model — the SMALL_RESIDENT tier routes to a model that does not exist.** Classification, JSON repair, tool-schema validation, short critique (5 of 13 task classes) are billed to the 35B at 1-3.45 tok/s when a 0.6-1.7B on CPU would do them at 20-50 tok/s WITHOUT holding the big slot. This is the single largest waste in the system. ⚠ Hardware honesty: 27GB budget is fully allocated (22.5 model / 1.0 KV / 3.0 OS) — deploying it HERE requires rebudgeting (one quant step down on the 35B buys ~2-3GB) or treating it as the first fleet-node feature. Decision needed, not just work.
2. **Cascade with confidence escalation** — nothing tries local-first-then-escalate on measured confidence; fan-out runs lanes in parallel (redundancy, not economy). A verifier-scored cascade (local answer → small-model/heuristic verdict → escalate only on low confidence) cuts remote spend on the long tail of easy tasks. Builds directly on the closed loop's eval scorer.
3. **Draft-and-polish A2A** — local drafts the 80% (free, private), remote edits/verifies the 20% (cheap: editing costs far fewer tokens than authoring). Today lanes produce parallel *alternatives* that get aggregated; nobody composes local-draft→remote-polish as a pipeline. Highest-leverage remote-cost reducer available.
4. **Speculative decoding** — llama.cpp supports --model-draft natively; a small draft model accelerates the 35B's own decoding 1.5-2.5× on the same slot. Same RAM caveat as (1); same rebudgeting decision unlocks both.
5. **Distillation pipeline dormant** — `ai-stack/model-optimization/distillation.py` exists as a stub while the closed loop already captures exactly the remote-teacher outputs distillation needs. The flywheel's last gear was built and never mounted.
6. **Local reranker** — RAG returns vector hits unreranked; a tiny cross-encoder reranker (CPU, ms-scale) before generation measurably lifts answer quality for zero remote cost.
7. **Model-level consensus reserved for rounds only** — high-stakes single decisions (commit gates, security verdicts) could cheaply take 2-of-3 votes (local + 2 remote lanes) but always get one model's opinion.
8. **Batch amortization** — P3 background small tasks could batch into single prompts (N classifications per call) instead of N slot acquisitions; the new banded queue makes the batching point obvious (drain P3 batch when slot frees).

## Recommended slices (feed into ratified plan, extends WS8)
- S1: Rebudget decision + deploy small resident model; wire SMALL_RESIDENT tier through slot_queue concurrency=3 (unblocks 1, 4).
- S2: Draft-and-polish pipeline as an aq-collab-round mode (`--mode cascade`) (3).
- S3: Confidence-scored escalation in dispatch using the existing eval scorer (2).
- S4: Mount distillation.py onto the closed loop's captured teacher outputs (5).
- S5: Local reranker in hybrid-coordinator RAG path (6).
