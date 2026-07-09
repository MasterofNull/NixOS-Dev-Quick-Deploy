# Usability Parity v2 Consensus

Status: collected, 4/4 lanes landed
Round: `usability-parity-v2`
Landed lanes: `claude`, `codex`, `antigravity`, `local`

## Verdict

PASS-WITH-CONDITIONS. Proceed with implementation only after treating the local lane as late-pending, not failed. The first implementation slice must make background task state truthful across delegation lanes before any broad UI redesign or new operator command family.

## Consensus Findings

All three landed lanes agree that the usability problem is primarily operational truth, not missing feature count. Operators cannot reliably tell whether agent work is queued, running, stalled, failed, stale, waiting on local inference, blocked by provider state, or misplaced in an inbox.

Common first principles:

- Instrument before polishing UI.
- Dashboard and CLI must read the same normalized task state.
- Local inference must use heartbeat/progress/stale-state signals, not arbitrary hard caps.
- Antigravity/Gemini fan-out remains no-key IDE/OAuth through the watched inbox.
- New services/routes/capabilities are incomplete without `aq-qa` plus dashboard/report visibility.

## Ranked Decisions

1. Implement `background_task.v1` / delegation status truth first.
2. Normalize task states across local, Codex, Antigravity inbox, drop zones, and registry tools.
3. Add durable stale/dead PID detection so false `running` does not persist.
4. Expose restart-cancelled and provider/fallback failures as explicit terminal reasons.
5. Add an Agent Tasks dashboard/API surface only after state normalization exists.
6. Add `aq doctor providers` after task truth, with no secret printing and no Antigravity API-key path.
7. Add sandbox/permission visibility as first-class operator state.
8. Add `aq-agent-stream.v1` JSONL projection from the normalized task model.
9. Add replay/eval fixtures for Broken pipe, provider mismatch, local timeout, stale PID, and drop rejection.
10. Defer spec/worktree execution and unified `aq` command router until the status substrate is reliable.

## First Slice

Slice: `background_task.v1` delegation status truth.

Primary files:

- `scripts/ai/lib/task_registry.py`
- `scripts/ai/aq-delegation-registry`
- `scripts/ai/delegate-to-local`
- `scripts/ai/delegate-to-codex`
- `scripts/ai/delegate-to-antigravity`
- `scripts/ai/aq-collab-round`
- `dashboard/backend/api/routes/aistack.py`
- `assets/dashboard.js`
- focused tests under `scripts/testing/`

Acceptance criteria:

- Dead PID plus zero output becomes `stale` or `failed`, never indefinite `running`.
- Live heartbeat sidecars with `ts` keep local tasks live.
- Restart/interruption errors are visible as specific reasons.
- Antigravity inbox has explicit `inbox_pending`, `inbox_landed`, or `inbox_unavailable` state.
- A CLI status path and one dashboard/API path expose the normalized state.
- `aq-qa` includes an integration check for the status path, not just `/health`.

## Validation Plan

- `python3 -m py_compile` for changed Python scripts.
- `bash -n` for changed shell scripts.
- focused stale PID / heartbeat schema tests.
- `scripts/ai/aq-collab-round collect --round usability-parity-v2`.
- live status check against `local-20260708-231639-o7qnkl` while it remains active.
- dashboard route smoke via `curl`.
- `scripts/ai/aq-qa 0 --machine`.
- `scripts/governance/tier0-validation-gate.sh --pre-commit` before commit.

## Local Lane Handling

The original local lane failed after local llama inference wedged and was restarted. The restarted lane `local-20260708-235359-44knlv` completed with only a non-substantive completion marker.

Follow-up Qwen retries produced stronger evidence:

- `local-20260709-001430-f3llz1` completed but returned textual `Thought:` / `Tool:` content and was falsely marked successful.
- `local-20260709-002206-ei5of8` produced useful Markdown but was truncated at 150 tokens by the direct-lane token heuristic.
- `local-20260709-002835-7qsrf2` produced a partial substantive local proposal and agreed that `background_task.v1` should remain first.

Local/Qwen therefore confirms the ranked decisions while adding two fixtures for Slice 1: false-success result quality and prompt-driven output-budget truncation.

## Codex Stale Registry Handling

Three apparent hanging Codex tasks in switchboard were stale registry rows, not live processes: `codex-20260708-224654-s4kn7lxxxxxx`, `codex-20260708-230805-yq4n07xxxxxx`, and `codex-20260708-231458-tgnak0xxxxxx`. Their registered PIDs no longer existed, and `aq-delegation-registry reconcile` marked them stale.

This reinforces the first-slice priority: dashboard and CLI surfaces must consume normalized task-state inference, not raw registry `running` values.

VERDICT: PASS — implement background task status truth first, using the local restart and stale Codex rows as validation fixtures.
