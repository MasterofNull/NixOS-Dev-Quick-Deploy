# Phase 173: Training Pipeline Review PRD

## Executive Summary
This PRD outlines the findings and proposed optimizations for the local AI agent training pipeline. Current telemetry ingestion is functional but suffers from signal dilution due to heuristic quality gates biased toward prose. Dataset growth is bottlenecked by high rejection rates for structured agent outputs. This phase focuses on hardening the quality signal, increasing evaluator stability, and accelerating high-fidelity dataset growth.

## Mission
To transform production telemetry into a high-quality, high-density fine-tuning dataset that accurately reflects successful agentic behaviors while ensuring pipeline reliability and evaluator statistical significance.

## Scope

### In Scope
- Quality scoring heuristic recalibration for agent-step events.
- RAGAS evaluation stability (sample count and baseline calibration).
- Training ingestion logic for `agent_step_complete` events.
- Telemetry rotation and checkpointing verification.
- Dataset growth acceleration strategies.

### Out of Scope
- Actual model fine-tuning execution (Phase 174+).
- Hardware provisioning for training.
- Modification of core inference engines.

## Constraints
- **Hardware:** Max 12 GPU layers (Renoir APU).
- **Latency:** Quality scoring must not block telemetry ingestion loops (async processing mandatory).
- **Storage:** Dataset must reside on writable partitions (not Nix store).

## Current State Architecture

### Telemetry Ingestion
- **File:** `ai-stack/local-agents/training_ingest.py`
- **Mechanism:** `TrainingIngestor` reads `hybrid-events.jsonl`, `delegation-feedback.jsonl`, and `optimization_proposals.jsonl`.
- **Heuristic:** `_quality_score()` combines keyword coverage (70% weight for prose) and length bonus (up to 0.3).
- **Agent Floor:** `agent_step_complete` events use a 0.40 floor (vs 0.65 default) but still rely on keyword coverage.

### Continuous Learning
- **File:** `ai-stack/mcp-servers/hybrid-coordinator/extensions/continuous_learning.py`
- **Mechanism:** Background loop (`_learning_loop`) processes batches, extracts `InteractionPattern`, and generates `FinetuningExample`.
- **Checkpointing:** JSON-based atomic writes via `Checkpointer`.
- **Resilience:** Circuit breakers for Qdrant/Postgres; disk pressure guards.

## Failure Modes Found

1.  **Keyword Bias (Signal-to-Noise):** `_quality_score()` penalizes concise, correct code or tool calls because they lack query-term repetition. Even with the `is_structured` boost (base 0.50), short responses are frequently rejected.
2.  **Evaluator Instability:** RAGAS faithfulness uses `sample_count=3`. With current variance, this leads to noise-driven "optimizations" that lack statistical validity.
3.  **Tool-Call Truncation:** `agent_step_complete` events where the model hit `max_tokens` (producing malformed JSON) are scored near 0.0 and rejected, losing the "failure pattern" signal.
4.  **Growth Bottleneck:** Dataset at 312 samples; trigger for fine-tuning is 1000. Current rejection rate (~60-70% for agent steps) delays the first training cycle by weeks.

## Proposed Architecture

### 1. Multi-Modal Quality Scoring
Transition from a single heuristic to event-type-specific scoring:
- **Prose (Inference):** Keep keyword coverage + semantic similarity (Embeddings-based).
- **Agent Steps:** Trust-but-Verify. If `event_type == "agent_step_complete"`, use the runner's `success` signal as a 0.80 base. Quality score then measures *optimality* (token efficiency, tool usage density) rather than *correctness*.

### 2. Evaluator Hardening
- **Min Sample Count:** Set `RAGAS_MIN_SAMPLES = 20`. Below this, metrics are marked as "PRELIMINARY" and do not trigger optimization proposals.
- **DPO Readiness:** Start labelling `delegation-feedback.jsonl` entries as "Negative" samples to enable future Direct Preference Optimization (DPO).

### 3. Ingestion Resilience
- **Truncation Handling:** Detect truncated JSON in `agent_step_complete`. Instead of rejection, ingest as a "Negative/Truncated" pattern for error-resolution training.

## Security & Configuration
- **Path Security:** Maintain `REPO_ROOT` separation; ensure telemetry is world-readable but dataset is restricted to the `ai-stack` user.
- **PII Scrubbing:** Ensure `scrub_telemetry_payload` is applied before pattern extraction (already in `continuous_learning.py`).

## Implementation Phases (High-Level)
1.  **Phase A (Signal):** Implement multi-modal scoring in `training_ingest.py`.
2.  **Phase B (Evaluator):** Update `continuous_learning.py` with minimum sample count gates and RAGAS baseline calibration.
3.  **Phase C (Resilience):** Add truncation detection and negative sample labelling.
4.  **Phase D (Verification):** Run a 24h backfill on existing telemetry to confirm dataset growth acceleration.

## Validation & Success Criteria
- **Measurable 1:** Dataset growth rate increases by >2x (rejection rate for successful agent steps drops from >60% to <10%).
- **Measurable 2:** RAGAS faithfulness variance drops by 40% with higher sample counts.
- **Measurable 3:** Zero data loss during simulated telemetry rotation (verified via `Checkpointer` logs).

## Risks & Mitigations
- **Risk:** Lowering the floor for agent steps introduces low-quality "hallucinated" successes.
- **Mitigation:** Rely on the `DirectRunner` verified success flag; only ingest steps that resulted in valid state changes.

## Open Questions
- Should we use `BGE-M3` embeddings for semantic quality scoring in the ingestor, or is the latency hit too high for a background script?
- Is 312 samples enough for a preliminary "curation" run before hitting the 1000 mark?

## Team Sign-off
- **Data Engineering:** APPROVED (Focus on ingestion reliability and throughput).
- **Pipeline Reliability:** APPROVED (Checkpointing and rotation logic is sound).
- **Quality Assurance:** APPROVED (Requirement for RAGAS sample count increase is critical).

---
*Drafted by Gemini-CLI (Architect Role) — 2026-06-17*
