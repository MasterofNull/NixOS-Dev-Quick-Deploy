# Attention recovery design — FROZEN R3 (owner-approved retirement; accepted by Claude 4mzeac + Gemini ciflmn)

> **Provenance**: Recovered and persisted from `/tmp/coord-attention-recovery-design-20261113.md` (`SHA-256 e1dcc39918e03962463f420bb6bc362499d9d185a74c3015a634b3d1aa3fd552`) so `/tmp` cleanup cannot erase the accepted R3 design while `Simurg@codex` is on quota cooldown.

## Scope, authority, and grounded contract

**STATUS: PLAN_READY_WITH_FOLLOWUPS (Claude `claude-20261113-175143-4mzeac` + Gemini `gemini-20261113-175142-ciflmn` READY; Codex unavailable on quota window; Local `local-20261113-175135-xnhid0` failed/recorded).** This is deliberately one producer/key pair: a pending alert with
`source == "ai-stack-health-monitor"` and `dedup_key == "qa-phase-0"`.
It neither changes human dispositions nor establishes a general policy.

Grounding: `scripts/health/ai-stack-health-monitor.py` currently pushes
phase-0 failures and leaves the queue untouched after a clean run.
`scripts/ai/lib/attention_queue.py` owns locking, persistence and the JSONL
archive. `push()` creates an item without `updated_at`, and an identical
deduplicated push may not mutate it; therefore `id + updated_at` is not a
safe recovery fence. Archive terminal state is represented by `status`, not
an `outcome` wrapper. The persisted alert has `identity` but no raw
`dedup_key`, so exact source/key matching requires an additive field.

## Frozen MVP proposal (accepted R3)

1. Add queue-owned alert fields `dedup_key: str | None` and
   `observation_generation: int`. A newly created matching alert starts at
   generation 1. Under the existing exclusive queue lock, **every** pending
   `ai-stack-health-monitor` / `qa-phase-0` failure observation increments
   its generation, including content-identical dedup pushes; it preserves the
   original failure payload and may refresh the existing producer fields only
   under the current push policy. No other source/key gets this special
   increment behavior.
2. Before running the phase-0 probe, the monitor asks the queue for a locked,
   immutable snapshot `{id, source, dedup_key, observation_generation}`. Only
   a parsed, complete, fresh, clean phase-0 result may ask the queue to retire
   that snapshot. The queue reacquires its lock and archives only when id,
   source, raw key, status `pending`, and generation all still match.
   Concurrent/new failure observations win. The snapshot occurs before the
   probe whenever an eligible record exists; timeout, non-zero, malformed,
   partial, stale, skipped, or no-payload proof must make **no retirement
   call**.
3. The helper moves the original record through the existing archive path with
   `status: "recovered"`, `recovered_at` (UTC ISO-8601),
   `recovery_reason: "phase-0-clean"`, and
   `resolved_by: "ai-stack-health-monitor"`. It never rewrites payload,
   error/freshness keys, human `approved`/`rejected`/`deferred`/`dismissed`, or
   unrelated items. A later failure produces a new pending alert, so
   fail → clean → fail re-alerts with later evidence.

### Legacy safety

Existing queue rows have neither raw `dedup_key` nor generation. A
queue-owned migration runs under the exclusive lock **before** a monitor
snapshot. It admits exactly one candidate only if its stored `identity` equals
`_identity("ai-stack-health-monitor", candidate_title, "qa-phase-0")`
(the supplied dedup key makes title irrelevant), and its `source`,
`status == "pending"`, and `autonomy_boundary == "human_gate"` also match
exactly. It atomically persists raw `dedup_key: "qa-phase-0"` and initial
generation 1, then returns the snapshot. Zero, multiple, malformed, mismatched,
or manually resolved candidates are a no-op. It never derives a key from a
title, prefix, or partial hash; unrelated and human-owned alerts remain
untouched.

## API and dashboard contract

`dashboard/backend/api/routes/aistack.py:get_alerts_status` retains all
current fields and adds only nullable `last_machine_recovery`:

```json
{"source":"ai-stack-health-monitor","dedup_key":"qa-phase-0","recovered_at":"<UTC ISO-8601>","recovery_reason":"phase-0-clean"}
```

The queue supplies it by inspecting at most the newest 200 physical JSONL
archive records; it is therefore a **bounded recent archive observation**, not
a claim about the globally newest historical recovery. Among that bounded
window it selects the newest parseable `recovered_at` with exact source/key
and `status == "recovered"`. Invalid, legacy, unmatched, malformed, or
out-of-bound older records yield `null`, not a guessed recovery. The response
never includes id, title, detail, payload, command, executor, proposed action,
or arbitrary archive fields.

`assets/dashboard.js:loadAlerts` adds one separate `fwRow` only when this
four-field projection validates source/key and ISO timestamp and the reason is
the allow-listed string above: label `Recent recovery`, value formatted local
time, class `info`. It must be visible with zero pending alerts and must not
be folded into the `Clear` badge. Render fixed label/allow-listed reason and
formatted timestamp only; do not inject archive strings into `innerHTML`.

## Complete QA proof predicates

The registered integration is `ALL_PHASES["0"] -> phase0.run` in
`scripts/testing/harness_qa/phases/__init__.py`; its actual queue CheckResult
is `phase0.py:_check_phase86_attention_queue` (86.1–86.7). Extend exactly
this registration (not a new phase) and invoke the non-`dashboard_safe` path.

* Queue tests: a matching pushed record persists raw key and integer
  generation; identical matching failure increments it; snapshot+clean archives
  exactly once with the recovered status/audit; changed generation, wrong
  source/key, manual resolution, and malformed/timeout/partial proof are
  no-ops; fail→clean→fail yields a new pending record with later payload.
* Monitor tests in `scripts/testing/test-ai-stack-health-monitor.py`: an
  eligible canonical pending alert is snapshotted before P0. The one shared
  `is_complete_clean_phase0_result` predicate accepts only a parsed JSON
  object with no `error`, `phase == "0"`, an integer (not boolean)
  `_monitor_returncode == 0`, `degraded_confidence is False`, non-boolean
  non-negative integer `passed`/`failed`/`skipped`, and a nonempty
  `tests` list. Every test must be an object with nonempty string `id` and
  `status == "PASS"`; `passed == len(tests)`, `failed == 0`, and
  `skipped == 0`. This is the complete emitted-result cardinality/identity
  check: no subset, empty list, unknown status, or count mismatch is clean.
  Any missing/wrong type/nonzero/degraded/empty/FAIL/SKIP/malformed/non-JSON,
  stale, or timeout result calls no retirement helper (normal failure handling
  remains separate).
* Phase 86 isolated-temp-queue check: imports new public helper; asserts the
  archive and active-queue predicates above without touching live queue state.
* 86.7 live endpoint: for HTTP 200, JSON must retain `pending` as an integer
  and contain `last_machine_recovery` as null or **exactly** the four
  fields/types above; arbitrary field leakage fails. It never creates or
  requires a live recovery.
* Route fixture: proves null for no archive and selection of newest valid exact
  recovered record within the bounded 200-record window, rather than archive
  order; a fixture with more than 200 unrelated newer records proves an older
  recovery is null rather than falsely “latest.” Dashboard fixture extends
  `scripts/testing/test-dashboard-qa-provider-probe.py`'s real-JS temporary
  Node-harness pattern for `assets/dashboard.js:loadAlerts`: the narrow
  response renders a separate Recent recovery line while badge and manual
  workflow remain unchanged; null renders no line.

## Owned implementation surface and validation

Owned source paths: `scripts/ai/lib/attention_queue.py`,
`scripts/health/ai-stack-health-monitor.py`,
`scripts/testing/test-ai-stack-health-monitor.py`,
`scripts/testing/harness_qa/phases/phase0.py`,
`dashboard/backend/api/routes/aistack.py`, and `assets/dashboard.js`, plus
their nearest existing tests including
`scripts/testing/test-dashboard-qa-provider-probe.py`. No Nix/service unit, new daemon/timer, database,
or new alert class is needed. Minimal-code ladder: reuse queue lock and JSONL
archive → add one narrow queue helper/fields → guarded monitor call → narrow
existing API/card projection; do not reuse health-spider's title/rejected path.

Reproducible acceptance commands (in the implementer's isolated worktree):

```sh
python3 scripts/testing/test-ai-stack-health-monitor.py
python3 scripts/testing/test-dashboard-qa-provider-probe.py
scripts/ai/aq-qa --phase 0
scripts/governance/tier0-validation-gate.sh --pre-commit
```
