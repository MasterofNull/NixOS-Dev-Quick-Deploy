# Observability Parity Consensus Review

Date: 2026-06-08
Status: REQUEST_REVISION resolved for first corrective slice; repo-validated, pending rebuild for live activation
Scope: Phase 149 agent-run logic observability, dashboard replay, useful-token telemetry

## Model-Team Inputs

Gemini proposal claimed Phase 149 complete with:

- raw `<think>` extraction in switchboard,
- `thought` and `planning` event types,
- dashboard rendering for thought events and HTML artifacts,
- useful-token null mitigation,
- `aq-qa 0.10.2` coverage.

Codex backend reviewer verdict: `REQUEST_REVISION`.

Codex dashboard/operator reviewer verdict: `REQUEST_REVISION`.

Local model reviewer verdict: `REQUEST_REVISION`, but the local delegation artifact truncated after the first finding. Treat this as additional evidence for the existing local delegation artifact reliability issue.

## Consensus Findings

1. Gemini's completion claim was too strong. The new check was grep-only and did not prove live event emission, schema consistency, dashboard visibility, or safety.
2. Raw `<think>` persistence/display is not acceptable. The dashboard may show reasoning was observed, but raw chain-of-thought must not be stored or displayed by default.
3. `planning` was only a label/icon before the corrective slice. Operators need actual planning events with safe fields.
4. The canonical schema and replay fixture must move with runtime event types.
5. HTML artifact previews must be sandboxed because artifact content is untrusted.
6. Unknown quality must not be counted as accepted artifact tokens. That inflates useful-token metrics and hides missing evaluation.

## Corrective Slice Implemented

Files changed:

- `ai-stack/switchboard/switchboard.py`
- `ai-stack/mcp-servers/hybrid-coordinator/extensions/ai_coordinator_handlers.py`
- `scripts/ai/lib/agent_run_events.py`
- `config/schemas/maeah/agent-run-event.schema.json`
- `scripts/testing/test-agent-run-event-envelope.py`
- `scripts/testing/test-telemetry-thought-event.sh`
- `assets/dashboard.js`
- `dashboard.html`

Changes:

- Switchboard now emits only a safe reasoning-observed `thought` event with summary, character count, content hash, and `raw_reasoning_suppressed`.
- Switchboard strips raw `<think>...</think>` blocks from the returned local response path after recording the safe summary.
- Hybrid coordinator now emits a safe `planning` event for route-selection decisions before token usage telemetry.
- Useful-token handling now preserves `None` when quality is unavailable, records `0` only when a quality gate is available and failed, and records output tokens only when the quality gate passed.
- Event schema now includes `thought` and `planning`.
- Agent-run envelope fixture now covers every event type, including `thought` and `planning`.
- Dashboard replay filter now includes `thought` and `planning`.
- Dashboard thought rendering now shows a policy-safe reasoning-observed card instead of raw content.
- Dashboard planning rendering now shows plan step, rationale summary, and evidence references.
- Dashboard HTML artifact preview is now sandboxed and fully escaped before `srcdoc`.
- `aq-qa 0.10.2` now validates the safe telemetry contract instead of grepping only for strings.

## Validation

Passed:

- `python3 -m py_compile ai-stack/switchboard/switchboard.py ai-stack/mcp-servers/hybrid-coordinator/extensions/ai_coordinator_handlers.py scripts/ai/lib/agent_run_events.py`
- `python3 scripts/testing/test-agent-run-event-envelope.py`
- `bash scripts/testing/test-telemetry-thought-event.sh`
- `python3 scripts/testing/test-useful-token-metrics.py`
- `python3 scripts/testing/test-dashboard-agent-replay.py`
- `node --check assets/dashboard.js`
- `AQ_QA_SKIP_REPORT_BACKED_CHECKS=1 timeout 120 scripts/ai/aq-qa 0 --machine`

Phase 0 result after the corrective slice: 95 passed, 0 failed, 2 skipped.

## Live Activation Status

Repo validation is green. Runtime code changes in switchboard and hybrid coordinator still require rebuild/restart before live services emit the new safe `thought` and `planning` events.

Current live telemetry before rebuild had no `thought` or `planning` events in `/var/lib/ai-stack/hybrid/telemetry/agent-run-events.jsonl`, confirming the user's dashboard concern.

## Remaining Slices

1. Add live replay summary tiles for planning/thought counts, latest planning step, and missing-observability warnings.
2. Add dashboard test coverage for thought/planning rendering in `assets/dashboard.js` or browser-level smoke.
3. Add live post-rebuild smoke that triggers a safe local reasoning-observed event and verifies it appears in `/api/aistack/agent-runs/{run_id}`.
4. Expand planning events beyond route selection into PRD proposal, cross-review, consensus, implementation, validation, and commit readiness transitions.
5. Fix direct local delegation artifact truncation/status persistence before relying on local model-team outputs as full evidence.
6. Decide whether raw reasoning capture is ever allowed in an explicit debug-only, local-only, time-bounded mode. Default remains suppressed.
