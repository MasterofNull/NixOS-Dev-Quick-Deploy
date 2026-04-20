# CLAUDE.md

This file provides always-read guidance for coding agents in this repository.
Keep this file compact and load deep docs on demand.

## Project Overview

NixOS-Dev-Quick-Deploy is a Nix-first deployment and AI-stack harness project
with declarative modules, operational scripts, and agent workflow tooling.

## Tech Stack

| Technology | Purpose |
|------------|---------|
| NixOS modules | Declarative system and service configuration |
| Bash + Python + Node | Harness CLIs, automation, and bridge tooling |
| Hybrid coordinator APIs | Workflow planning/run/hints orchestration |
| MCP bridge | Tool discovery and tool-calling integration |

## Commands

```bash
# Agent onboarding / session priming (use FIRST in any session)
aq-prime                                              # progressive disclosure onboarding
aqd workflows primer --target . --objective "<task>" # read-only session primer

# Context & task scoping
aq-context-bootstrap --task "<task>"   # minimal context + workflow recommendation
aq-hints --query "<task>"              # ranked workflow hints from harness

# Common workflow entry points
aqd workflows project-init --target <dir> --name <name> --goal <goal>
aqd workflows brownfield --target <repo-dir> --objective "improve X"
aqd workflows list                     # full workflow catalog

# Capability & runtime diagnosis
aq-capability-gap --query "<task>"     # classify missing tools/skills
aq-runtime-diagnose                    # service/runtime diagnosis loop
aq-system-act --query "<task>"         # unified entrypoint: gaps + runtime

# Reporting & QA
aq-report                              # AI stack health digest
aq-qa 0                                # phase-0 health checks
```

`aqd` also exposes: `policy evaluate`, `reasoning route`, `parity *` (regression/chaos/SLO),
`skill *` (validate/init/package/bundle), `mcp *` (scaffold/validate/deploy-aidb).
Run `aqd --help` for the full subcommand tree.

## Project Structure

```text
repo/
├── AGENTS.md                 # compact global policy baseline
├── CLAUDE.md                 # always-read core card (this file)
├── docs/AGENTS.md            # canonical full policy
├── docs/agent-guides/        # progressive disclosure guides
├── .agent/                   # workflow state, PRD, and guardrails
├── .claude/commands/         # slash-command behavior contracts
├── .agents/plans/            # phased implementation plans
├── scripts/ai/aqd            # guided workflow + agent tooling CLI
├── scripts/ai/mcp-bridge-hybrid.py  # MCP stdio bridge + tool registry
└── nix/modules/              # declarative NixOS system/service modules
```

## File Placement Contract

1. Do not create new files in repo root unless explicitly required.
2. Write docs under subject folders in `docs/`, not directly in `docs/`.
3. Write scripts under subject folders in `scripts/`, not directly in `scripts/`.
4. AI workflow artifacts must live in:
   - `.agent/` for PRD, rules, workflow evidence
   - `.claude/commands/` for command contracts
   - `.agents/plans/` for phase/slice plans
5. Run `scripts/governance/repo-structure-lint.sh --staged` before commit.

## Core Rules

1. Never hardcode secrets/tokens/passwords.
2. Never hardcode ports/service URLs.
3. Prefer declarative Nix/module changes over runtime script fallbacks.
4. For complex tasks use: `plan -> run/start -> hints -> execute -> validate`.
5. Do not finalize without validation evidence.

## Orchestrator Protocol (CRITICAL)

**Default behavior for Claude Opus in this repo:**

1. **Research** - Gather context via progressive disclosure, hints, and memory recall
2. **Plan** - Decompose into discrete delegatable slices
3. **Delegate** - Route implementation to sub-agents (qwen/codex)
4. **Audit** - Review outputs, validate, approve or request revision
5. **Commit** - Ensure all completed work is committed with git discipline (see Task completion defaults)
6. **Minimize token usage** - Only execute directly when delegation overhead exceeds task

**Delegation routing:**
| Task Type | Route To | Orchestrator Role |
|-----------|----------|-------------------|
| Code implementation | qwen | Review + merge |
| Test scaffolding | qwen | Review + validate |
| Architecture decisions | claude (sub) | Synthesize + decide |
| Config/Nix changes | qwen | Review + validate |
| Documentation | qwen | Review + edit |
| Security audit | claude (sub) | Analyze + approve |

**Sub-agent guardrails:**
- No re-scoping beyond assigned slice
- No cross-agent routing
- No final acceptance decisions
- Return to orchestrator on ambiguity

**Always use tools first:**
- `aq-hints --query "<task>"` before planning
- `/workflow/plan` for structured execution
- Check memory recall for prior solutions

**Task completion defaults (MANDATORY WORKFLOW):**
1. Context gathering: Read files, understand patterns
2. Research: Use grep/glob, understand conventions
3. Implementation: Code following existing patterns
4. Validation: Run tests, check syntax
5. Git commit: REQUIRED for all completed work
   - `git add <files> && git commit -m "type(scope): msg\n\nCo-Authored-By: Claude Sonnet 4.5 <noreply@anthropic.com>"`
   - Use feat/fix/docs/chore/test prefix
   - Include Co-Authored-By trailer
   - Run validation before commit
6. Update todo list to reflect completion

CRITICAL: Uncommitted changes = Incomplete task

## Validation

```bash
bash -n scripts/ai/aqd
python3 -m py_compile scripts/ai/mcp-bridge-hybrid.py
scripts/governance/repo-structure-lint.sh --staged
```

## Progressive Disclosure

Load only what is needed:

| Topic | File |
|-------|------|
| Compact policy baseline | `AGENTS.md` |
| Canonical full policy | `docs/AGENTS.md` |
| Agent quick start | `docs/agent-guides/01-QUICK-START.md` |
| Debugging | `docs/agent-guides/12-DEBUGGING.md` |
| Hybrid workflow model | `docs/agent-guides/40-HYBRID-WORKFLOW.md` |
| Continuous learning | `docs/agent-guides/22-CONTINUOUS-LEARNING.md` |
| Agentic bootstrap runbook | `docs/development/AGENTIC-WORKFLOW-BOOTSTRAP-2026-03-05.md` |
| Switchboard profile matrix | `docs/agent-guides/46-SWITCHBOARD-PROFILES.md` |
| Preserved deep legacy guidance | `docs/agent-guides/99-CLAUDE-DETAILS-LEGACY.md` |

## Notes

- Keep this file low-token.
- Move detailed guidance to docs and link from here.
- New repos should be scaffolded via `aqd workflows project-init`.
