# Reviewer Lane Probe & Short-Credential Redaction

Date: 2026-11-17
Task ID: HF-20261117-REVIEWER-LANE-PROBE

## Objective
- Probe and capability-test candidate reviewer lanes on synthetic data before spending a review slot (`scripts/ai/probe-reviewer-lane`), refuse redirects, and scrub credentials of any length (including `< 12` chars) before output truncation.
- Delivered: `scripts/ai/probe-reviewer-lane`, `scripts/testing/test-probe-reviewer-lane.py`, `scripts/ai/aq-session-start`, `scripts/testing/harness_qa/phases/phase0.py`.

## Workflow/Session IDs
- Workflow ID: none (bounded slice from the orchestrator)
- Session ID: Simurg@gemini/gemini-4-argon#78d98033

## Delegation Decision
- Implemented in isolated worktree `.agents/delegation/worktrees/lane-probe`; reviewed independently by Codex (`18/18` PASS).

## Commands Executed
```bash
python3 scripts/testing/test-probe-reviewer-lane.py
bash scripts/testing/check-harness-first-static-gates.sh
scripts/governance/tier0-validation-gate.sh --pre-commit
```

## Validation Evidence
- Root cause: `scrub()` only iterated `range(len(token), MIN_PREFIX - 1, -1)` (`MIN_PREFIX = 12`), allowing short tokens (`< 12` chars) to bypass redaction and `leaks()`.
- Fix: `text = text.replace(token, "[REDACTED]")` executes unconditionally before the prefix loop; added `test_short_credential_scrubbed_and_leak_guard_trips` (`18/18` pass).

## Rollback Plan
- `git revert <sha>`. Trigger: false positive or probe failure in `probe-reviewer-lane`.

## Residual Risk
- Prefix matching remains bounded at `MIN_PREFIX = 12` to avoid redacting short common words that happen to match the first few characters of a long token.

## Hint Feedback
- Codex round-4 (`izhxwq`) and live verification confirmed 18/18 unit tests pass.

## Review Round (Codex REQUEST_CHANGES on b80b1f56, addressed)
- P1 credential disclosure: a chat/catalog URL whose host is outside the lane's default hosts is refused (exit 2) unless `--token-cmd` names an explicit credential; the default `gh auth token` never runs for foreign hosts.
- P2 scoring: a hit needs REQUEST_CHANGES plus a finding matching the case's defect marker (defect text or location); placeholder findings score 0/8.
- P2 smoke validation: the catalog needs at least one non-empty string model id and the `ok` chat reply must be non-empty and contain `ok`; `[{}]` and empty chat give `lane_unavailable` (exit 3).
- P2 redaction: internal result fields stay raw; `render()` redacts string values only at serialization (file and stdout); tested with credential `lane`.
- P2 evidence paths: `lane-probe-<lane>-<ts>-<uuid12>.json`, created with `O_EXCL` and mode 0600 at creation; tested with 16 concurrent writers and a forced name collision.
- Tests: `python3 scripts/testing/test-probe-reviewer-lane.py` now runs 23 tests, all passing.
