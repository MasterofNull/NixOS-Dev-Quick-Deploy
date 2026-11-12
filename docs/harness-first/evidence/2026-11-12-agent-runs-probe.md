# Dashboard agent-runs list answers in bounded time

Date: 2026-11-12

## Objective

The health spider's `agent-runs` dashboard probe timed out on every run (open RSI incident
`health-spider:dashboard-agent-runs`, about 503 occurrences); every other dashboard probe passed. Make the route meet the
probe's 5 s limit by fixing the route's work, not the probe.

## Workflow/Session IDs

- Branch `fix/agent-runs-probe-timeout`, worktree `.agents/delegation/worktrees/agent-runs-probe`, base main 76533d451.
- Claimed via `aq-claim` (lane claude); no overlap with the active Codex sessions.

## Delegation Decision

Sonnet 5.5 implementer (Rule 17 default); brief `.agents/delegation/outputs/wave-f/agent-runs-probe.md`. The orchestrator
reviewed the reverse reader (chunk-boundary byte joining before decode) and confirmed the loader's final timestamp sort keeps
the response order. Independent review via aq-land.

## Commands Executed

- `curl -m 60 'http://127.0.0.1:8889/api/aistack/agent-runs?limit=1'` three times against the running service (read-only)
- Direct timing of `_load_agent_run_events` and the summary on the live event file
- `python3 scripts/testing/test-dashboard-agent-replay.py`

## Validation Evidence

- Before: 6.59 s, 5.86 s, 6.24 s (HTTP 200, 558 B) against the probe's 5 s timeout (`scripts/ai/aq-health-spider` ~123).
- Cause: `_load_agent_run_events` (`dashboard/backend/api/routes/aistack.py`) parsed all 126,126 lines of the 153 MB
  `agent-run-events.jsonl` per request to keep the last 5000, synchronously inside the async handler.
- After, on the live file: loading 5000 events 0.19 s (299 runs), summarising 0.24 s.
- test-dashboard-agent-replay 9/9, including a new 60,000-event case: exactly 5000 newest events returned, route under 2 s
  (0.81 s), and an old run is still found by run_id.

## Rollback Plan

Revert the PR and restart `command-center-dashboard-api.service`.

## Residual Risk

- A run_id that occurs only far back in the file still scans backwards through the whole file (correct, but slow); the
  list view, which the probe uses, is bounded.
- The event log itself grows without bound (153 MB); retention is logged separately in the issues backlog.
- Live effect needs a dashboard restart; no rebuild.

## Hint Feedback

The open RSI incident's producer field named the probe; timing the endpoint against the probe's timeout located the route.
