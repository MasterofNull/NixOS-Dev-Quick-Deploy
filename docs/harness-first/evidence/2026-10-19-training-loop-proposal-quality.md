# Evidence — training-loop proposal quality gate — 2026-10-19

Trigger: owner rejected attention alert `attn-57e0078777684ea5` (proposal `loop-loop-20261017-170952-0`) as non-actionable and asked to improve the process so training feedback is valuable. The proposal's title was a truncated retrieval hit (`route_handler.py (score=26.89, source=ke`), rationale a list of retrieval hits, `expected_keyword_gains` empty, confidence defaulted to 0.5.

## Root cause (`scripts/ai/aq-local-training-loop`)
1. IMPROVE prompt dispatched in `hybrid` mode, so retrieval context leaked into the answer.
2. Non-JSON answers fell back to `{"raw": ...}` paragraphs that became proposals.
3. No validation: confidence defaulted to 0.5, empty gains accepted, title = first 80 chars of any text.
4. The model only saw case id/score/missing keywords, not the case prompt or its own failing answer.

## Change
- Prompt carries per failing case (max 5) the case prompt excerpt, the model's answer excerpt and missing keywords; allowed `change_type` list; one JSON example; "JSON array only".
- IMPROVE dispatched in `direct` (no-RAG) mode.
- No raw fallback: unparseable answer -> zero proposals + `improve_parse_failure` diagnostic.
- `_validate_proposal`: root_cause/change_description >= 40 chars and not retrieval-hit text; allowed change_type; non-empty gains that are actual missing keywords; explicit confidence in [0,1] and >= 0.6. Rejections recorded in `proposals_rejected` with reasons, never written to `optimization_proposals.jsonl`.
- Title = root_cause trimmed to 120 chars on a word boundary; `change_type` + failing case ids recorded; dedupe of pending `(change_type, root_cause)`.

## Validation
- `scripts/testing/test-training-loop-proposal-quality.py` — passed (junk proposal rejected, good proposal passes, missing confidence / out-of-set gains rejected, non-JSON -> none, prompt evidence, title, dedupe).
- `test-training-loop-trust-gates.py`, `test-local-training-loop-timeout-task-id.py` — PASS; `py_compile` clean.

## Review
Author-lane claude (sonnet implementer, claude orchestrator). Independent review: gemini agent CLI (antigravity lane) PASS_WITH_FOLLOWUPS — low: legacy pending rows without `evidence.root_cause` dedupe by title only; prompt case cap 8 -> 5.

## Activation (Rule 15)
- Integrated / ON: live in the next `ai-local-training-loop` run (script path unchanged; no flag).
- Validated: unit-level; first live run is the real-world check — deferred to the next scheduled run (dated 2026-10-19).
- Observable: run result carries `proposals_rejected` and `improve_parse_failure`; owner sees only proposals that pass the gate via `aq-alerts`.
- Intervenable: owner approve/reject via `aq-approve` / `aq-reject`.
