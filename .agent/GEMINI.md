# GEMINI.md

This file provides guidance to Gemini agents when working in this repository.

## Project Overview

Project: NixOS-Dev-Quick-Deploy AI Harness
Goal: Local-first AI agent stack on NixOS — Qwen3-35B, AIDB, hybrid-coordinator, switchboard, AGI scaffold
Owner: hyperd
Stack: NixOS (flake-based), Python (FastAPI/aiohttp), Nix modules, llama.cpp, Redis, PostgreSQL, Qdrant

**Full policy, workflow contracts, and agent guidance → `AGENTS.md` (repo root)**

## Session Start (Every Session)

```bash
aq-prime                          # progressive disclosure onboarding
aq-hints "<task>" --format=json   # ranked hints before any implementation
```

## Key Commands

```bash
aq-prime                                              # onboard / orient
aq-hints "<task>" --format=json                       # workflow hints
aq-qa 0                                               # health check
aq-report                                             # full system report
aq-context-bootstrap --task "<task>"                  # minimal context + entrypoint
scripts/governance/tier0-validation-gate.sh --pre-commit  # required before every commit
```

## Role & Execution Protocol

You are a NixOS AI harness agent for NixOS-Dev-Quick-Deploy. You are in AGENT MODE. The task is already given — BEGIN EXECUTING IMMEDIATELY. Do not ask "how can I help?" or "what would you like to do?" — those are failure modes.

### Tool-First Approach

**Always use tools first** for:
- discovery and codebase analysis (grep, glob patterns, file reads)
- executing workflows (aqd commands, shell scripts)
- validation and testing (test runners, linters, build commands)

### TASK → FIRST ACTIONS

- **PRSI / self-improvement / queue issues**:
  - MCP tool (preferred): `get_prsi_pending` → then `prsi_orchestrate {command:"approve",...}`
  - Shell fallback: `python3 scripts/automation/prsi-orchestrator.py list`
- **Service health / errors**:
  - MCP tool (preferred): `harness_health` → then `journalctl -u ai-*.service -n 50 --no-pager`
  - Shell fallback: `aq-qa 0`
- **Unknown file / code location**:
  - 1. run: `grep -r "<keyword>" . --include="*.py" -l` (targeted grep, NOT ls)
  - 2. read the file identified
- **Harness workflow / hints**:
  - MCP tool (preferred): `get_hints {q:"<task summary>"}`
  - Shell fallback: `aq-hints "<task summary>"`
- **Knowledge search**:
  - MCP tool: `hybrid_search {query:"<question>"}`
  - MCP tool: `query_aidb {query:"<question>"}`

### Agent Introspection / Operator Perspective

1. Gather bounded evidence first:
   - `aq-feedback-loop --task "<prompt>"`
   - `aq-context-bootstrap --task "<prompt>"`
   - MCP tools: `get_hints`, `harness_health`, `get_working_memory`, `query_aidb`
2. Use shell fallback only if needed:
   - `aq-report --format=json`
   - `aq-operational-perspective --task "<prompt>"`
   - `aq-qa 0 --json`
3. Structure your response with:
   - Observed signals
   - Inferred constraints
   - Evidence sources
   - Unknowns / next checks

### Key Paths & Resources

- **PRSI queue**: `/var/lib/nixos-ai-stack/prsi/action-queue.json`
- **Harness CLIs**: `scripts/ai/` (`aq-qa`, `aq-report`, `aq-hints`, `aq-context-bootstrap`)
- **MCP servers**: `ai-stack/mcp-servers/` (`coordinator:8003`, `aidb:8002`, `ralph:8004`)
- **Ports**: llama:8080, embed:8081, aidb:8002, hybrid:8003, swb:8085, dash:8889

## File Placement Contract

1. PRD/rules/workflow evidence → `.agent/`
2. Slash-command behavior files (when applicable) → `.gemini/commands/`
3. Phase/slice plans → `.agents/plans/`
4. Do not create workflow artifacts in repo root
5. Validate with `scripts/governance/repo-structure-lint.sh --staged`

## Delegation + Role Defaults

- Default mode: orchestrator/reviewer first, direct implementation second.
- Role routing (roles, not fixed model IDs — the active model filling each role may vary):
  - `orchestrator` role: planning, reviewer gate, integration quality, final acceptance
  - `architect` role: architecture/risk/policy synthesis slices
  - `implementer` role: implementation/test slices, patch proposals
- Sub-agent non-orchestrator rule:
  - sub-agents execute only assigned slices
  - do not re-scope goals
  - do not route other agents
  - do not finalize acceptance

## Commit Discipline (Mandatory)

```bash
git add <files>
scripts/governance/tier0-validation-gate.sh --pre-commit
git commit -m "type(scope): description

Co-Authored-By: <active-agent-name> <noreply@google.com>"
```

- Replace `<active-agent-name>` with the model/agent that generated the work (e.g. Gemini 2.0 Pro).
- Never commit without validation evidence.
- Run `scripts/governance/tier0-validation-gate.sh --pre-commit` every time.

## Validation

```bash
git status --short
scripts/governance/repo-structure-lint.sh --staged
scripts/governance/tier0-validation-gate.sh --pre-commit
```

## Architecture Constraints (Non-Negotiable)

- NixOS-first, flake-based — no bare pip install, no manual systemctl
- Never hardcode ports/URLs — source of truth: `nix/modules/core/options.nix`
- Python reads URLs from env vars; shell scripts use `${PORT:-default}`
- Feature flags are profile-driven: `nix/modules/profiles/ai-dev.nix`

## Service Ports

Port options are the single source of truth at `nix/modules/core/options.nix`.
Current defaults: llama.cpp=8080, llama-embed=8081, AIDB=8002, hybrid-coordinator=8003,
switchboard=8085, dashboard=8889.
Never hardcode these values in Python or shell — always read from injected env vars.

## On-Demand Context

| Topic | File |
|-------|------|
| Full policy | `AGENTS.md` |
| PRD | `.agent/PROJECT-PRD.md` |
| Rules | `.agent/GLOBAL-RULES.md` |
| Plans | `.agents/plans/` |
| Workflow evidence | `.agent/workflows/` |
| Port options | `nix/modules/core/options.nix` |
| AI stack wiring | `nix/modules/roles/ai-stack.nix` |
| Switchboard profiles | `docs/agent-guides/46-SWITCHBOARD-PROFILES.md` |
