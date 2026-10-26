# Evidence: Hybrid Coordinator ISO-8601 Timestamp Parsing Robustness

## Objective
Fix recurring event processing errors in `ai-hybrid-coordinator` caused by malformed or non-standard ISO-8601 timestamp strings (specifically `+00:00Z` dual-zone notation and trailing `Z` variants in `hybrid-events.jsonl`) that caused `datetime.fromisoformat()` to throw `Invalid isoformat string` and fail learning telemetry ingestion.

## Workflow/Session IDs
- Session ID: `57a807e7-c3e6-4e8e-833b-ce38fb8d47cd`
- PRD: `.agent/PROJECT-DURABLE-AGENTS-SOTA-UI-PRD.md`
- Issue ID: `rsi-6e45c88de3ad4e164a6da6cb`
- Branch: `fix/hybrid-events-isoformat-robustness-wave6`

## Delegation Decision
- Implementer: Antigravity orchestrator.
- Reviewer: Codex independent parity check.

## Commands Executed
- `/nix/store/h6rsdbc6bcfdn7z2dsvhvhbrpkcjzfgw-python3-3.13.15-env/bin/python3 -c "from extensions.continuous_learning import ContinuousLearningPipeline; print(ContinuousLearningPipeline._parse_event_timestamp('2026-10-07T21:15:22.750890+00:00Z'))"`
- `bash scripts/governance/tier0-validation-gate.sh --pre-commit`
- `bash scripts/testing/check-harness-first-pr-evidence-gate.sh`

## Validation Evidence
- Tested timestamp parsing directly across `2026-10-07T21:15:22.750890+00:00Z`, `2026-10-07T21:15:22.750890Z`, `2026-10-07T21:15:22`, and `None` — all cleanly parsed without exception.
- Verified via `/nix/store/h6rsdbc6bcfdn7z2dsvhvhbrpkcjzfgw-python3-3.13.15-env/bin/python3`.
- Tier 0 pre-commit gate passed (71/71 checks pass).
- Pre-push Quick Deploy Lint passed (22/22 checks pass).

## Rollback Plan
- Revert commit on `fix/hybrid-events-isoformat-robustness-wave6`.

## Residual Risk
- Minimal: fallback to `datetime.now(timezone.utc)` guarantees non-blocking execution if an unparseable non-string object is received.

## Hint Feedback
- `aq-hints` accurately pointed to `ai-hybrid-coordinator` service journals and recurring telemetry event failures.
