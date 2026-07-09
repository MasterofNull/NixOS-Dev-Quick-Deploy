# Verdict

PASS for a native harness usability parity program, with the first implementation slice focused on durable delegation/task progress visibility before broader dashboard redesign.

# Evidence Read

- `.agents/plans/parity-gitlawb-zero-2026-07-08.md`: strongest Zero lessons are `aq-agent-stream.v1`, permission events, sandbox grants, specialists, `background_task.v1`, spec/worktree runs, offline evals, provider doctor, repo map, and schedules.
- `.agents/plans/gitlawb-zero-gap-analysis.md`: highlights stream JSON, worktree isolation, prompt/diff eval fixtures, and token-aware context views.
- `.agent/ACTIVATION-AUDIT.md`: implemented is not done until integrated, on, live-tested, observable, and intervenable; F2 scheduler/backpressure/model-tier pieces are built but dormant.
- `docs/operations/DASHBOARD-ARCHITECTURE-REFERENCE.md`: dashboard is the operator visibility layer; new managed capability must expose health, drift, validation, or operational state.
- `docs/agent-guides/47-AGENT-TOOL-CONTRACT.md`: tool availability differs by lane; unavailable tools must be recorded once and use bounded fallbacks.
- `docs/architecture/role-matrix.md`: orchestrator assigns slices; implementers cannot self-accept; reviewer gates remain mandatory.
- Live workflow evidence from this round: local delegation failed when switchboard restarted, nested Codex reported running with no live PID and zero-byte output, and Antigravity must use a no-key IDE/OAuth inbox lane.

# Expert-Team Findings

Product/Operator UX Lead: the main usability defect is not lack of features; it is that capability state is scattered across dashboard fields, task logs, PULSE, registry rows, journals, service health, and agent-specific CLIs.

Dashboard Information Architect: first viewport should answer: system health, active agent lanes, blocked permissions, provider/auth posture, pending human decisions, running background tasks, and latest validation state. Blank `--` fields must become actionable degraded states.

CLI/Terminal UX Designer: one command should summarize the operating picture. Proposed family: `aq status`, `aq tasks`, `aq doctor providers`, `aq sandbox grants`, `aq stream tail`, `aq interventions`.

Agent-Orchestration Architect: the SSOT should be a canonical event/task envelope, not per-script conventions. `aq-agent-stream.v1` and `background_task.v1` should become the adapter layer for local, Codex, Antigravity inbox, drop zones, and future specialists.

Systems/NixOS Implementer: wire through declarative paths, systemd tmpfiles, and existing service/env contracts. Avoid runtime-only daemon drift.

Security/Sandbox Reviewer: no API keys for Antigravity/Gemini fan-out. Permission requests, sandbox denials, and escalation grants must be structured operator objects with no secret values.

Observability/SRE Owner: stale PID, heartbeat, no-output, cancelled-by-restart, provider mismatch, and inbox-not-consumed must be first-class states visible in `aq-report`, dashboard, and `aq-qa`.

QA/Eval Engineer: every new surface needs fixture tests plus live checks. Agent evals must score expected files, forbidden files, required events, and no-commit behavior.

Performance/Tokenomics Engineer: avoid model calls for deterministic status. Use lightweight collectors for status and reserve inference for synthesis/review.

# Ranked Parity Gaps

1. Durable background task status: current lanes can report false running with dead PID or zero output.
2. Unified stream JSON: lane events are not one schema across local, Codex, Antigravity, drop zones, and dashboard replay.
3. Permission/sandbox UX: denials and grants are not consistently visible as operator decisions.
4. Provider doctor: post-rebuild provider/auth mismatch still requires multi-command diagnosis.
5. Dashboard first-viewport operations model: active workflows and interventions are not summarized coherently.
6. Spec-first worktree execution: PRD exists, but no single ergonomic `aq-run --spec --worktree`.
7. Offline agent evals: validation exists, but prompt-to-diff agent behavior scoring is incomplete.
8. Project specialists: skills/roles exist, but not compact scoped specialist manifests with tool ceilings.
9. Repo-map packet: context discovery is powerful but scattered across lean-ctx, understand-anything, wiki, and hints.
10. Declarative schedules: timers exist, but agent jobs lack one operator-facing schedule contract.

# Proposed UX Architecture

Dashboard navigation:
- Overview ribbon: health, active lanes, failed lanes, pending interventions, provider posture, validation status.
- Agent Operations card: each task row shows lane, pid/live, heartbeat age, output bytes, stream path, current phase, stale policy, last event, intervention buttons.
- Provider Doctor card: local/remote route posture, no-key Antigravity inbox state, configured provider URL class, smoke status, and explicit mismatch reason.
- Sandbox/Permissions card: effective grants, recent denials, pending approval, write roots, escalation state.

CLI command family:
- `aq status --machine`: one deterministic system summary.
- `aq tasks list|show|reconcile --machine`: canonical `background_task.v1` view.
- `aq doctor providers --machine`: provider/auth/model/profile checks without secret exposure.
- `aq sandbox policy|grants --machine`: effective grants per lane/session.
- `aq stream tail <task>`: JSONL events for active work.
- `aq interventions list|approve|reject|defer`: unified operator actions.

Event/progress model:
- `aq-agent-stream.v1` JSONL events with `schema`, `task_id`, `lane`, `seq`, `event_type`, `ts`, `status`, `summary`, and redacted payload.
- `background_task.v1` metadata with `pid`, `pid_alive`, `created`, `heartbeat`, `output_path`, `output_bytes`, `stream_path`, `exit_code`, `stale_reason`, and `last_transition`.

Intervention model:
- Safe defaults: inspect, retry, mark unavailable, defer, approve/reject permission, pause schedule.
- Approval-gated: destructive cleanup, rollback, secret/provider changes, boot/disk actions.

Replay/history model:
- Dashboard and CLI read the same JSONL stream and task metadata.
- Eval fixtures assert event presence and forbidden event absence.

# Slice Plan

Slice 1: `background_task.v1` delegation status unification.
- Files: `scripts/ai/lib/task_registry.py`, `scripts/ai/delegate-to-local`, `scripts/ai/delegate-to-codex`, `scripts/ai/delegate-to-antigravity`, `scripts/ai/aq-collab-round`, `scripts/ai/aq-delegation-registry`, `dashboard/backend/api/routes/aistack.py`, `assets/dashboard.js`.
- Acceptance: dead PID plus zero output becomes `stale` or `failed`, not pending; restart-cancelled local tasks are distinguishable; dashboard/API show task state; `aq-qa` has an integration check.
- Validation: focused unit tests, `aq-collab-round collect`, `aq-delegation-registry reconcile`, `curl /api/...`, `aq-qa 0 --machine`.

Slice 2: `aq doctor providers --machine`.
- Files: switchboard profile helpers, provider/env contract, CLI, dashboard route/card, QA phase.
- Acceptance: detects mismatched provider URL/key class without printing secrets; explicitly directs Antigravity to no-key IDE/OAuth inbox.

Slice 3: `aq-agent-stream.v1`.
- Files: local agent loop, dispatcher adapters, registry schema, dashboard replay adapter, JSON schema tests.
- Acceptance: local/Codex/Antigravity/drop-zone paths emit comparable lifecycle events.

Slice 4: sandbox and permission visibility.
- Files: `aq-sandbox`, AppArmor/systemd grant readers, dashboard card, report section.
- Acceptance: effective writable roots, AppArmor profile, escalation mode, and recent denials visible per lane.

Slice 5: spec/worktree run and agent eval fixtures.
- Files: `aq-run`, eval runner, fixtures, validation registry, docs.
- Acceptance: isolated worktree run can be scored without committing; forbidden-file and required-event checks pass.

# Validation Matrix

| Capability | Dashboard | CLI | aq-report | aq-qa | Live test |
|---|---|---|---|---|---|
| background tasks | Agent Operations card | `aq tasks` | task summary | stale-pid check | kill/restart simulation |
| provider doctor | Provider card | `aq doctor providers` | provider posture | mismatch fixture | switchboard smoke |
| agent stream | replay/timeline | `aq stream tail` | event counts | schema check | local delegation run |
| sandbox grants | Sandbox card | `aq sandbox grants` | grant summary | policy check | denied write fixture |
| eval fixtures | eval trend | `aq-agent-eval` | eval score | fixture runner | throwaway worktree |

# Risk Register

- Security/sandbox: exposing grants must not expose secrets or normalize unsafe escalation.
- Operator confusion: avoid adding more cards without a first-viewport hierarchy and one CLI summary.
- Performance/token cost: status commands must be deterministic and no-model by default.
- Local model latency: no arbitrary hard caps; use heartbeat, progress, and stale-state classification.
- False confidence: stale registry rows must never render as healthy/running.
- Over-automation: retry and remediation require explicit state, boundaries, and review gates.

# First Slice Recommendation

Implement Slice 1 first: `background_task.v1` delegation status unification.

It precedes UI polish, provider doctor, and specialists because current collaboration cannot reliably tell pending from dead. This round already reproduced the defect twice: local failed due restart-induced connection refusal, and nested Codex reported running with no process and no output. Until task state is trustworthy, every higher-level dashboard or collaboration workflow can lie.

Done criteria:
- `delegate-to-codex --status` and `aq-collab-round collect` mark no-live-pid/zero-output as stale or failed.
- Local restart interruption records a specific cancellation/refused-connection state.
- `aq-delegation-registry reconcile` uses the same state names.
- Dashboard/API show task state and stale reason.
- `aq-qa 0 --machine` includes one check that exercises the integration path, not only `/health`.

# Open Questions

- Should Antigravity inbox watcher state be represented as its own `background_task.v1` lane when no local PID exists?
- Should stale zero-output be terminal immediately, or only after a short grace period?
- Which dashboard route should own the first Agent Operations card: existing `aistack.py` or a narrower task route?

VERDICT: PASS — prioritize trustworthy task/progress visibility first, then build the broader usability parity layers on top.
