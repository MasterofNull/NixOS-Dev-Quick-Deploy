# Local Verified-Edit Completion PRD

Status: IMPLEMENTED_PENDING_LIVE_DOGFOOD
Owner: Codex orchestrator
Date: 2026-08-28
Evidence task: `local-20260828-064534-n1khvu`

## Problem

The local model produced the requested behaviorally correct edit by 790.3 seconds, but
the executor treated that success only as progress. It opened another ordinary
tool-capable 800-token turn, accepted a redundant third edit, and was terminated at
the 900-second wall. The repository result was correct while the task was falsely
terminalized as failed.

## Objective

For an explicitly declared single-file dogfood task, turn a successful in-scope write
into a typed completion candidate only after static coaching and the configured
behavioral command both pass. Give the model one short, non-tool synthesis opportunity,
then terminate successfully without another ordinary tool turn.

## Acceptance contract

- Eligibility requires an exact `DECLARED SINGLE-FILE SCOPE: <repo-relative-path>`
  marker, a successful write to that path, no accepted write outside that path, and an
  explicitly executed behavioral verification command with exit code zero.
- Rejected, coached, unverified, behaviorally failing, disabled-check, malformed-scope,
  and out-of-scope edits never produce a completion candidate.
- Candidate synthesis is exactly one call with at most 96 output tokens and no tools.
  Tool-shaped or empty synthesis output is not executed and falls back to bounded,
  deterministic completion text.
- Final task JSON, progress, and event evidence identify the typed completion path.
- Normal unmarked tasks retain current behavior; no tool, filesystem, shell, network,
  commit, or runtime authority expands.

## Implementation slice

1. `ai-stack/local-agents/agent_executor.py` — candidate eligibility, typed evidence,
   bounded no-tool synthesis, terminal success.
2. `scripts/ai/aq-agent-loop` — preserve candidate evidence in final summary/progress
   and wrapper completion event.
3. `scripts/ai/aq-local-dogfood-run` — emit the exact declared single-file marker for
   already bounded dogfood tasks.
4. `scripts/testing/test-edit-verify.py` — hermetic positive and fail-closed vectors.

## Validation

- `python3 scripts/testing/test-edit-verify.py`
- `python3 scripts/testing/test-agent-loop-event-streaming.py`
- `python3 -m py_compile ai-stack/local-agents/agent_executor.py scripts/ai/aq-agent-loop scripts/ai/aq-local-dogfood-run scripts/testing/test-edit-verify.py`
- Hash-bound fixture checks discovered by Tier0, with mechanical re-pin only when the
  behavior predicates remain true.
- One bounded live dogfood task after independent review and commit; no uncurated queue.

## Exclusions and next gate

- This does not declare the current model promoted or generally reliable.
- This does not reapply the reverted cancellation F1 subject.
- Completion-signal success must still pass independent exact-subject review and Tier0.
- Promotion remains governed by the full scored suite, latency, RAGAS, pinned artifact,
  and two consecutive qualifying runs.

## Independent code review

- Reviewer: Codex `/root/local_runtime_audit` (independent of implementation)
- Verdict: `PASS`
- Exact four-file code subject SHA-256: `0a27befbe78b36b79103c17b4ee31c95d5cfcac8ca8a7f2729762bb5a5c7d9e6`
- Focused evidence: edit verification 69/69 PASS; agent-loop event streaming PASS;
  grammar is suppressed in both request paths and synthesis output is never parsed or
  dispatched as a tool.
- Completed: reliability re-pin and Tier0 pre-commit gate (44 PASS, 0 FAIL).
- Remaining gate: final staged-subject review, atomic commit, then one bounded live
  dogfood task.
