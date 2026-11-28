# Steering reports only what it can deliver (R1-R4)

## Objective

Make operator steering honest. The only consumer of the per-task control queue (`.agents/delegation/control/<task_id>.jsonl`) is `agent_executor` (`ai-stack/local-agents/agent_executor.py:2757-2778`, via `control_channel.poll`), and it reads only `inject` and `cancel`, only for local-agent tasks. Owner-accepted design 2026-11-27 after Codex and Gemini review; UI change limited to honest status text.

- R1. Archive `scripts/ai/aq-human-intervention` (no production caller; its `pause`, `resume`, `skip` and `edit_intent` kinds were queued but read as plain text) to `.agent/archive/20261127-aq-human-intervention` (plain `git mv`; recent entries in that directory are uncompressed). Repoint `scripts/testing/test-human-intervention.py` to `aq-agent-send`, keeping the `aq-cockpit-monitor` assertions. `scripts/ai/aq-cockpit-monitor` now shows PENDING for a last `inject` or `cancel` too (a queued signal is not known to be consumed).
- R2. `POST /loop/control` `steer`: resolve the target to an ACTIVE local-agent task (registry `agent == local-agent`, status running or waiting) and enqueue through the same `control_channel` module file the executor loads; return `status: "queued"`. Unknown or inactive id, invalid id, non-local lane, `orchestrator` and `lane-*` return HTTP 422 `unsupported` with a reason and write no queue file. A queue write failure returns 503, never `queued`. The PULSE.log line and the RESUME hint are written only after a successful enqueue.
- R3. `POST /agent-runs/{run_id}/guidance`: kept. A run mapped to an active local-agent task is enqueued (`delivery_status: queued`, `inject`); otherwise `delivery_status: unsupported` with a reason. The unread `.agents/guidance` spool is no longer written. The `post_agent_run_control` side effect is unchanged (inspected: it appends a `human_control` audit event to the agent-run events JSONL and makes a best-effort, swallowed `POST /workflow/run/{id}/control` to the coordinator; both preserved). Actions other than `guidance` and `redirect` (pause, resume, step_approve) have no consumer and report `unsupported` even for a mapped task. `GET .../guidance` is unchanged and now reports `has_guidance: false` for new runs.
- R4. Cross-lane steering recorded as a dated deferral in `config/activation-manifest.json` with owner, review date and acceptance criteria (see Residual Risk).

`dashboard.js`: the steer modal shows the response ("queued, delivered between agent turns", or "not delivered: <reason>") instead of an optimistic message; the Pi canvas guidance result line follows `delivery_status`.

## Workflow/Session IDs

- Branch/worktree: `worktree-agent-a62b14724e9b96b2f`, based on `origin/main` 38a80347e.
- Slice: steering-honest-delivery (headless bounded correctness slice). Simurg@claude/sonnet-5.5 sub-agent session of the orchestrator.
- Files changed are staged only; nothing is committed.

## Delegation Decision

Bounded implementer slice dispatched by the orchestrator to a Sonnet 5.5 sub-agent with an explicit model override (Rule 17). No further sub-agents. Review of this slice is the orchestrator's to route to an independent lane (Rule 17/18); not self-reviewed.

## Commands Executed

```text
python3 scripts/testing/test-steering-honest-delivery.py     # pre-change (new tests, old aistack.py)
python3 scripts/governance/check-activation-manifest.py --staged
python3 scripts/governance/check-cross-surface-contract.py
bash scripts/governance/tier0.d/check-ci-test-coverage.sh
python3 scripts/testing/test-steering-honest-delivery.py
python3 scripts/testing/test-human-intervention.py
python3 scripts/testing/test-pi-agent-streaming-ui.py
python3 scripts/testing/test-dashboard-compat-routes.py
(phase0) harness_qa.phases.phase0._check_pi_agent_streaming_canvas(ctx)   # 0.10.67
ruff check <touched python>;  basedpyright <touched python>
node --check assets/dashboard.js
FORCE_HARNESS_FIRST_EVIDENCE_GATE=true bash scripts/testing/check-harness-first-pr-evidence-gate.sh
```

## Validation Evidence

Fails without the fix (new route tests run against the unmodified `aistack.py` and `aq-cockpit-monitor`):

```text
FAIL: test_invalid_id_unsupported      AssertionError: 200 != 422 : {"ok":true,"action":"steer","agent":"../etc/passwd",...,"stdout":"Guidance registered for ../etc/passwd"
FAIL: test_non_local_lane_unsupported  AssertionError: 200 != 422 : {"ok":true,"action":"steer","agent":"t-codex-1",...
FAIL: test_orchestrator_and_lane_targets_unsupported  200 != 422 (orchestrator "registered")
FAIL: test_unknown_id_unsupported      200 != 422
FAIL: test_write_failure_is_error_not_queued  AssertionError: 200 not greater than or equal to 500
Ran 15 tests ... FAILED (failures=12)
```

After the fix:

- `test-steering-honest-delivery.py`: 12 tests, OK. Covers: valid active local task appends exactly one line and one `control_channel.poll` with the executor's cursor handling injects it once with no re-injection (a source assertion pins the executor's `_cc.poll(task.id, _ctrl_cursor)` call; the executor itself is not run); invalid id, unknown id, inactive task, non-local lane (`codex`, `local-direct`) and `orchestrator` / `lane-*` each return 422 `unsupported` and leave no file; a write failure (control dir blocked by a file) returns 503, not queued, on both routes; the guidance route mapped path (one queue line, audit event written, no spool) and unsupported path (`delivery_status: unsupported`, reason, no spool, no queue file, audit event per call, unsupported action on a mapped task). The routes run against a throwaway repo root holding its own copy of `control_channel.py`, so the queue root is derived exactly as in production (the module's file location).
- `test-human-intervention.py`: 6 tests, OK (inject, cancel, ordering, unsafe id rejected, usage error, `aq-cockpit-monitor --once` shows "Intervention Dock", PENDING, CANCEL).
- `test-pi-agent-streaming-ui.py`: 6/6 tests passed (tests 4 and 5 updated to the new contract; the phase0 0.10.67 check requires the "6/6 tests passed" string, kept).
- phase0 0.10.67 (`_check_pi_agent_streaming_canvas`, run directly offline): PASS.
- `test-dashboard-compat-routes.py`: PASS (21 routes registered).
- `check-activation-manifest.py --staged`: 10 entries, 0 fail, 0 warn.
- `check-cross-surface-contract.py`: PASS.
- `check-ci-test-coverage.sh`: PASS (818 tests: 726 declared, 92 exempt); new test registered in both `config/ci-checks.json` lists.
- ruff: new/edited test files clean; `aistack.py` count unchanged at 38 (all pre-existing). basedpyright: new test files 0 errors; `aistack.py` shows only pre-existing errors (none in the added code). `node --check assets/dashboard.js`: clean.
- `config/python-check-baseline.json`: two stale `test-human-intervention.py` F401 entries removed (the rewrite no longer has the unused imports).

Not run: full tier0, live dashboard restart, and a live end-to-end steer against a running local-agent task (needs a dashboard backend restart, an owner act). The executor poll is covered by the queue API, not by running `agent_executor`.

## Rollback Plan

`git revert` of the slice commit restores the previous routes, JS and `aq-human-intervention` (a `git mv` back from `.agent/archive/20261127-aq-human-intervention`). No data migration: the queue format is unchanged, and the `.agents/guidance` spool was never read. The dashboard backend needs a restart after merge for the route change to take effect.

## Residual Risk

- Steering still reaches only active local-agent tasks. Deferral (R4), recorded in `config/activation-manifest.json`: "cross-lane live steering (codex, gemini, claude and direct-lane tasks)", dated 2026-11-27, owner hyperd, review 2026-12-11. Acceptance: a design is implemented for one non-local lane such that a steer to an active task is read by that lane's runner and changes its next step; the dashboard reports delivered only after a consumer acknowledgement, not at enqueue time; `_resolve_steerable_task` refusals shrink and the new test gains a per-lane case; a live end-to-end steer on that lane is attested. The local-lane-only limit is a second dated deferral on the "operator steering queue" entry (review 2026-12-11).
- `queued` means appended to the queue; delivery happens at the executor's next turn boundary and there is no consumer acknowledgement yet, so a task that finishes before its next turn never reads the message.
- Active-task resolution reads `.agents/delegation/registry.jsonl` `agent == local-agent` and assumes the registry task id equals the executor `task.id` (`run_id=task_id` in `dispatch.py`); a stale `running` row for a dead process would accept a message nobody reads.
- `GET /agent-runs/{id}/guidance` now returns `has_guidance: false` for new runs; it reads the old spool and has no other consumer in the repo besides the updated test.
- Historical evidence docs that name `aq-human-intervention` are left unchanged as a record.

## Hint Feedback

No aq-hints query was available in this headless slice; discovery used the verified facts in the dispatch and direct reads. Useful finding to seed: `apiFetch` in `assets/dashboard.js` returns null for any non-2xx response, so refusal reasons are lost unless a call uses raw `fetch`. Backlog entry added: STEER-DELIVERY-CLAIMED-FALSE in `.agent/memory/issues-backlog.md`.

### Review follow-up (Codex P2, head 17029b17e)

The guidance route reported `persisted: true` unconditionally. It now returns `bool(result["persisted"])` from `post_agent_run_control`, so an audit-write failure reads `persisted: false`, and an unsupported target reports only whether the audit event was written (never a queue entry). New tests `test_audit_write_failure_reports_persisted_false_when_mapped` and `..._when_unsupported` failed on the prior code (`FAILED (failures=2)`, 15 tests) and pass after (15 OK).
