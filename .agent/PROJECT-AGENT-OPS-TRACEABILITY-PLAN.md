# Agent Ops Traceability R0M Plan

Status: **M0–M1 ACCEPTED — M1 COMMITTED `748c5a9c`; M2A CANDIDATE READY 2026-07-15; M2B/M3/R1–R4 UNAUTHORIZED**

**Activation deferral (2026-07-15):** M2A is dormant. The closed delegation-task-record schema,
transactional TaskRegistry operations (begin/attach_process/transition_m2a/show_m2a/reconcile_m2a),
queued-grace projector extension, and ExecBarrier primitive are present as the contract foundation
only. No live wrapper imports or invokes M2A surfaces. Activation is separately authorized M2B
wrapper adoption.
Parent: `.agent/PROJECT-AGENT-OPS-TRACEABILITY-PRD.md`

## 1. Proposed exact inventory

1. `.agent/PROJECT-AGENT-OPS-TRACEABILITY-PRD.md`
2. `.agent/PROJECT-AGENT-OPS-TRACEABILITY-PLAN.md`
3. `config/schemas/agent-ops-projection.schema.json`
4. `scripts/ai/lib/agent_ops_projection.py`
5. `scripts/testing/fixtures/agent-ops-projection-golden.json`
6. `scripts/testing/test-agent-ops-projection.py`
7. `scripts/ai/aq-tui-dashboard`
8. `scripts/testing/harness_qa/phases/phase0.py`
9. `scripts/ai/_aq-qa-bash`
10. `config/validation-check-registry.json`
11. `docs/operations/agent-ops-window.md`
12. `scripts/ai/delegate-to-local`
13. `scripts/ai/delegate-to-claude`
14. `scripts/ai/delegate-to-codex`
15. `scripts/ai/delegate-to-antigravity`
16. `docs/architecture/role-matrix.md`

No other file is part of the R0M program inventory. L2B-A was accepted and committed as `fbeffbab`,
removing the prior overlap blocker. Each remaining slice still requires its own exact authorization.

### M1 exact candidate inventory

1. `.agent/PROJECT-AGENT-OPS-TRACEABILITY-PRD.md`
2. `.agent/PROJECT-AGENT-OPS-TRACEABILITY-PLAN.md`
3. `config/schemas/agent-ops-projection.schema.json`
4. `scripts/ai/lib/agent_ops_projection.py`
5. `scripts/testing/fixtures/agent-ops-projection-golden.json`
6. `scripts/testing/test-agent-ops-projection.py`
7. `scripts/ai/aq-tui-dashboard`
8. `docs/operations/agent-ops-window.md`

M1 may not edit Phase-0, Bash QA, the validation registry, any delegation wrapper, role policy, web
dashboard, lifecycle authority, or inference surface. Those are M2/M3 or separate-program concerns.

## 2. Slice sequence

### M0 — Pure projection contract

Create the closed schema, pure bounded readers/classifiers, and golden fixtures. No dashboard or gate
adoption until adversarial tests pass.

### M1 — Agentic Ops adoption

Replace raw process-string classification with the pure projector. Add ancestry/cgroup deduplication,
registry/progress/inbox correlation, explicit untracked/conflict cards, and machine JSON health.
Host facts are gathered by bounded read-only adapters and injected into the M0 projector. The
projector never reads `/proc` itself. `/proc` permission loss, PID reuse, missing cgroup data, oversized
registries/inboxes, and malformed JSON fail closed without preventing the TUI from rendering a
sanitized degraded card. Default cards and metrics never expose raw argv, prompts, output, or secrets.

### M2 — Dispatch enforcement and gates

Require every supported `delegate-to-*` wrapper to create a valid initial tracked record before model
or IDE work and fail closed if projection preflight rejects the route. The role contract prohibits
internal platform collaboration/subagent implementation until a supported lifecycle bridge exists;
such processes remain `UNTRACKED/BLOCKED`. Register Phase-0/Bash/validation checks. If implementation
proves another dispatch file must change, stop and revise the inventory; do not absorb it.

### M3 — Live verification

Exercise one tracked registry fixture/process, one Antigravity pending/archive transition, one idle
daemon, one untracked sandbox process, and one completed process. Confirm TUI and `--json` parity,
cache expiry, no duplicate cards, and no sensitive content.

## 3. Required adversarial fixtures

- Codex app-server idle; interactive main session; harness-managed Codex task; bwrap parent/child;
- incidental `exec` text that must not imply active work;
- PID reuse/start-time mismatch, disappearing `/proc`, permission denial, and cgroup absence;
- PGID/session-leader drift with cgroup-preserved deduplication;
- two registry rows for one PID, one row for two processes, stale running row, terminal/live conflict;
- heartbeat without trusted progress and forged progress producer;
- local internal/outer ID mismatch with explicit correlation;
- Antigravity pending, output-written-not-archived, archived, missing-output, and stale lane state;
- unsupported internal collaboration implementation marked blocked;
- prompt/secret/raw-command redaction and low-cardinality metric checks.

## 4. Validation

```bash
python3 scripts/testing/test-agent-ops-projection.py
scripts/ai/aq-tui-dashboard --json
scripts/ai/aq-qa 0 --machine
scripts/governance/tier0-validation-gate.sh --pre-commit
```

Live validation captures sanitized machine output and proves active-count convergence after process
exit. No synthetic fixture may be reported as live evidence.

## 5. Stop conditions

Stop for revision if implementation creates a lifecycle store, writes registry/inbox/process state,
uses raw substring classification as authority, labels untracked work nominal, exposes prompt/secret
content, silently kills a process, changes inference behavior, overlaps unresolved L2B-A bytes, or
requires a file outside the exact inventory.

## 6. Authorization request

Flagship design and acceptance reviews passed; the owner/orchestrator activated and consumed the
single-use M1 authorization, and the exact candidate was committed as `748c5a9c`. M2–M3 and R1–R4
remain unauthorized regardless of M1 status.

Implementation evidence: focused M1 tests pass 19/19, R0 passes 16/16, L2B-A passes 8/8, and L2A
passes 7/7. Host-backed Phase 0 wrote immutable evidence for 169 passed, 0 failed, and 9 skipped;
Tier0's wrapper does not yet recognize evidence-only `aq-qa` output, so final acceptance must
adjudicate that disclosed infrastructure blocker plus the mandatory host-visible smoke.
