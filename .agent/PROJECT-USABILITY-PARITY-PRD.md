# Project PRD: AI Harness Usability Parity

Status: consensus-ready for slice execution
Created: 2026-07-09
Collaboration: `collab_1`, plan `plan-collab_1-1783573787`
Source prompt: `.agents/prompts/AI_HARNESS_USABILITY_PARITY_EXPERT_TEAM_PROMPT.md`
Inputs: `.agents/plans/usability-parity-v2/claude.md`, `.agents/plans/usability-parity-v2/codex.md`, `.agents/plans/usability-parity-v2/antigravity.md`, `.agents/plans/usability-parity-v2/AGGREGATE.md`

## Objective

Make the AI harness operable from a coherent dashboard and CLI mental model. An operator
must be able to discover capabilities, launch or monitor agent work, understand progress,
diagnose provider/sandbox failures, inspect outputs, and choose safe next actions without
memorizing scattered logs, services, ports, files, or hidden fallback paths.

## Problem Statement

The current system can run sophisticated local and remote agent workflows, but operational
truth is fragmented across registry JSONL, progress sidecars, heartbeat files, task logs,
PULSE/RESUME, journald, dashboard cards, and several `aq-*` tools.

This session exposed concrete examples:

- Antigravity headless tasks failed with `Broken pipe` while status initially looked like a
  normal running background task.
- After the stdio fix, the real state was visible: remote HTTP 429 plus local fallback timeout.
- Local/Qwen failed before producing a proposal, but the operator had to inspect stream files
  to understand how far it got.
- `aq-drop` reported a queued drop, while `ai-drop-daemon` later rejected or failed it in
  journald because agent mode is disabled or registry writes are confined.
- Local task registry can infer false stale when heartbeat files use `ts` rather than
  `heartbeat_at` or `last_heartbeat`.

These are not cosmetic issues. They are operator visibility defects.

## Non-Goals

- Do not install or depend on Zero.
- Do not redesign the canonical 8-step workflow.
- Do not enable autonomous destructive actions by default.
- Do not globally enable shell-capable drop-zone agent mode to make a demo pass.
- Do not build dashboard panels on stale or unnormalized state.
- Do not cap local inference by arbitrary wall-clock/tool-call/read limits.

## Principles

1. Truthful state before UI polish.
2. Every service or route ships with dashboard/report/QA visibility.
3. Provider, sandbox, fallback, and task-state failures are first-class operator objects.
4. Local inference stays progress/liveness driven, not age-capped.
5. CLI and dashboard consume the same normalized state model.
6. Manual/human review boundaries remain explicit.

## Native Parity Targets

| Zero-inspired pattern | Native harness target | Delivery gate |
| --- | --- | --- |
| `background_task.v1` | normalized agent task status projection | focused tests + dashboard card |
| `aq-agent-stream.v1` | compact JSONL event/progress projection | replay fixture + aq-report summary |
| Permission events | sandbox grants and denials as visible status | `aq-doctor` + dashboard row |
| Provider doctor | provider/profile/secret/fallback diagnosis | CLI command + QA smoke |
| Scoped specialists | bounded file/git A2A and slice contracts | collaboration boundary docs |
| Offline eval fixtures | expected/forbidden file and event assertions | `aq-qa` phase registration |
| Spec-first task runs | later `aq-run --spec --worktree` | defer until task status is reliable |

## Phase Plan

### Phase 1: Delegation Status Normalization

Goal: make `delegate-to-local`, `delegate-to-antigravity`, and shared registry consumers agree
on live, failed, stale, and fallback states.

Likely files:

- `scripts/ai/lib/task_registry.py`
- `scripts/ai/delegate-to-local`
- `scripts/ai/delegate-to-antigravity`
- `scripts/testing/test-delegate-antigravity-background-stdio.py`
- new focused tests for heartbeat `ts`

Acceptance:

- Live heartbeat/progress files prevent false stale.
- Antigravity status exposes provider HTTP failures and local fallback timeout as terminal reasons.
- Background child stderr/stdout is captured in output logs, not lost or crashed.
- Status output includes output path and next inspection command.

Validation:

- `python3 -m py_compile scripts/ai/delegate-to-antigravity`
- `python3 scripts/testing/test-delegate-antigravity-background-stdio.py`
- focused task-registry heartbeat regression
- `scripts/ai/aq-qa 0 --machine`

### Phase 2: Drop-Zone Dispatch Visibility

Goal: make queued, rejected, failed, and dispatched drop states visible without reading journald.

Likely files:

- `scripts/ai/aq-drop`
- `scripts/ai/aq-drop-daemon`
- `nix/modules/roles/ai-stack.nix` or related service/AppArmor module
- dashboard API route for drop/agent task status

Acceptance:

- Agent-mode policy rejection is visible from CLI and dashboard.
- Registry write confinement failure is visible as a failed drop.
- Daemon can write intended mutable state through declarative Nix/AppArmor policy or reports a
  durable terminal failure.

Validation:

- focused drop rejection fixture
- daemon dispatch fixture with writable registry
- journald no longer required for the primary operator path

### Phase 3: Agent Tasks Dashboard Card

Goal: expose active/recent agent task truth in Command Center.

Likely files:

- `dashboard/backend/api/routes/aistack.py`
- `assets/dashboard.js`
- dashboard route tests

Acceptance:

- Card shows task id, lane, status, age, progress/heartbeat state, output artifact, and failure reason.
- No `--` for known fields from registry/progress/heartbeat/output.
- Full logs are not loaded into the dashboard payload.

Validation:

- dashboard route unit test
- live `curl` route check
- visual smoke if frontend layout changes are non-trivial

### Phase 4: Provider and Sandbox Doctor

Goal: one CLI entrypoint explains provider readiness, local slot state, sandbox grants, and common
operator remediation.

Likely files:

- `scripts/ai/aq-doctor` or an existing diagnostics CLI
- provider/profile helpers
- dashboard status route

Acceptance:

- Reports switchboard status, remote configured state, provider class, last provider failure,
  local fallback availability, and sandbox writable roots.
- No secrets are printed.
- Uses port/env SSOT rather than hardcoded ports.

Validation:

- CLI smoke
- redaction test
- env-contract check if new env vars are added

### Phase 5: HUD and Tool Registry Parity

Goal: improve `aq-chat` and local runtime discoverability after status truth is stable.

Likely files:

- `scripts/ai/aq-chat`
- `ai-stack/agents/runtimes/local_agent_runtime.py`
- tool registry helpers

Acceptance:

- HUD shows lane/profile/tool count from real runtime state.
- `/tools` lists active runtime tools, not stale docs.
- Tool schema remains within budget.

Validation:

- focused CLI tests
- token/schema budget test

### Phase 6: Replay and Eval Fixtures

Goal: prevent regressions in task-state truth, allowed file changes, and event projections.

Likely files:

- `scripts/testing/harness_qa/phases/`
- fixture files under `scripts/testing/fixtures/` or equivalent
- validation registry updates

Acceptance:

- Replays known failure cases: Broken pipe, remote 429, local timeout, false stale, drop rejection.
- Asserts expected/forbidden files for agent proposals.
- Registered in `aq-qa`.

Validation:

- focused fixture test
- `scripts/ai/aq-qa 0 --machine`
- tier0 pre-commit gate before commit

## Consensus Update — Usability Parity v2

Round `usability-parity-v2` reached 3/4 quorum with `claude`, `codex`, and `antigravity`
landed. Local/Qwen task `local-20260708-231639-o7qnkl` remains live and late-pending, so it
must not be cancelled or treated as failed unless its PID dies, heartbeat stops, or its output
records a terminal failure.

Consensus decision: implement background task status truth first. Dashboard polish, unified `aq`
command routing, provider doctor, sandbox grant UI, and spec/worktree execution all depend on
trustworthy task state.

## First Implementation Slice

Start with Phase 1. The first patch should complete status normalization for existing delegation
paths, building on the already-applied Antigravity child-stdio fix.

Why first:

- Every later dashboard/CLI feature depends on truthful state.
- It resolves failure modes observed in this session.
- It is testable without a rebuild unless shared service policy changes are introduced.

Done means:

- Antigravity Broken pipe cannot recur from inherited stdout/stderr.
- Local heartbeat schema drift is fixed.
- Status commands communicate terminal reasons clearly.
- Focused tests pass.
- Issues backlog and PULSE/RESUME are updated.

## Multi-Agent Participation Record

- Codex: prompt author, orchestrator, reviewer, synthesis author, Antigravity stdio fix.
- Antigravity/Gemini: produced `.agents/plans/usability-parity/antigravity.md`.
- Local/Qwen: attempted `local-20260708-221019-0k0jbj`, failed before proposal artifact.
- Drop daemon: attempted fan-out path, blocked by policy/confinement; logged as issue.

## Open Issues Feeding This PRD

- `local-delegation-heartbeat-schema-false-stale`
- `drop-zone-agent-mode-disabled-by-default-visible-only-in-journal`
- `drop-daemon-cannot-write-delegation-registry`
- Antigravity remote lane/provider 429 and fallback timeout visibility

## Approval Gate

Before any implementation phase is marked complete:

- focused tests pass
- `aq-qa` coverage exists for new service/route/capability
- dashboard or CLI visibility exists for the changed operational state
- `scripts/governance/tier0-validation-gate.sh --pre-commit` passes
- handoff and issue backlog are updated
