# AQ Inference Bench Plan

Status: implemented
Owner: codex
Date: 2026-06-29

## Slice

Implement the first safe repo-local inference benchmark matrix from `local-inference-runtime-matrix`.

## Steps

- [x] Add PRD and implementation plan.
- [x] Add benchmark config and schema.
- [x] Add `scripts/ai/aq-inference-bench`.
- [x] Add tests for validation, dry-run, localhost guardrails, and fake localhost execution.
- [x] Register the capability in the system catalog and validation registry.
- [x] Run focused checks and tier0 gate.
- [x] Commit with validation notes.

## Follow-Up Candidates

- Persist benchmark reports into the metrics database.
- Add dashboard cards for latest inference matrix results.
- Add admitted runtime profiles for vLLM, SGLang, Ollama, and MLX after capability-intake approval.
