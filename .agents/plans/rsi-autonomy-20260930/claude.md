# Claude — rsi-autonomy-20260930

Read-only. Inspected `scripts/automation/prsi-orchestrator.py`, `scripts/ai/lib/rsi_lifecycle.py`,
`config/runtime-prsi-policy.json`, `nix/modules/roles/ai-stack.nix` (ai-prsi-* units),
`dashboard/backend/api/routes/aistack.py` (`/prsi/*` routes), `ai-stack/autonomous-improvement/autonomous_loop.py`
(integration surface only, not edited), `.agent/collaboration/rsi-incidents.json`, and the live
`/var/lib/nixos-ai-stack/prsi/action-queue.json`. No files written except this one. Did not touch
aq-report internals or autonomous_loop metrics logic (Luna scope). No delegation dispatched for this
lane per round instruction.

## 1. Architecture — `rsi_awaiting_validation` is a designed sink with no consumer

`_run_rsi_delegate` (`prsi-orchestrator.py:850-893`) returns exactly one of three terminal strings per
dispatch: `rsi_stalled` (timeout), `rsi_failed` (nonzero exit or missing delegate receipt), or
`rsi_awaiting_validation` (success, line 893). The only code path that can ever move a row *out* of
`rsi_awaiting_validation` is `_reconcile_rsi_queue` (`:766-779`), and it only fires on an unrelated
signal: the incident's `status` in `.agent/collaboration/rsi-incidents.json` flipping away from
`"open"`. That flip is produced solely by `rsi_lifecycle.resolve(incident_id, root_cause, regression,
validation)` (`scripts/ai/lib/rsi_lifecycle.py:156-167`) — a strict function requiring all three
evidence strings non-empty. `grep -rl rsi_lifecycle` across the live tree (excluding worktrees) returns
exactly three files: `prsi-orchestrator.py` (comment only, no call — `:56`), `test-rsi-adapters.py`,
`test-rsi-lifecycle.py`. **No production code calls `resolve()`.** There is no script, systemd unit, or
dashboard route that reads a `rsi_awaiting_validation` row, inspects its bounded receipt
(`row.execution.receipt.stdout_tail`/`stderr_tail`, capped 2000/1000 chars at `:876-882`), and drives it
to resolution. This — not a missing feature idea, but a verified dead end in the call graph — is the
literal cause of "rsi_awaiting_validation has no consumer."

## 2. Authority — two disconnected gate surfaces, neither wired to closure

- **Pre-execution gate**: `require_independent_verifier_for_high_risk` (`config/runtime-prsi-policy.json:56`,
  enforced at `prsi-orchestrator.py:979,1003-1007`) blocks `risk=="high"` rows from `_select_actions_for_execution`
  unless `row.approval.verifier_by` is set. RSI incident rows are always `risk="high"` (`safe: False` at
  `:489` → `_risk_tier` `:320-327` returns `"high"`). The only way to populate `verifier_by` is
  `prsi-orchestrator.py verify --id <row-id> --by <name>` (`cmd_verify`/`_set_verifier`, `:660-671,686-689`) —
  a manual CLI with no caller in any service, timer, or dashboard route (`/prsi/*` exposes `sync`,
  `approve`, `execute`, `actions` only — no `verify` endpoint, confirmed by grep at
  `dashboard/backend/api/routes/aistack.py:4467-4560`).
- **Closure gate**: `rsi_lifecycle.resolve()` is a *separate* authority with its own evidence contract
  (root_cause/regression/validation text) and is not conditioned on `approval.verifier_by` at all.

These two gates do not reference each other. A design that "closes the loop" without deliberately
linking them will either (a) let `resolve()` be called by anyone without ever having passed the
pre-execution verifier gate, silently downgrading the existing high-risk control, or (b) leave the gap
exactly as-is. Any fix must make the *same* independent-reviewer identity satisfy both, in one call, or
require verifier_by to already be set as a precondition to calling resolve.

## 3. Operations — dispatch is automated, validation is not

`ai-prsi-rsi-dispatch.timer` (`nix/modules/roles/ai-stack.nix:2421-2425`, `OnUnitActiveSec=5min`) plus a
`systemd.paths` unit watching `.agent/collaboration/rsi-incidents.json` (`:2412-2419`) drive
`rsi-dispatch --execute --apply` automatically and continuously. There is no `ai-prsi-rsi-validate`
(or equivalent) service/timer anywhere in `nix/modules/roles/ai-stack.nix` (grep confirmed) and no
`/prsi/verify` or `/prsi/rsi-resolve` dashboard route. Production is asymmetric: fully automated
production of `rsi_awaiting_validation` rows, zero automated or operator-facing path to review them.
`autonomous_loop.py::_prsi_sync_execute` (`:430-482`) only calls `prsi-orchestrator.py sync`/`execute`
(the ordinary action queue), never `rsi-dispatch` — RSI incident lifecycle is entirely outside the
autonomous-loop cadence, confirming it is a separately-owned authority path, not an accidental omission.

## 4. Measurement precondition (Luna-owned, cited not re-diagnosed)

`ai-prsi-orchestrator.service` (`ai-stack.nix:2346-2379`, `MemoryMax=256M`) runs `prsi-orchestrator.py
cycle`, whose `_fetch_report` (`:349-360`) subprocesses `aq-report --format=json` inside the same cgroup
(no `Delegate=true`). The known 552192 KiB RSS sample against a 256M cap risks OOM-killing the sync
step before structured actions land — any acceptance test for the closure design must tolerate/detect a
failed or truncated sync rather than assume it always succeeds. I did not touch aq-report or this unit;
flagging only because the closure plan's acceptance test depends on sync completing.

## 5. Failure mode observed live (report, not fixed)

Read `/var/lib/nixos-ai-stack/prsi/action-queue.json` directly (this is the real
`PRSI_ACTION_QUEUE_PATH` used by both ai-prsi-* units). On-disk it is a top-level **JSON array** of 14
elements: element 0 is a dict shaped like the expected `{"actions": [...]}` envelope (containing a
`prefer_local` row timestamped `2026-09-30T16:41:48Z`); the remaining 13 elements are flat dicts with a
different schema (`summary`, `details`, `status:"queued"`, epoch-float `created_at` ~`1790786520`,
`action: "resume_background_maintenance"`) that do not match any shape `prsi-orchestrator.py` writes.
`_load_queue()` (`:330-341`) does `if not isinstance(payload, dict): payload = {}` — since the file is a
list, **every load of this file currently discards all queue state, including any real RSI rows,
approvals, and verifier signatures, silently.** I did not find the producer of the second schema in the
live tree (not `autonomous_loop.py`, not `prsi-orchestrator.py`) — it is either a stale file from a
prior format or a second, unidentified writer sharing the path. This file may be under active
concurrent write from another process; I did not modify it. Any acceptance test must run against an
isolated `PRSI_ACTION_QUEUE_PATH` override (already supported, `:46`), never the live path, until this
schema collision is root-caused and attributed.

## 6. Minimal plan — review-validation-integration closure

Scope: one new bounded subcommand, no change to existing commands' behavior or defaults.

1. **New subcommand `prsi-orchestrator.py rsi-resolve --id <row-id> --by <name> --root-cause <str>
   --regression <str> --validation <str>`.**
   - Precondition (hard-fail, no partial effect): row status must be exactly `rsi_awaiting_validation`;
     `approval.verifier_by` must already be set (reuse existing `cmd_verify` flow) and `--by` must equal
     `approval.verifier_by` — one identity satisfies both gates, closing the §2 disconnect instead of
     adding a second one.
   - `--by` must differ from `row.execution.receipt`'s originating delegate identity (independent-review
     invariant already implied by `require_independent_verifier_for_high_risk`).
   - On success: call `rsi_lifecycle.resolve(...)` exactly once under the existing
     `rsi-incidents.lock` (already taken inside `resolve()`), then under the existing queue lock
     transition the PRSI row directly to `rsi_resolved` (don't wait for the next `_reconcile_rsi_queue`
     sweep) and append the supplied evidence into `row.execution` for audit. This makes `rsi-resolve` the
     single, explicit consumer of `rsi_awaiting_validation`.
   - No systemd timer for this command. Per Rule 15 (intervenable) and the UX-first-for-gated-features
     precedent, resolution requires human-attestable evidence text — keep it a deliberate reviewer
     action (CLI now; a `/prsi/rsi-resolve` dashboard route is a natural, separately-scoped follow-up,
     not part of this minimal slice).

2. **Stale incident closure evidence (the 5 open incidents)**: do not bulk-close. Codex's incident-level
   review already owns root-cause detail per the round brief — once it supplies root_cause/regression/
   validation text per incident, an independent reviewer runs `rsi-resolve` once per incident (5 bounded,
   auditable calls). No script should do this in bulk; bulk-closing is exactly the "fake the signal"
   pattern Rule 19 forbids.

3. **Scoped activation**: ship `rsi-resolve` dormant (reachable only by explicit CLI invocation) until a
   human/reviewer has exercised it successfully against the isolated test fixture in item 4. Do not add a
   systemd unit in the same change — this is an operator-gated control surface, not a cron job.

4. **Live end-to-end acceptance test** (extend `scripts/testing/test-prsi-rsi-intake.py`, which already
   has an `rsi_awaiting_validation` fixture at `:157`, and `scripts/testing/test-rsi-lifecycle.py`):
   run against an isolated `PRSI_ACTION_QUEUE_PATH`/`.agent/collaboration` tmp tree (never the live
   path, per §5) — synthetic incident → `rsi-dispatch --execute --apply` (mocked delegate) →
   `rsi_awaiting_validation` → `verify` → `rsi-resolve` → assert row status `rsi_resolved` **and**
   `rsi-incidents.json` incident status `resolved` **and** `_reconcile_rsi_queue` is idempotent on replay
   (no double-resolve, no lock deadlock under concurrent dispatch + resolve).

## 7. Acceptance criteria

- `rsi-resolve` refuses any row not in `rsi_awaiting_validation`, any call without prior `verifier_by`,
  and any call where `--by == verifier_by` is false — three negative tests required, not just the happy
  path.
- No existing command's default output or exit code changes (regression-free for `sync`/`list`/`approve`/
  `reject`/`execute`/`cycle`/`agent`/`rsi-dispatch`).
- New test suite passes fully isolated from `/var/lib/nixos-ai-stack/prsi/*` and `.agent/collaboration/
  rsi-incidents.json` (live paths untouched).
- `require_independent_verifier_for_high_risk` remains `true` in `config/runtime-prsi-policy.json` and is
  not weakened, removed, or defaulted differently anywhere in the new code path.
- The §5 queue-file schema collision is filed as its own tracked item (owner TBD by orchestrator — it is
  inside `prsi-orchestrator.py`'s own contract, not aq-report/autonomous_loop metrics) before any
  activation is declared DONE, since it currently invalidates queue-state durability end-to-end.

## 8. Blockers to close before activation

- §5 queue-file schema collision unresolved — until attributed and fixed, queue durability (including any
  future `rsi-resolve` writes) cannot be trusted on the live path.
- §4 MemoryMax/aq-report RSS mismatch (Luna-owned) — sync reliability precondition for acceptance
  evidence to be trustworthy; not blocking the `rsi-resolve` design itself.
- No independent-reviewer identity source exists yet beyond free-text `--by`; this round's design accepts
  that as sufficient given human-in-the-loop already required by Rule 15, but flags it as a weaker control
  than a signed/authenticated identity if this authority is ever escalated beyond the current bounded CLI.

## Verdict

PLAN_READY_WITH_FOLLOWUPS. The closure design in §6 is minimal, reuses existing locks/locking
primitives and the existing verifier gate rather than adding a parallel authority, and does not touch
files owned by other workers. It should not be marked DONE/activated until the §5 data-integrity blocker
is independently resolved — building the consumer on top of a queue file that silently resets on every
read would produce evidence that looks like closure but isn't (Rule 19 anti-gaming). I did not observe
or assume any cross-agent consensus in this document; this is my lane's assessment only.

## 9. Addendum (round 2 — orchestrator clarification, 2026-09-30)

Owner has authorized bounded unattended non-destructive repair; manual-only CLI resolution (§6.3 as
originally scoped) does not by itself meet that objective. Amending §6/§7 in place (this section only —
no source/staging/service changes made):

**9a. Add a real independent agent consumer, not just a human CLI.** Introduce an `rsi-verifier-agent`
role distinct from both the dispatch delegate (the identity that produced the row under repair) and the
orchestrator itself — satisfying the existing independent-reviewer invariant (§6, `--by != receipt
delegate identity`) with an automated caller instead of only a human operator:
- **Subject-bound evidence**: the agent's root_cause/regression/validation text must embed the specific
  `incident_id`, PRSI row id, and a content hash of the exact `receipt.stdout_tail`/`stderr_tail` it
  reviewed. Evidence not bound to that triple is rejected by `rsi-resolve` (new precondition) — this
  stops copy/boilerplate evidence reuse across rows (Rule 19).
- **Integration**: the agent calls the same `rsi-resolve` subcommand from §6 through the same lock
  contract — it is an automated caller with its own `--by` identity, not a bypass path. No second
  authority surface is created.
- **Terminal verification, not receipt trust**: before calling `resolve`, the agent must independently
  re-check the actual post-repair system state relevant to the incident class (service health, file
  state, targeted test — whichever the incident names), not merely parse the delegate's self-reported
  receipt text. Resolve is only called if that independent terminal check itself confirms remediation.
- **Stop condition (hard)**: if the terminal check is inconclusive, the row's risk tier/authority exceeds
  what this agent role is authorized for, or `approval.verifier_by` is unset, the agent MUST leave the
  row untouched and escalate — never force a resolution to make the queue look clear. This keeps §2's two
  gates intact and bounds the agent to the same non-destructive envelope as the human path.

**9b. Mocked vs. live acceptance are not interchangeable — split §6 item 4 and §7 explicitly.** The fixture
test in `test-prsi-rsi-intake.py`/`test-rsi-lifecycle.py` (mocked delegate, isolated tmp paths) proves the
state machine and locking logic only; it must be labeled "logic-level, not live-readiness evidence" in
its own docstring/report output. A **separate** live acceptance pass is required before any
DONE/activation claim: real `ai-prsi-rsi-dispatch.timer`, a real (non-mocked) delegate run, and the
verifier agent exercised against a staging instance of the actual runtime paths — only that second pass
may be cited as evidence the closure works end-to-end. A green mocked-fixture run must never be reported
as live validation.

**9c. §5 queue-path claim downgraded to unverified.** My original §5 asserted
`/var/lib/nixos-ai-stack/prsi/action-queue.json` is "the real `PRSI_ACTION_QUEUE_PATH` used by both
ai-prsi-* units" — I observed only that one path, from one read, and did not independently confirm both
units resolve to it. The orchestrator's independent check is against
`/var/lib/nixos-ai-stack/optimizer/prsi/action-queue.json` — a different path (extra `optimizer/`
segment) than the one I read. I did not verify these are the same file (symlink, bind mount) versus two
distinct queue files with independently drifting state. Retracting the "both units" claim: **effective
consumer path is unverified.** Before any verifier-agent or `rsi-resolve` design is activated, each
`ai-prsi-*` unit's actual runtime `PRSI_ACTION_QUEUE_PATH` (from its systemd `Environment=`/unit file in
`nix/modules/roles/ai-stack.nix`, not assumed) must be read directly and compared, and the §5 schema-
collision finding re-validated against whichever path(s) are confirmed live — it may be present on one
path, both, or be an artifact of reading the wrong one.
