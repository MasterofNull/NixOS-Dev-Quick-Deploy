# claude lane reference (moved from .claude/CLAUDE.md; on-demand, not always-on)

Sections moved verbatim to keep the always-on file small. Nothing here was deleted.

Contents: Slash Commands; Required Shared Knowledge (all agents — load at session start); Skill Index; Validation; Context Engineering Rules.

## Slash Commands

```bash
/prime                                      # session-zero onboarding + harness orient
/create-prd .agent/PROJECT-PRD.md          # scaffold a new PRD
/plan-feature "objective"                  # create phased feature plan
/execute .agents/plans/phase-template.md  # execute a phase plan
/commit                                    # guided commit with validation gates
/explore-harness                           # interactive harness capability tour
```

## Required Shared Knowledge (all agents — load at session start)

Cross-agent canonical references — read before any non-trivial task:
- `.agent/PROMOTED-BUG-PATTERNS.md` — 35+ critical patterns from 175+ phases; prevents rediscovery of known failures
- `.agent/INFRASTRUCTURE-CONSTRAINTS.md` — hardware limits, service ports, delegation status, NixOS error patterns, model config

---

## Skill Index

Skills are lazy-loaded knowledge modules for agents. Always check for a relevant skill before reading raw files.

```bash
# Quick routing — suggest skills before starting any non-trivial task:
aq-skill-suggest "your task description"
aq-skill-suggest "apparmor rule"          # → apparmor-rules, nixos-system
aq-skill-suggest "async handler"          # → python-async
aq-skill-suggest "gemini prompt"          # → agent-tool-map, multi-agent-collab

# Full index: .agent/SKILL_INDEX.md (always-in-context routing table)
# Skill files: .agent/skills/<name>/SKILL.md
```

**Skill loading rule**: load max 2-3 skills per task. Pass skill names (not content) to sub-agents.
Agent-specific filter: `aq-skill-suggest "<query>" --agent gemini|claude|codex|local`

## Validation

```bash
git status --short
scripts/governance/repo-structure-lint.sh --staged
scripts/governance/tier0-validation-gate.sh --pre-commit
```

## Context Engineering Rules

- **Always-on envelope:** role/authority, active objective, owned paths, acceptance criteria, and stop/validation constraints only.
- **Fetch triggers:** use `aq-resume`, then `aq-hints`/`aq-skill-auto` (at most 2–3 matching skills), then `lean-ctx` outlines/signatures and bounded line reads for exact symbols. Load domain policy or memory topics only when a task trigger or pointer requires them.
- **Delegation:** pass pointers, scope, acceptance criteria, and blockers; never parent history, full policy transcripts, whole source files, or full skill bodies.
- **Boundary persistence:** write the active envelope to `RESUME.json` and durable findings to topic files so a fresh session does not replay the conversation.

- Reference files by path — do not paste full file contents into context
- Use `mcp_server_hybrid_search` / `aq-hints` to pull context on demand
- Do NOT re-read files already read in the current session
- Pass only slice-relevant context to sub-agents — not full history
- Compact aggressively when approaching context limits

## Claude lane prose (moved from lane region, 2026-10-10, delivery-workflow budget trim)

Use direct implementation only after:
- problem scope is clear from tool output
- validation plan is documented
- AI-layer guidance is understood

- Sub-agent non-orchestrator rule:
  - sub-agents execute only assigned slices
  - do not re-scope goals
  - do not route other agents
  - do not finalize acceptance

- Never commit without live testing + doc update evidence.
- Run `scripts/governance/tier0-validation-gate.sh --pre-commit` every time.

**Always use tools first** for:
- discovery and codebase analysis (grep, glob patterns, file reads)
- executing workflows (aqd commands, shell scripts)
- validation and testing (test runners, linters, build commands)

- Default mode: orchestrator/reviewer first, direct implementation second. "Direct implementation second" means *after* checking whether a cheaper eligible lane exists (Rule 17) — it is not license to self-implement whenever delegation gets friction; a stalled/refusing sub-agent is grounds to fix the dispatch (correct model tier, better evidence), not to pull the work back to the orchestrator.

4. **Update the PM tracker** (owner-directed 2026-08-23; DoD dimension 6): for work under a tracked plan,
   update that plan's `tracker.json` editorial (items/goals/deps/detection-signals) so the projected
   gantt/kanban dashboard stays live. **Never hand-type status/% or the rendered charts** — the projector
   computes status from git+systemd (anti-gaming, Rule 20). A stale/missing tracker for active work = not done.

**After compaction / 401 failure recovery**: `aq-resume` outputs the last-known objective,
phase, todo snapshot, and uncommitted changes. Read it before doing anything else.

**When starting a new task**: immediately write/update `.agent/collaboration/RESUME.json`
with the current objective, phase, and todo snapshot. This is the compaction anchor point.

These wrappers add context injection, audit logging, and rate-limit guardrails. Bypassing them degrades harness observability.

## Claude lane prose (2) (moved from lane region, 2026-10-10, delivery-workflow budget trim)

**Role SSOT → `docs/architecture/role-matrix.md`** (Phase 58A.1). All role text below is a summary projection; the role matrix governs in case of conflict.

with the model/agent that generated the work (e.g. the model shown in your current session).

Full operating sequence before any commit:

## Claude lane prose (3) (moved from lane region, 2026-10-10, delivery-workflow budget trim)

- do not retry an unchanged failed tool call without a changed hypothesis

Goal: Local-first AI agent stack on NixOS — locally hosted LLM (currently Qwen3-35B), AIDB, hybrid-coordinator, switchboard, AGI scaffold
Owner: hyperd

Validate with `scripts/governance/repo-structure-lint.sh --staged`

## Delegation
