# Behavioral Verify Shell Quoting PRD

Status: ACCEPTED_PENDING_COMMIT
Owner: Codex orchestrator
Local implementer evidence: `local-20260828-064534-n1khvu`
Date: 2026-08-28

## Objective

Prevent a behavioral-verification file path from being interpreted as shell syntax when
substituted into the operator-declared `AQ_EDIT_VERIFY_CMD` template.

## Implemented scope

- `ai-stack/local-agents/agent_executor.py`: import `shlex` and substitute
  `shlex.quote(file_path)` for `{file}`.

The local model produced the exact requested edit by 790.3 seconds and touched no other
file. It then reached the 900-second wall without emitting completion, so the edit is
implemented but its task terminal disposition is follow-up-required.

## Remaining acceptance work

- Completed: hostile-file-name regression, `test-edit-verify.py` (53/53),
  syntax validation, and independent exact code-and-test subject review.
- Completed: Tier0 pre-commit gate (44 PASS, 0 FAIL).
- Pending: final staged-subject review and atomic commit.

## Exclusions

- No change to the operator command template, shell choice, tool authority, or runtime.
- No model promotion claim.

## Independent review

- Reviewer: Codex `/root/local_runtime_audit` (independent of implementation)
- Verdict: `PASS`
- Reviewed code-and-test subject SHA-256: `03908fa4e70ae37596eec69c8dd5179aea84b04ffd4dcb800f42fa83f6acc7f3`
- Validation: `python3 scripts/testing/test-edit-verify.py` — 53/53 PASS
- Finding: the quoted hostile path remains one literal argument under the existing `bash -c` contract; no shell, template, tool-authority, or runtime scope expanded.
