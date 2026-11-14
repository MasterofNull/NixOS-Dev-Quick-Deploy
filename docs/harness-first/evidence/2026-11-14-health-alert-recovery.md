# Health monitor retires its own qa-phase-0 alert after a clean phase-0 run

Date: 2026-11-14

## Objective

The `ai-stack-health-monitor` pushes a pending alert (dedup key `qa-phase-0`) when phase 0 fails, but never retires it after a clean run, so stale alerts pile up for the owner. This retires exactly that one source/key pair, fail-closed, under the queue lock, with an audit trail. Human dispositions are never touched.

## Workflow/Session IDs

- Plan: `.agents/plans/health-alert-recovery-20261113/` (DESIGN.md sha 3b2e607c106f2f8fe1d5c1fa3a3a4eb4e4da74c8aaddbf6b48681a5c06ac1b65).
- Design author: Simurg@codex. Original R3 reviews: claude-20261113-175143-4mzeac and gemini-20261113-175142-ciflmn (on sha e1dcc399, since lost from /tmp). Re-review of the persisted copy: Claude Sonnet, PLAN_READY_WITH_FOLLOWUPS, in `.agents/delegation/outputs/health-alert-recovery-20261113/REREVIEW-20261114-claude-sonnet.md`.
- Branch `slice/health-alert-recovery-20261114b`. Implementer: Claude Sonnet 5.5. Orchestrator: Simurg@claude/opus-5.5#da0ef470.

## Delegation Decision

Sonnet implementer (Rule 17 default). Codex was at its local implement cap. The independent code reviewer is chosen by aq-land (codex first).

## Commands Executed

- `python3 scripts/testing/test-ai-stack-health-monitor.py`: PASS.
- `python3 scripts/testing/test-dashboard-qa-provider-probe.py`: the new `test_alerts_status_recent_recovery` passes. `test_dashboard_html_has_exactly_six_probe_rows` fails identically on main (pre-existing; logged in the backlog).
- `aq-qa 0 --machine`: 207 pass / 1 fail / 9 skip before the 86.7 change. The failure was 86.7, because the live dashboard predates the new field. After the change, 86.1-86.6 and 86.8 PASS and 86.7 SKIPs.
- `scripts/governance/tier0-validation-gate.sh --pre-commit`: 68 passed, 0 failed.

## Validation Evidence

- Generation fence: a concurrent failure observation increments `observation_generation`, and retirement compares-and-swaps on it (test 86.8 plus the unit tests).
- Legacy migration fires only for exactly one exact-identity pending human_gate candidate.
- Consumer audit: `aq-alerts`/`get_all` read active rows only; `aq-approve` acts on pending; `aq-system-state` counts pending/auto_ok; `aq-pm-tracker` requires approved. No consumer changes were needed.

## Rollback Plan

Revert the PR. Retired alerts stay in the archive with status `recovered` and full audit fields, and the queue format stays backward compatible (raw `dedup_key` and generation are additive).

## Residual Risk

- Phase 0 currently reports 9 SKIPs on this host. The clean predicate requires zero skips, so the live alert will stay pending until a fully clean run. This is by design and fail-closed.
- Deviation for the reviewer: when `last_machine_recovery` is absent, 86.7 SKIPs (restart needed) instead of FAILing. A malformed field still FAILs.
- Activation needs a dashboard backend restart, an owner act.

## Hint Feedback

None.
