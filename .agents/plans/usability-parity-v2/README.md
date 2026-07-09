# Collaborative Round — usability-parity-v2

Opened: 2026-07-09T05:46:54Z
Target artifact (if a review round): .agents/plans/usability-parity-v2

## Task
# AI Harness Usability Parity Expert-Team Prompt

Collaboration board: `collab_1`
Created: 2026-07-09
Orchestrator: Codex
Mode: PRD/debate/planning only. Do not implement code in this pass.

## Objective

Use the Gitlawb/zero parity-gap analysis and recent harness lessons to design the next
AI harness human-usability upgrade across:

- Command Center dashboard UI
- `aq-*` CLI/operator interface
- agent collaboration/delegation workflows
- local inference/session progress visibility
- permission/sandbox/provider diagnosis
- task/eval/replay ergonomics

The outcome must help an operator manage the AI harness without memorizing scattered
commands, paths, logs, timers, profiles, or service internals. The north star is:

> If the harness can do something, the operator should be able to discover it, run it,
> understand progress, intervene safely, and inspect results from one coherent UI/CLI
> mental model.

## Source Materials To Read First

Read these files before writing your proposal:

- `.agents/plans/parity-gitlawb-zero-2026-07-08.md`
- `.agents/plans/gitlawb-zero-gap-analysis.md`
- `.agents/prompts/TOKENOMICS_PARITY_TEAM_HANDOFF.md`
- `.agents/prompts/CLOUDFLARE_SOFTWARE_FACTORY_PARITY.md`
- `.agent/AQ-CHAT-ROUTING-PRD-CONSOLIDATED.md`
- `.agent/AQ-CHAT-ROUTING-PLAN-CONSOLIDATED.md`
- `.agent/ACTIVATION-AUDIT.md`
- `docs/operations/DASHBOARD-ARCHITECTURE-REFERENCE.md`
- `docs/agent-guides/47-AGENT-TOOL-CONTRACT.md`
- `docs/architecture/role-matrix.md`

Also inspect current surfaces as needed:

- `dashboard.html`
- `assets/dashboard.js`
- `dashboard/backend/api/routes/aistack.py`
- `scripts/ai/aq-chat`
- `scripts/ai/aq-report`
- `scripts/ai/aq-qa`
- `scripts/ai/delegate-to-local`
- `scripts/ai/delegate-to-antigravity`
- `scripts/ai/lib/task_registry.py`

## Key Lessons From Zero To Translate Natively

Do not propose installing or enabling Zero. Treat it as a design reference only.
Translate useful patterns into native NixOS harness slices:

1. `aq-agent-stream.v1`: one canonical JSONL protocol for lane/task events.
2. Permission events as first-class operator UX objects.
3. `aq-sandbox policy/grants`: effective sandbox and writable-root explainer.
4. Project-local specialists with scoped tools and no recursive delegation by default.
5. Durable `background_task.v1` metadata with heartbeat, output, stale-pid policy, and stream path.
6. `aq-run --spec --worktree`: spec-first isolated task execution.
7. Offline agent eval fixtures that score expected/forbidden changed files and trace events.
8. `aq-doctor providers`: provider/secret/model/profile diagnosis after rebuilds.
9. `aq-repo-map`: deterministic current-task repo map packet.
10. `aq-schedule`: declarative scheduled agent jobs with capability and output contracts.

## Required Expert Team Baseline

Every participating model must respond as the full same expert-team baseline, not as
one isolated role. Include sections for all roles:

1. Product/Operator UX Lead
2. Dashboard Information Architect
3. CLI/Terminal UX Designer
4. Agent-Orchestration Architect
5. Systems/NixOS Implementer
6. Security/Sandbox Reviewer
7. Observability/SRE Owner
8. QA/Eval Engineer
9. Performance/Tokenomics Engineer

Call out disagreements between roles explicitly.

## Required Analysis Questions

Answer these with concrete evidence from the repo:

1. What are the biggest human-usability gaps in the current harness UI and CLI?
2. Which gaps come directly from the Zero parity analysis?
3. Which gaps come from recent harness lessons: hidden activation state, stale alerts,
   hard-coded timeout/cap assumptions, scattered dashboard fields, unclear provider state,
   unclear sandbox grants, and opaque delegation progress?
4. What should be discoverable from the dashboard first viewport?
5. What should be discoverable from one CLI command without opening docs?
6. What operator interventions should exist and where should they live?
7. Which dashboard fields, CLI outputs, and event streams are the SSOT for each workflow?
8. What must be measurable before any implementation slice is considered complete?
9. What should be rejected as overreach, unsafe automation, or UI clutter?

## Deliverables

Produce a proposal that can be merged into a consolidated PRD/plan. Required sections:

1. Executive usability diagnosis
2. Top 10 parity gaps ranked by operator value and implementation risk
3. Proposed UX model:
   - dashboard navigation and cards
   - CLI command family
   - event stream/progress model
   - intervention model
   - replay/history model
4. Slice plan:
   - 3 to 7 implementation slices
   - files likely touched
   - acceptance criteria
   - validation commands
   - dashboard/aq-report/aq-qa coverage
   - rollback strategy
5. Parity scorecard:
   - Zero pattern
   - current local equivalent
   - current status
   - proposed native harness improvement
   - validation gate
6. Risk register:
   - security/sandbox
   - operator confusion
   - performance/token cost
   - local model latency
   - false confidence from stale telemetry
   - over-automation
7. Concrete first slice recommendation:
   - choose one slice to implement first
   - explain why it precedes the others
   - define exact done criteria

## Non-Negotiable Constraints

- Do not implement code in this pass.
- Do not install or run Zero.
- Do not propose runtime-only system changes; NixOS declarative changes only.
- Do not add a new service without aq-qa and dashboard/report visibility.
- Do not hardcode ports, secrets, provider URLs, or local paths outside existing contracts.
- Do not cap local agents by arbitrary tool-call/read/timeout counts; use progress/liveness/stale-state signals.
- Do not make autonomous commit/fix behavior the default. Keep PRSI/reviewer/human boundaries intact.
- Do not change the canonical 8-step workflow into a new workflow. Add overlays or PRDs, not contract drift.
- Do not accept Gemini/Antigravity claims without review evidence.

## Output Contract

Write your response as Markdown with these exact top-level headings:

1. `# Verdict`
2. `# Evidence Read`
3. `# Expert-Team Findings`
4. `# Ranked Parity Gaps`
5. `# Proposed UX Architecture`
6. `# Slice Plan`
7. `# Validation Matrix`
8. `# Risk Register`
9. `# First Slice Recommendation`
10. `# Open Questions`

End with:

`VERDICT: PASS|REQUEST_REVISION|BLOCKED — one sentence`

## Agent Output Paths

If you have file-write access, write your proposal to the matching path:

- Local/Qwen: `.agents/plans/usability-parity/local.md`
- Antigravity/Gemini: `.agents/plans/usability-parity/antigravity.md`
- Codex: `.agents/plans/usability-parity/codex.md`
- Opencode/other: `.agents/plans/usability-parity/opencode.md`

If you do not have file-write access, return the proposal in your task output and cite
the collaboration board `collab_1`.

## Collaboration Submission

After producing the proposal, submit or make it ready for:

`scripts/ai/aq-collaborate contribute collab_1 --agent <agent-id> --phase usability-parity --description "<short title>" --approach "<path or summary>"`

If your lane cannot call `aq-collaborate`, include the exact contribution command the
orchestrator should run for you.

## Protocol
Each agent writes its OWN file here — `codex.md`, `local.md`, `antigravity.md`, `claude.md`.
NEVER append to a shared file. The orchestrator aggregates into `AGGREGATE.md`.
- local[Qwen] runs long — the round stays OPEN for it; never skipped.
- antigravity (Antigravity IDE, real Gemini via its OWN OAuth) picks up the task from the inbox
  `.agent/collaboration/antigravity-inbox/usability-parity-v2.md` and writes `antigravity.md`. No API keys.
