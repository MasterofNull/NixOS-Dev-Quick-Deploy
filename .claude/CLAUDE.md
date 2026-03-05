# CLAUDE.md

This file provides guidance to Claude Code when working in this repository.

## Project Overview

NixOS-Dev-Quick-Deploy is a Nix-first deployment and AI-stack harness project with:
- declarative system/service modules,
- workflow APIs (`/workflow/plan`, `/workflow/run/start`, `/hints`),
- MCP tool discovery and agent workflow tooling.

## Tech Stack

| Technology | Purpose |
|------------|---------|
| NixOS modules | Declarative platform configuration |
| Bash/Python/Node | Harness scripts and bridges |
| Hybrid coordinator APIs | Workflow orchestration |
| MCP bridge | Tool discovery and invocation |

## Commands

```bash
# Prime context (read-only)
/prime

# Refresh PRD and planning artifacts
/create-prd .agent/PROJECT-PRD.md
/plan-feature "objective"

# Execute and commit slices
/execute .agents/plans/phase-template.md
/commit

# Explore harness quickly
/explore-harness
```

## Project Structure

```text
.agent/
  PROJECT-PRD.md
  GLOBAL-RULES.md
  workflows/
.claude/
  CLAUDE.md
  commands/
.agents/
  plans/
scripts/ai/
  aqd
  mcp-bridge-hybrid.py
```

## Validation

```bash
bash -n scripts/ai/aqd
python3 -m py_compile scripts/ai/mcp-bridge-hybrid.py
scripts/governance/repo-structure-lint.sh --staged
```

## On-Demand Context

| Topic | File |
|-------|------|
| Compact policy baseline | `AGENTS.md` |
| Canonical full policy | `docs/AGENTS.md` |
| Agent quick start | `docs/agent-guides/01-QUICK-START.md` |
| Debugging | `docs/agent-guides/12-DEBUGGING.md` |
| Hybrid workflow | `docs/agent-guides/40-HYBRID-WORKFLOW.md` |
| Agentic bootstrap runbook | `docs/development/AGENTIC-WORKFLOW-BOOTSTRAP-2026-03-05.md` |
