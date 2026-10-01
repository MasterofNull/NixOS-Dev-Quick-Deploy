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
