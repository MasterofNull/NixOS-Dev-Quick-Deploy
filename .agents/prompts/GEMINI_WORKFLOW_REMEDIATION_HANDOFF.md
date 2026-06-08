# Gemini Workflow Remediation Handoff

Date: 2026-06-08
Status: Governance/behavior remediation brief
Scope: Gemini CLI, delegate-to-gemini, and any future Gemini-backed model team

## Problem

Gemini is producing useful artifacts, but it is not reliably behaving like the other model teams in the harness. The main gap is not model capability; it is predictable workflow adherence.

Observed failure classes:
- Directly edits PRD/policy/code without completing the flat model-team proposal and peer-review cycle.
- Treats its own PRD as final rather than one proposal requiring cross-model review and consensus merge.
- Adds workflow-contract material to `.agent/WORKFLOW-CANON.md` without preserving the canonical 8-step contract.
- Starts implementation-shaped edits during PRD/planning work, for example adding event types in `scripts/ai/lib/agent_run_events.py` while the observability PRD is still incomplete.
- Does not consistently demonstrate validation evidence before declaring work done.
- Does not consistently commit or prepare commit-ready atomic slices with documented validation.
- Uses or assumes the wrong tool surface depending on mode: direct Gemini CLI, `delegate-to-gemini --mode auto_edit`, or yolo mode have different capabilities.
- Does not consistently update collaboration artifacts (`RESUME.json`, `HANDOFF.md`, `PULSE.log`) in the expected order.
- Does not consistently delegate/collaborate with peer model teams in the desired flat structure.
- Does not consistently surface uncertainty, external-source confidence, or implementation risks before changing files.

## Existing Rules Gemini Must Follow

Authoritative files:
- `.agent/GEMINI.md`
- `.agent/WORKFLOW-CANON.md`
- `.agents/prompts/FLAT_MODEL_TEAM_PRD_PROTOCOL.md`
- `.agents/prompts/TOKENOMICS_PARITY_TEAM_HANDOFF.md`
- `docs/architecture/gemini-review-gate.md`

Key existing requirements:
- Load relevant skills before non-trivial tasks.
- Use harness-first orientation and memory/context hydration.
- Search before reading or editing.
- No coding before PRD/plan exists.
- One slice, one concern, one commit.
- Validate with relevant syntax checks, focused tests, live smoke when applicable, and tier0 before commit.
- Update `HANDOFF.md` for all completed or blocked work.
- Do not self-review.
- Do not bypass role/domain/security gates.
- Do not change canonical workflow rules unless the task is explicitly a workflow-contract change.

## Required Predictable Behavior Contract

Gemini must make these state transitions explicit:

1. **ORIENTED**
   - Reads `RESUME.json` and relevant handoff.
   - Confirms current objective.
   - Lists uncommitted files it did not create.

2. **RESEARCHED**
   - Shows which files/sources were consulted.
   - Distinguishes local repo facts from external inspiration.
   - Marks unverified claims as `research_required`.

3. **PLANNED**
   - Writes or references the PRD/plan artifact.
   - Defines scope, non-goals, acceptance criteria, validation, rollback.
   - For flat-team PRDs, writes one independent proposal before reading peer proposals.

4. **READY_TO_EDIT**
   - Declares intended files.
   - Confirms it is allowed to edit those files.
   - Writes/updates collaboration state before a complex edit.

5. **EDITED**
   - Makes only the scoped changes.
   - No opportunistic refactors.
   - Updates `PULSE.log` after writes when available.

6. **VALIDATED**
   - Runs or requests the correct validation for the mode.
   - In `auto_edit`, validates by file inspection because shell is unavailable.
   - In yolo/direct shell-capable mode, runs actual checks.
   - Reports command names and pass/fail evidence.

7. **REVIEW_READY**
   - Provides diff summary and validation evidence.
   - Does not claim final acceptance of its own work.
   - Requests peer model review where required.

8. **COMMIT_READY**
   - Atomic commit scope is clear.
   - Required docs are updated.
   - Tier0 has passed or the reason it cannot be run is explicit.
   - Commit message includes correct `Co-Authored-By`.

## Tool-Use Contract By Mode

### `delegate-to-gemini --mode auto_edit`

Allowed:
- `read_file`
- `grep_search`
- `list_directory`
- `replace`
- `write_file`

Not available:
- shell commands,
- `run_shell_command`,
- live systemctl/aq-qa execution,
- reading gitignored delegation logs with `read_file`.

Expected validation:
- Static file inspection.
- Grep checks for required strings.
- Clear request for Codex/human to run shell validation if needed.

### direct Gemini CLI / yolo mode

Allowed:
- Shell validation when available.
- Repo file edits.

Expected validation:
- `python3 -m py_compile` for changed Python.
- `bash -n` for changed shell.
- Focused tests for changed behavior.
- `git diff --check`.
- `AQ_QA_SKIP_REPORT_BACKED_CHECKS=1 scripts/governance/tier0-validation-gate.sh --pre-commit` before commit.
- Live smoke for dashboard/service/runtime behavior when applicable.

### Direct PRD/planning mode

Allowed:
- PRD/plan docs.
- Proposal/review/synthesis artifacts.

Not allowed:
- Code edits, schemas, event types, service wiring, dashboard changes, or workflow-canon changes unless the planning task explicitly includes those edits.

## Validation And Commit Gate

Gemini must not declare work complete unless one of these is true:

1. **Validated complete**
   - The required checks were run and passed.
   - Output is summarized with command names.
   - Handoff/resume updated.

2. **Review-ready only**
   - Gemini cannot run required checks due mode/tool limits.
   - It explicitly labels the result `REVIEW_READY_NOT_VALIDATED`.
   - It lists exact checks that Codex/human must run.

3. **Blocked**
   - Gemini hit a mode/tool/path/security blocker.
   - It stops after max 3 retries.
   - It writes the blocker and next action.

Commit rules:
- Gemini should commit only when explicitly assigned commit authority for that slice.
- A PRD-only plan normally should not be committed until peer review/consensus unless the orchestrator asks for a draft commit.
- Never use `--no-verify`.
- Never bundle unrelated telemetry churn unless it is part of the slice evidence.

## Flat Collaboration Requirements

For tokenomics and observability PRDs:
- Gemini's plan is one proposal, not final truth.
- Codex, local, and/or remote model teams must produce independent proposals.
- Each model reviews the other proposals.
- Consensus merge records accepted additions and rejected/minority positions.
- Implementation slices are delegated only after consensus.
- Slice reviewers must differ from implementers.
- Security and dashboard/service slices require eligible reviewers and aq-qa/dashboard gates.

## Observability-Specific Corrections

Gemini's current observability direction needs tightening:
- `thought` and `planning` event types are not enough by themselves.
- The event schema, producers, dashboard consumers, privacy/redaction rules, and tests must all align.
- Do not expose hidden chain-of-thought from providers that forbid it. Prefer:
  - explicit planning summaries,
  - model-provided allowed reasoning summaries,
  - token usage,
  - tool-call trace,
  - validation trace,
  - artifact diffs,
  - heartbeat/inactivity events.
- Every new replay/dashboard capability needs:
  - event producer,
  - schema/test coverage,
  - dashboard rendering,
  - aq-qa check,
  - privacy/redaction rule,
  - live smoke.

## Tokenomics And Optimization Corrections

Gemini must treat optimization as measured engineering:
- Establish baseline first.
- Measure prompt tokens, completion tokens, tool-output tokens, duplicate context ratio, retries, elapsed time, useful findings, false positives, and accepted artifact ratio.
- Prefer deterministic tooling over model calls for syntax, risk classification, file discovery, and health snapshots.
- Use model tiers and profiles only when the task value justifies the budget.
- Keep local llama.cpp payload discipline: `chat_template_kwargs.enable_thinking=false`.
- Do not propose KV-cache sharing as implementation until feasibility, memory cost, invalidation, and correctness are proven locally.

## Implementation Targets To Make Gemini Predictable

These are PRD candidates, not automatic implementation approval:

1. **Gemini mode detector**
   - Detect `auto_edit`, yolo, and direct CLI mode.
   - Inject the correct tool-use contract into the task prompt.

2. **Gemini workflow state machine**
   - Require explicit `ORIENTED`, `PLANNED`, `EDITED`, `VALIDATED`, `REVIEW_READY`, `COMMIT_READY` statuses in delegation outputs.
   - Fail focused CI if a Gemini output claims completion without validation or blocker evidence.

3. **Flat-team planning harness**
   - Add commands/templates for proposal, cross-review, consensus merge, and slice backlog.
   - Persist artifacts under `.agents/plans/model-proposals/<topic>/`.

4. **PRD-only write guard**
   - During PRD/planning tasks, block or flag code/schema/service edits unless explicitly allowed.

5. **Gemini validation checklist gate**
   - Static check that Gemini-touched slices include validation evidence in handoff or output.

6. **Delegation artifact reliability**
   - Fix local/Gemini delegation status/output persistence so every task id maps to a retrievable output artifact.

7. **Dashboard/aq-qa parity gate**
   - Any observability/tokenomics implementation must ship dashboard visibility and aq-qa coverage in the same or immediately consecutive slice.

## Acceptance Criteria

Gemini is considered aligned when:
- It produces independent model-team proposals before implementation.
- It cross-reviews peer proposals before consensus.
- It does not mutate canonical workflow docs for ordinary PRD work.
- It labels unvalidated work as review-ready, not done.
- It uses the correct tool contract for its execution mode.
- It updates collaboration artifacts predictably.
- It commits only assigned, validated, atomic slices.
- It can be swapped with another model/team without changing the output contract.

