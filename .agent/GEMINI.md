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

## Tool-First Approach

**Always use tools first** for:
- discovery and codebase analysis (grep, glob patterns, file reads)
- executing workflows (aqd commands, shell scripts)
- validation and testing (test runners, linters, build commands)

Use direct implementation only after:
- problem scope is clear from tool output
- validation plan is documented
- AI-layer guidance is understood

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
switchboard=8085, cli-bridge=8089, dashboard=8889.
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
