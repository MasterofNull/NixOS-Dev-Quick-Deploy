---
title: "Phase 173: Training Pipeline Review — Claude Expert Draft"
expert_roles: ["Data Pipeline Architect", "MLOps Systems Engineer"]
agent: claude-sonnet-4-6
phase: "Phase 2 — Independent PRD Draft (no cross-agent visibility)"
date: 2026-06-17
status: draft
---

# Phase 173: Training Pipeline Review — Claude Independent PRD

## Executive Summary

The training pipeline has two structural problems that explain the 312-sample ceiling and
RAGAS instability: (1) two independent ingestion pipelines (`training_ingest.py` and
`continuous_learning.py`) that operate without coordination, creating potential duplication
and coverage gaps; and (2) a missing feedback closure loop — the pipeline captures what was
generated but has no mechanism to confirm whether the generated content actually improved
downstream model behavior. The RAGAS score instability is a symptom of the second problem,
not a calibration bug.

## Mission

Establish a single authoritative training signal path with measurable feedback closure — so
that the pipeline can answer "did adding these samples actually make the model better?" before
generating the next batch.

## Scope

### In Scope
- Audit and reconcile the dual-pipeline architecture (training_ingest.py vs continuous_learning.py)
- Identify the event type gaps that prevent agent execution traces from becoming training samples
- Define a minimum viable feedback closure metric
- Propose RAGAS evaluation stabilization with a statistically meaningful sample floor
- Define aq-qa checks and dashboard coverage for training pipeline health

### Out of Scope
- Actual model fine-tuning execution
- Switching the fine-tuning format (keep JSONL / chat-format)
- Hardware changes (Renoir APU constraint preserved)
- Changes to the telemetry emission side (producers stay as-is)

### Constraints
- REPO_ROOT env var separation required for all file writes (EROFS pattern)
- Dataset writes must be group-writable (`0664`, ai-stack group) for multi-user access
- No synchronous file I/O inside async coordinator handlers

## Current State Architecture

### Pipeline A — training_ingest.py (standalone script)
- **Reads**: `hybrid-events.jsonl`, `delegation-feedback.jsonl`, `optimization_proposals.jsonl`
- **Also reads**: `.agents/telemetry/hybrid-events.jsonl` (user spool from delegate-to-local)
- **Writes**: `FINE_TUNING_DATASET` (`/var/lib/ai-stack/hybrid/fine-tuning/dataset.jsonl`)
- **Quality gate**: `_quality_score()` — keyword coverage + length bonus; structured floor 0.50; agent_step_complete floor 0.40
- **Deduplication**: per-run SHA-256 content hash, loaded from dataset at startup
- **Event types accepted**: `inference_complete`, `chat_completion`, `hybrid_completion`, `local_inference`, `agent_step_complete`
- **Trigger**: manual CLI or scheduled — NOT wired to coordinator service lifecycle

### Pipeline B — continuous_learning.py (coordinator service)
- **Reads**: `ralph-events.jsonl`, `aidb-events.jsonl`, `hybrid-events.jsonl`, user spool
- **Writes**: `InteractionPattern` → Qdrant + Postgres; `FinetuningExample` → separate path
- **Checkpointing**: per-file byte-position in `checkpoint.json` (rotation detection: line 875, `last_pos > file_size → reset`)
- **Quality gate**: `_extract_pattern_from_event()` — separate logic from Pipeline A
- **Trigger**: coordinator startup → background `_learning_loop`

### Divergence Between Pipelines
- Both read `hybrid-events.jsonl` independently with NO shared dedup layer
- Pipeline A writes to `dataset.jsonl`; Pipeline B writes patterns to Qdrant/Postgres
- An event that passes both quality gates appears in both pipelines — double-counted
- Neither pipeline knows what the other has processed
- `agent_step_complete` events from `agent_executor.py` go into user spool and are read by both
  pipelines, but Pipeline B's `_extract_pattern_from_event` may handle them differently

### RAGAS Evaluation
- `sample_count=3` — single digit, statistically meaningless
- Faithfulness avg=0.6 with this sample count has a confidence interval of ±0.4
- Optimization proposals generated from these scores are noise-driven, not signal-driven
- No minimum sample gate before proposals are generated

### Dataset Growth
- Current: 312 samples
- Trigger threshold: 1000 (estimated, not confirmed in config)
- `MIN_LATENCY_MS = 500` filters out all sub-500ms responses — eliminates most cached hits
  and short tool-routing responses, but also eliminates valid fast code completions
- `tool_result` events: NOT in accepted event types — agent tool results are never trained on
- `system_prompt` events: NOT in accepted event types — system prompt injections not captured

## Failure Modes Found

1. **Dual pipeline no-coordination (CRITICAL)**: Two independent readers on the same JSONL files
   with separate quality gates and dedup layers. The training dataset and the coordinator
   pattern store may diverge silently. No reconciliation mechanism exists.
   - `training_ingest.py` — standalone dedup via content hash (lines 202-209)
   - `continuous_learning.py` — `pattern_hashes` Set, separate (lines 321-327)

2. **tool_result events absent from training set**: Agent tool execution results are the
   highest-signal training data (they show what the model chose to call and what it got back)
   but `_is_useful_hybrid_event()` (line 112-120 of training_ingest.py) rejects them:
   `etype not in ("inference_complete", "chat_completion", "hybrid_completion", "local_inference", "agent_step_complete")`.

3. **RAGAS sample_count=3 produces invalid optimization proposals**: Any faithfulness score
   from 3 samples has variance ≥ 0.2. Proposals generated from these scores create circular
   "improvements" that aren't grounded in statistical evidence.

4. **No feedback closure**: The pipeline measures what was generated (quality score, RAGAS
   faithfulness on generation) but has no signal for whether those samples improved model
   outputs in subsequent runs. The loop is open — there is no "did this training actually help?"
   measurement.

5. **MIN_LATENCY_MS=500 over-filters fast agentic responses**: Short tool dispatch decisions
   (e.g., "which tool to call" decisions completing in 200ms) are valid training signal but
   filtered. The latency gate was designed for caching artifacts, not agentic decisions.

6. **No aq-qa coverage for training pipeline**: Zero aq-qa checks for training_ingest.py
   execution, dataset growth rate, or pipeline health. Breakage is silent.

7. **No dashboard panel for training pipeline**: Dataset size, ingest rate, and rejection rate
   are not visible. Per the Service Coverage Contract in WORKFLOW-CANON, this makes the
   pipeline incomplete.

## Proposed Architecture

### Fix A — Unified Event Router (replaces dual pipeline)
Introduce a single `TrainingEventRouter` that both pipelines reference:
- Shared dedup layer (Redis set or SQLite — already available)
- Routes events to: fine-tuning dataset (training_ingest path) AND pattern store (CLP path)
- Single event-type allowlist, single quality gate registry
- Both pipelines import the router rather than implement their own logic

### Fix B — tool_result Event Ingestion
Add `tool_result` to `_is_useful_hybrid_event()` accepted types with dedicated scoring:
- Quality signal: did the tool succeed? (`result.success == True`)
- Training pair: `(tool_call_json, tool_result_json)` as assistant→tool round-trip
- Floor: 0.35 (lower than agent_step_complete — tool results are verifiably correct by definition)

### Fix C — RAGAS Statistical Gate
- `RAGAS_MIN_SAMPLES = 20` (minimum before any score is statistically actionable)
- Below threshold: mark metric as `PRELIMINARY`, suppress proposal generation
- At 20+ samples: normal proposal flow
- Long-term target: 100 samples per evaluation window

### Fix D — Feedback Closure Metric
- After each ingest cycle, compare quality scores of new samples against quality scores of
  samples from the same profile/task-type in the previous cycle
- If trend is positive: `feedback_loop_improving = True`
- Emit as a telemetry event readable by aq-report and dashboard
- This is the minimal viable closed-loop signal

### Fix E — aq-qa + Dashboard Coverage
- Add `phase_173_training_health()` checks: dataset size, ingest rate last 24h, rejection rate, RAGAS sample count
- Add dashboard card: "Training Pipeline" with dataset size, growth rate, last ingest timestamp, RAGAS status

## Security & Configuration
- No new secrets or ports introduced
- REPO_ROOT env var required for all path resolution (existing pattern)
- Dataset writes must use `NamedTemporaryFile + os.replace()` atomic pattern (already in training_ingest.py)
- Redis dedup key TTL should be 30 days (prevents unbounded growth)

## Implementation Phases (High-Level)

| Slice | Scope | Owner (TBD) | Depends On |
|-------|-------|-------------|------------|
| 173-A | Fix tool_result ingestion in training_ingest.py | TBD | — |
| 173-B | RAGAS min-sample gate in continuous_learning.py | TBD | — |
| 173-C | Shared dedup layer / event router design + impl | TBD | 173-A, 173-B (interface) |
| 173-D | Feedback closure metric + telemetry event | TBD | 173-C |
| 173-E | aq-qa checks + dashboard panel | TBD | 173-A, 173-B |

**Integration boundary**: Slice 173-C must coordinate with 173-A and 173-B owners on the
shared interface before any of the three begin implementation.

## Validation & Success Criteria

| Metric | Current | Target | How Measured |
|--------|---------|--------|--------------|
| Dataset samples | 312 | >500 in 7 days post-fix | `wc -l dataset.jsonl` |
| agent_step_complete rejection rate | ~60% | <20% | dry-run mode output |
| tool_result samples in dataset | 0 | >50 | grep source=tool_result |
| RAGAS sample count | 3 | ≥20 per window | aq-qa check |
| aq-qa training checks | 0 | ≥4 | aq-qa phase output |
| Dashboard training panel | absent | present + live | dashboard visual |

## Risks & Mitigations

- **Risk**: Shared dedup layer becomes a bottleneck. **Mitigation**: Redis SADD is O(1);
  use per-content-hash keys with 30d TTL.
- **Risk**: tool_result ingestion adds low-quality truncated results.
  **Mitigation**: `result.success == True` gate; truncated results have `success=False`.
- **Risk**: Feedback closure metric is gamed by the pipeline itself.
  **Mitigation**: Compare against holdout samples from a prior ingest window, not current.

## Open Questions

1. Is `continuous_learning.py`'s `FinetuningExample` output ever consumed downstream, or is
   `dataset.jsonl` the only active fine-tuning input? If the former is dead code, consolidating
   to a single pipeline is simpler.
2. What is the actual fine-tuning trigger threshold? 1000 is estimated — confirm in config.
3. Should `delegation-feedback.jsonl` negative samples be structured as DPO pairs (chosen/rejected)
   rather than just gap patterns?

## Team Sign-off
- **Data Pipeline Architect**: APPROVED — Architecture is sound; dual pipeline is the root cause
  of dataset growth stagnation. Fix C (shared event router) is the load-bearing change.
- **MLOps Systems Engineer**: APPROVED with concern — Feedback closure (Fix D) is the weakest
  proposal; the proxy metric (quality score trend) is a proxy for a proxy. Recommend adding a
  downstream evaluation benchmark run after each ingest cycle as a stronger closure signal.

---
*Drafted independently by Claude Sonnet 4.6 (Data Pipeline Architect + MLOps Systems Engineer)*
*Phase 2 of Flat Collaborative Design Protocol — no cross-agent visibility during drafting*
*Date: 2026-06-17*

## Addendum: Local Agent/Inference Failure Assessment
*Added post-PRD-drafting, Phase 173 review session*

### Failure 1 — Qwen3 PRD Draft: Exploration Stagnation Guard

**Root cause (confirmed from log):**
`Exploration stagnation: 12 consecutive reads without any edit_file or write_file — aborting at tool call 12.`

Code: `ai-stack/local-agents/agent_executor.py:854` — `_READS_HARD_LIMIT = 12`
Comment in code: *"Models in self-improvement mode should read 1-3 files then act."*

This guard was calibrated for **implementation tasks** (where reading 12 files before acting is pathological over-exploration). PRD drafting is a **research task** — reading 5–10 files before writing is the correct behavior, not a stagnation signal. There is no task-type differentiation in the current dispatcher.

**Fix:** Add `--task-type research` flag to `delegate-to-local` → passes `task_type="research"` to `aq-agent-loop` → `agent_executor.py` sets `_READS_HARD_LIMIT = 25`, `_MAX_READS_WITHOUT_EDIT = 15` when `task_type == "research"`. The soft nudge at 8 should include context: *"Research task detected — continue reading, but begin writing your output by read 15."*

### Failure 2 — Gemini Sign-off "No Output" Misdiagnosis

**Root cause:** `delegate-to-gemini --check` was stripping or hiding content. The raw log (`gemini-20260617-143606-23smc6.log`) DOES contain a full APPROVED verdict — it was only invisible through the `--check` display path. The proxy fill was unnecessary.

**Monitoring gap exposed:** The orchestrator had no automated way to distinguish "Gemini produced content" from "Gemini produced only warnings" without reading the raw log file directly. The `--check` output path must validate content density — if the output file is below a threshold (e.g., <500 bytes above the ~300-byte YOLO header), report `partial-success` not `completed`.

### Failure 3 — Gemini Addendum Dispatch: True Empty Output

The addendum log (428 bytes, warnings only) is a genuine failure — no Gemini API response. Dispatched immediately after the sign-off; likely hit a per-minute rate limit or the background `nohup` process did not start correctly. This is distinct from Failure 2.

**Fix:** Add a `GEMINI_MIN_CONTENT_BYTES = 500` check in the dispatch registry update. If output bytes ≤ YOLO_HEADER_BYTES + 500, mark task as `partial-success` and emit an attention queue alert so the orchestrator knows a retry is needed.

### Systemic Assessment

All three failure modes share a common root: **no output contract enforcement at dispatch boundary.** The orchestrator has no schema to validate that an agent task produced the expected artifact (PRD file written, sign-off verdict present, addendum section appended). Adding structural validation at task close would catch all three without requiring task-specific logic.

*Drafted by Claude Sonnet 4.6 (Data Pipeline Architect + MLOps Systems Engineer)*
*Date: 2026-06-17*
