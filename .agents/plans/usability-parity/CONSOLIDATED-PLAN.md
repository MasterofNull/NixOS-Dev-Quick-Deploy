# Consolidated Plan: Usability Parity Expert-Team Workflow

Status: ready for Phase 1 implementation
PRD: `.agent/PROJECT-USABILITY-PARITY-PRD.md`
Collaboration: `collab_1`, plan `plan-collab_1-1783573787`

## Decision

Proceed with the usability parity program, but reorder the first slice:

1. Delegation status normalization
2. Drop-zone dispatch visibility
3. Agent Tasks dashboard card
4. Provider and sandbox doctor
5. HUD and tool registry parity
6. Replay/eval fixtures

Antigravity recommended starting with tool registry/HUD parity. Codex accepts that as an
important phase but moves it later because this session showed that task status truth is
not yet reliable enough for dashboard/HUD polish.

## Current Evidence

- Antigravity proposal exists: `.agents/plans/usability-parity/antigravity.md`
- Codex proposal exists: `.agents/plans/usability-parity/codex.md`
- Project PRD exists: `.agent/PROJECT-USABILITY-PARITY-PRD.md`
- Local proposal missing: `local-20260708-221019-0k0jbj` failed before producing an artifact
- Antigravity headless Broken pipe fixed in `scripts/ai/delegate-to-antigravity`
- Live smoke now records the real failure path: remote HTTP 429 plus local fallback timeout
- Drop daemon fan-out is blocked by registry write confinement

## Phase 1 Slice Contract

Objective: normalize delegation task status so CLI/dashboard/report consumers can trust task state.

Scope:

- `delegate-to-local --status`
- `delegate-to-antigravity --status`
- shared registry/heartbeat/progress parsing
- focused tests
- issue/PULSE/RESUME updates

Out of scope:

- Dashboard redesign
- New autonomous abort/restart controls
- Enabling shell-capable drop agent mode
- Tool registry/HUD changes
- NixOS service policy changes unless required by a failing focused test

Acceptance:

- Live progress/heartbeat tasks are not false-staled due schema mismatch.
- Dead tasks with output logs report terminal failure reasons.
- Provider/fallback outcomes are visible without reading raw logs first.
- Antigravity background child stdio regression remains covered.
- Validation commands pass.

Validation commands:

```bash
python3 -m py_compile scripts/ai/delegate-to-antigravity scripts/testing/test-delegate-antigravity-background-stdio.py
python3 scripts/testing/test-delegate-antigravity-background-stdio.py
scripts/ai/aq-qa 0 --machine
```

## Phase 2 Slice Contract

Objective: make drop-zone dispatch outcomes visible and durable.

Acceptance:

- `aq-drop` does not leave operators with a false "queued" success when daemon policy will reject.
- Failed/rejected drops have durable status.
- Dashboard or CLI can show the failure reason.

## Phase 3 Slice Contract

Objective: add Agent Tasks visibility to the dashboard.

Acceptance:

- Latest task states render with no known-data `--` fields.
- Task details include lane, status, age, progress/heartbeat, output path, and failure reason.
- Payload remains compact; no full log dumps.

## Phase 4 Slice Contract

Objective: expose provider and sandbox diagnosis in one operator command/surface.

Acceptance:

- Provider readiness, remote errors, local slot fallback, AppArmor/sandbox grants, and common
  remediation are discoverable without opening docs.
- No secrets are printed.

## Phase 5 Slice Contract

Objective: make `aq-chat` HUD and `/tools` reflect active runtime state.

Acceptance:

- HUD shows lane/profile/tool count.
- `/tools` reflects runtime registry.
- Tool schema remains within budget.

## Phase 6 Slice Contract

Objective: add replay/eval fixtures for the known task-state and file-boundary failures.

Acceptance:

- Known cases replay: Broken pipe, provider 429, local timeout, false stale, drop rejection.
- Expected/forbidden file assertions protect collaboration boundaries.

## Next Action

Implement Phase 1, starting with the local heartbeat schema false-stale bug and terminal reason
normalization. Keep the Antigravity stdio fix in the same slice because it is already implemented
and validated.
