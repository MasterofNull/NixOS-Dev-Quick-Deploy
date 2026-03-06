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
# Guided AI-layer bootstrap (empty directory)
scripts/ai/aqd workflows project-init --target <dir> --name <name> --goal <goal>

# Read-only session primer
scripts/ai/aqd workflows primer --target <repo-dir> --objective "resume task"

# Brownfield guided planning
scripts/ai/aqd workflows brownfield --target <repo-dir> --objective "improve X"

# Workflow catalog
scripts/ai/aqd workflows list
```

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
6. If running as a nested/sub-agent: do not act as orchestrator.
7. Delegation-first: route eligible slices to `qwen` (patches) and `claude` (architecture/risk) while orchestrator performs reviewer gate.

## Delegation Defaults

- `codex` (or active controller): planner + orchestrator + reviewer only by default.
- `claude`: architecture/risk synthesis and policy reasoning slices.
- `qwen`: concrete implementation slices and test scaffolding.
- Sub-agent guardrail: no re-scoping, no cross-agent routing, no final acceptance decisions.

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
| Preserved deep legacy guidance | `docs/agent-guides/99-CLAUDE-DETAILS-LEGACY.md` |

## Notes

- Keep this file low-token.
- Move detailed guidance to docs and link from here.
- New repos should be scaffolded via `aqd workflows project-init`.
