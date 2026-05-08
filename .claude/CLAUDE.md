# CLAUDE.md

This file provides guidance to Claude Code when working in this repository.

## Project Overview

Project: NixOS-Dev-Quick-Deploy AI Harness
Goal: Local-first AI agent stack on NixOS — Qwen3.6-35B, AIDB, hybrid-coordinator, switchboard, AGI scaffold
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
aq-prime                          # onboard / orient
aq-hints "<task>" --format=json   # workflow hints
aq-qa 0                           # health check (39 checks)
aq-report                         # full system report
aq-context-bootstrap --task "<task>"   # minimal context + entrypoint
scripts/governance/tier0-validation-gate.sh --pre-commit   # required before commit
```

## Commit Discipline (Mandatory)

```bash
git add <files>
git commit -m "type(scope): description

Co-Authored-By: Claude Sonnet 4.6 <noreply@anthropic.com>"
```

Run `scripts/governance/tier0-validation-gate.sh --pre-commit` before every commit.
Never commit without validation evidence.

## File Placement Contract

1. PRD/rules/workflow evidence → `.agent/`
2. Slash-command behavior files → `.claude/commands/`
3. Phase/slice plans → `.agents/plans/`
4. Do not create workflow artifacts in repo root
5. Validate with `scripts/governance/repo-structure-lint.sh --staged`

## Architecture Constraints (Non-Negotiable)

- NixOS-first, flake-based — no bare pip install, no manual systemctl
- Never hardcode ports/URLs — source of truth: `nix/modules/core/options.nix`
- Python reads URLs from env vars; shell scripts use `${PORT:-default}`
- Feature flags are profile-driven: `nix/modules/profiles/ai-dev.nix`
- `deploy-options.local.nix` is gitignored — secrets wiring only, no eval-time policy

## Service Ports

| Service | Port |
|---------|------|
| llama.cpp | 8080 |
| llama-embed | 8081 |
| AIDB | 8002 |
| hybrid-coordinator | 8003 |
| switchboard | 8085 |
| cli-bridge | 8089 |
| dashboard API | 8889 |

## Delegation Model

- **Claude Code (this session)**: architecture, risk, synthesis, orchestration
- **Codex (via aq-delegate)**: implementation slices, test scaffolding
- **Qwen (local, via harness)**: patches, runtime scripts
- `aq-delegate --auto-approve <agent> "<task>"` — always use this for sub-agent work

## On-Demand Context

| Topic | File |
|-------|------|
| Full policy | `AGENTS.md` |
| PRD | `.agent/PROJECT-PRD.md` |
| Plans | `.agents/plans/` |
| Port options | `nix/modules/core/options.nix` |
| AI stack wiring | `nix/modules/roles/ai-stack.nix` |
| Switchboard profiles | `docs/agent-guides/46-SWITCHBOARD-PROFILES.md` |
