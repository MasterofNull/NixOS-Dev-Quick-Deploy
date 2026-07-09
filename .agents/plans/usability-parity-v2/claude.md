# Verdict

PASS-WITH-CONDITIONS. The usability parity program should proceed, but the first implementation
slice must make multi-agent task state truthful before adding new dashboard/HUD affordances.

# Evidence Read

- `.agents/prompts/AI_HARNESS_USABILITY_PARITY_EXPERT_TEAM_PROMPT.md`
- `.agents/plans/usability-parity/antigravity.md`
- `.agents/plans/usability-parity/codex.md`
- `.agent/PROJECT-USABILITY-PARITY-PRD.md`
- `.agent/collaboration/PULSE.log`
- `.agent/memory/issues-backlog.md`
- `scripts/ai/aq-collab-round`
- `scripts/ai/delegate-to-antigravity`
- `scripts/ai/delegate-to-local`
- `scripts/ai/aq-drop`
- `scripts/ai/lib/task_registry.py`

# Expert-Team Findings

1. Product/Operator UX Lead: operators currently cannot trust a single surface for task truth.
2. Dashboard Information Architect: the dashboard needs an Agent Tasks surface, but only after
   status normalization prevents false running/queued states.
3. CLI/Terminal UX Designer: the first CLI win is a consistent status vocabulary across
   `delegate-to-local`, `delegate-to-antigravity`, `aq-drop`, and future `aq-agent-status`.
4. Agent-Orchestration Architect: `background_task.v1` should be the first native parity object.
5. Systems/NixOS Implementer: drop-daemon registry write confinement needs declarative repair;
   do not paper over it by enabling broader permissions.
6. Security/Sandbox Reviewer: surface sandbox policy and denied grants; do not auto-enable
   shell-capable lanes.
7. Observability/SRE Owner: provider 429, local fallback timeout, stale heartbeat, and daemon
   dispatch denial must be structured events, not log-only findings.
8. QA/Eval Engineer: replay fixtures should lock known failures before UI expansion.
9. Performance/Tokenomics Engineer: compact task summaries should feed UI; full logs remain links.

# Ranked Parity Gaps

1. Background task truth model missing.
2. Drop-zone queued/rejected/failed states are not operator-visible.
3. Provider/fallback diagnosis is scattered across logs.
4. Local heartbeat schema drift can false-stale live work.
5. Dashboard lacks an Agent Tasks card.
6. Sandbox grants and denials are not discoverable.
7. CLI `/tools` and HUD do not reflect runtime truth.
8. Replay fixtures do not enforce allowed/forbidden agent changes.
9. Spec-first isolated task runs are not yet operator-friendly.
10. Collaboration round outcomes are not surfaced as a single scorecard.

# Proposed UX Architecture

- CLI state model: normalize status around `queued`, `running`, `waiting`, `done`,
  `failed`, `stale`, and `blocked`, with `reason`, `output_file`, `progress_file`,
  `heartbeat_at`, `provider_path`, and `next_action`.
- Dashboard: add an Agent Tasks card after the status model lands. It should show task id,
  lane, status, age, last heartbeat/progress, failure reason, and output links.
- Event stream: project existing registry/progress/heartbeat/log state into
  `aq-agent-stream.v1` JSONL rather than inventing a new source of truth.
- Intervention model: start with inspect/retry guidance. Add abort/pause only after signal
  handling and stale detection are reliable.
- Replay/history: use fixtures for the known cases from this session before enabling
  one-click reruns.

# Slice Plan

1. Status Truth Slice
   - Normalize local/Antigravity task status and heartbeat parsing.
   - Keep the Antigravity background stdio fix.
   - Add focused regressions for false-stale and Broken pipe.

2. Drop Visibility Slice
   - Make rejected/failed drops durable and queryable.
   - Fix daemon writable-state policy declaratively.

3. Agent Tasks Dashboard Slice
   - Add compact dashboard card and API projection for recent tasks.
   - No full log payloads.

4. Doctor CLI Slice
   - Add provider, fallback, sandbox, and writable-root diagnosis.
   - Redact secrets.

5. HUD and Tool Registry Slice
   - Make `/tools` and prompt HUD reflect active runtime tools and profiles.

6. Replay/Eval Slice
   - Add fixtures for Broken pipe, provider 429, local timeout, false stale, and drop rejection.

# Validation Matrix

| Gate | Validation | Expected |
| --- | --- | --- |
| Broken pipe regression | `python3 scripts/testing/test-delegate-antigravity-background-stdio.py` | pass |
| Heartbeat schema | focused registry test | `ts` heartbeat keeps task live |
| Drop rejection | focused drop fixture | terminal state visible without journald |
| Dashboard parity | route/UI test | no known-data `--` fields |
| QA | `scripts/ai/aq-qa 0 --machine` | pass |
| Governance | `scripts/governance/tier0-validation-gate.sh --pre-commit` | pass |

# Risk Register

- Risk: UI built over untrustworthy status. Mitigation: status truth first.
- Risk: shell-capable drop mode expands authority. Mitigation: show policy, do not auto-enable.
- Risk: full logs overload dashboard. Mitigation: compact metadata plus links.
- Risk: local inference appears wedged while alive. Mitigation: heartbeat/progress, not age-only caps.
- Risk: collaboration rounds regress to solo synthesis. Mitigation: use `aq-collab-round` and per-agent files.

# First Slice Recommendation

Start with Status Truth Slice. It is the prerequisite for dashboard, doctor, replay, and HUD work.
Do not mark the usability parity phase complete until each new status field is visible in at least
one CLI or dashboard surface and has a focused regression.

# Open Questions

1. Should normalized status be exposed through a new `aq-agent-status`, or first as a library used
   by existing lane-specific commands?
2. Should failed drop records be moved to a `failed/` directory, a registry row, or both?

VERDICT: PASS — proceed with multi-agent round collection and implement Status Truth first after consensus.
