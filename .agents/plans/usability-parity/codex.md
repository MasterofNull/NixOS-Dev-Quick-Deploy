# Verdict

REQUEST_REVISION on the raw plan as an implementation order, PASS on the direction.
The first implementation slice should not start with broad tool-registry/HUD work alone.
The first slice must close the operator visibility gap for delegation state because the
current session proved that fan-out can appear queued/running while the real state is
Broken pipe, provider 429, local fallback timeout, daemon confinement failure, or no
proposal artifact.

# Evidence Read

- `.agents/prompts/AI_HARNESS_USABILITY_PARITY_EXPERT_TEAM_PROMPT.md`
- `.agents/plans/usability-parity/antigravity.md`
- `.agent/collaboration/RESUME.json`
- `.agent/collaboration/PULSE.log`
- `.agent/memory/issues-backlog.md`
- `scripts/ai/delegate-to-antigravity`
- `scripts/ai/delegate-to-local`
- `scripts/ai/lib/task_registry.py`
- `scripts/ai/aq-drop`
- `dashboard/backend/api/routes/aistack.py`
- `assets/dashboard.js`

# Expert-Team Findings

1. Product/Operator UX: the main usability failure is state fragmentation. Operators
   need one place to see task status, provider outcome, fallback path, output artifact,
   and next action.
2. Dashboard IA: dashboard parity is incomplete until delegation/fan-out state is visible
   as live cards, not just logs.
3. CLI UX: `delegate-* --status` and `aq-drop` need consistent terminal states and clear
   failure causes. "Queued" is not enough if a daemon later rejects or cannot dispatch.
4. Agent-Orchestration: `background_task.v1` should normalize task id, lane, status,
   pid, heartbeat, progress path, stream path, output path, terminal reason, and retry
   affordance.
5. Systems/NixOS: drop-daemon write confinement must be solved declaratively before
   event-driven fan-out can be trusted.
6. Security/Sandbox: do not bypass daemon policy by enabling shell-capable agent mode
   globally. Surface the policy decision instead.
7. Observability/SRE: provider 429, local fallback timeout, false-stale heartbeat, and
   daemon write denial should be first-class event types.
8. QA/Eval: every slice needs replay fixtures and expected/forbidden file assertions.
9. Performance/Tokenomics: event summaries should be compact and stream-oriented; avoid
   dumping full logs into dashboard payloads.

# Ranked Parity Gaps

1. Delegation state opacity: high operator value, low/medium risk.
2. Drop-zone false acceptance: high value, medium risk because service confinement is involved.
3. Provider/fallback diagnosis opacity: high value, low risk.
4. Local task heartbeat/schema drift: high value, low risk.
5. Dashboard missing Agent Tasks panel: high value, medium risk.
6. CLI command family lacks a single doctor path: medium/high value, low risk.
7. Sandbox grants are not inspectable by operators: medium value, low risk.
8. Tool registry/HUD parity: medium/high value, medium risk because it touches runtime behavior.
9. Replay/eval fixtures for agent runs: medium value, medium risk.
10. Spec-first isolated runs: high value, higher risk; defer until observability is stable.

# Proposed UX Architecture

The UX model should center on an "Agent Operations" surface shared by CLI and dashboard.

- CLI: `aq-agent-status <id>` or existing `delegate-* --status` should expose normalized
  `background_task.v1` fields and terminal reason.
- Dashboard: add an Agent Tasks card showing recent task id, lane, state, live progress,
  provider/fallback path, output artifact, and next action.
- Event stream: introduce `aq-agent-stream.v1` JSONL as a projection over existing task
  registry, progress, heartbeat, and output artifacts.
- Intervention: start with safe inspect/retry guidance only. Abort/pause can follow after
  signal handling is standardized.
- Replay/history: phase later, after status and events are reliable.

# Slice Plan

1. Slice A: Delegation Status Normalization
   - Files: `scripts/ai/lib/task_registry.py`, `scripts/ai/delegate-to-local`,
     `scripts/ai/delegate-to-antigravity`, focused tests.
   - Done: status accepts heartbeat `ts`, reports terminal reason, distinguishes provider
     failure from process crash, and never marks a live progress/heartbeat task stale.

2. Slice B: Drop-Daemon Dispatch Visibility
   - Files: `scripts/ai/aq-drop`, `scripts/ai/aq-drop-daemon`, Nix/AppArmor service wiring,
     focused tests.
   - Done: rejected/failed drops are queryable from CLI and dashboard; daemon can write
     intended mutable registry paths or reports a visible policy failure.

3. Slice C: Agent Tasks Dashboard Card
   - Files: `dashboard/backend/api/routes/aistack.py`, `assets/dashboard.js`,
     dashboard tests.
   - Done: dashboard displays the latest agent tasks with status, lane, age, output link,
     and failure reason.

4. Slice D: Provider and Sandbox Doctor
   - Files: `scripts/ai/aq-doctor` or existing diagnostic CLI, dashboard route, tests.
   - Done: one command explains provider config, remote status, local slot state, sandbox
     grant summary, and common remediation.

5. Slice E: HUD and Tool Registry Parity
   - Files: `scripts/ai/aq-chat`, `ai-stack/agents/runtimes/local_agent_runtime.py`, tests.
   - Done: `/tools` reflects active runtime tools and HUD shows lane/profile/tool count.

6. Slice F: Replay and Eval Fixtures
   - Files: `scripts/testing/harness_qa/phases/`, fixture data, validation registry.
   - Done: offline fixtures catch false queued/running/success states and forbidden file edits.

# Validation Matrix

| Gate | Command | Expected |
| --- | --- | --- |
| Status schema | focused Python test | heartbeat `ts` keeps live tasks live |
| Antigravity child stdio | `python3 scripts/testing/test-delegate-antigravity-background-stdio.py` | no Broken pipe regression |
| Drop rejection | focused daemon/CLI fixture | rejected drop has visible terminal state |
| Dashboard parity | dashboard route test | Agent Tasks card has no `--` for known data |
| QA phase | `scripts/ai/aq-qa 0 --machine` | no phase-0 regression |
| Tier0 | `scripts/governance/tier0-validation-gate.sh --pre-commit` | full pre-commit gate passes |

# Risk Register

- Security: enabling shell-capable drop agent mode globally would widen privilege. Mitigation:
  surface the policy and require explicit configuration.
- Operator confusion: too many task states can clutter UI. Mitigation: normalize into a small
  state set plus detail row.
- Performance: dashboard must not read full logs. Mitigation: summarize tails and metadata.
- Local latency: local fallback may be alive but slow. Mitigation: progress/heartbeat, not age caps.
- False confidence: queued/running without output is misleading. Mitigation: terminal reasons.
- Over-automation: default action should be inspect/retry guidance, not autonomous kill/restart.

# First Slice Recommendation

Implement Slice A first: Delegation Status Normalization.

Reason: every later UI/CLI improvement depends on truthful task state. This session exposed
multiple dark states: Antigravity Broken pipe, remote 429, local fallback timeout, local false
stale, and drop-daemon registry write denial. A dashboard card built on unnormalized state would
just make bad data prettier.

Exact done criteria:
- `delegate-to-local --status` does not false-stale live heartbeat/progress tasks.
- `delegate-to-antigravity --status` reports clean terminal reasons after provider/fallback failure.
- Failed tasks include output path and reason.
- Focused tests pass.
- Issue backlog and dashboard/PRD references are updated.

# Open Questions

1. Should the normalized status command be a new `aq-agent-status`, or should it remain a shared
   library consumed by existing `delegate-* --status` commands first?
2. Should failed drop records live in `.agents/drops/failed/`, registry JSONL, or both?

VERDICT: PASS — proceed with Slice A before broader UI/HUD implementation.
