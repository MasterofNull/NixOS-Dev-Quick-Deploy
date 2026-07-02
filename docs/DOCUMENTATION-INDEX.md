# Documentation Index

Structured entry point for all documentation in this repo. Organized by audience.
Last updated: 2026-07-01

**Progressive disclosure**: Start with "Start Here", go deeper only when needed.
**Token-efficient pattern**: Reference by path — don't paste docs into context.

---

## Start Here (Everyone)

| Doc | Purpose |
|-----|---------|
| `README.md` | Project overview, quick install |
| `AGENTS.md` | Canonical agent policy, role contracts, onboarding |
| `CLAUDE.md` | Claude Code operating guide (also covers all agents) |
| `.agent/WORKFLOW-CANON.md` | 8-step workflow, all agents |
| `docs/agent-guides/01-QUICK-START.md` | First task checklist |

---

## Codebase Wiki (Architecture Orientation — Start Here for Code Questions)

The fastest way to understand a subsystem. Generated from the knowledge graph.

```bash
aq-wiki --list          # list all sections
aq-wiki --section <name> # read a section
aq-wiki --status         # freshness check
```

| Section | What It Covers |
|---------|---------------|
| `.understand-anything/wiki/README.md` | Navigation index — start here |
| `.understand-anything/wiki/hybrid-coordinator.md` | Request routing, intent, tool dispatch |
| `.understand-anything/wiki/switchboard.md` | Profile routing, circuit breakers |
| `.understand-anything/wiki/local-agent.md` | Qwen3-35B runtime, outer loop |
| `.understand-anything/wiki/agent-runtimes.md` | Slot scheduling, SlotWaitTimeout |
| `.understand-anything/wiki/aidb.md` | RAG server, Qdrant, knowledge ingestion |
| `.understand-anything/wiki/nix-modules.md` | NixOS module declarations |
| `.understand-anything/wiki/ai-scripts.md` | aq-loop, aq-wiki, delegate-to-* |
| `.understand-anything/wiki/governance.md` | Pre-commit gates, validation |
| `.understand-anything/wiki/configuration.md` | Progressive disclosure, profiles |
| `.understand-anything/wiki/testing.md` | Test harness, inference tests |

→ Maintenance guide: `docs/agent-guides/48-WIKI-MAINTENANCE.md`

---

## Agent Guides (Numbered Reference)

| Guide | Topic |
|-------|-------|
| `docs/agent-guides/00-SYSTEM-OVERVIEW.md` | Full stack overview |
| `docs/agent-guides/01-QUICK-START.md` | First-session checklist |
| `docs/agent-guides/02-SERVICE-STATUS.md` | Service health and port map |
| `docs/agent-guides/10-NIXOS-CONFIG.md` | NixOS declarative config rules |
| `docs/agent-guides/12-DEBUGGING.md` | Debugging patterns |
| `docs/agent-guides/20-LOCAL-LLM-USAGE.md` | llama.cpp / Qwen3-35B config |
| `docs/agent-guides/21-RAG-CONTEXT.md` | RAG query patterns, collections |
| `docs/agent-guides/22-CONTINUOUS-LEARNING.md` | Training pipeline, dataset |
| `docs/agent-guides/30-QDRANT-OPERATIONS.md` | Qdrant operations |
| `docs/agent-guides/31-POSTGRES-OPS.md` | PostgreSQL operations |
| `docs/agent-guides/32-ERROR-LOGGING.md` | Error logging patterns |
| `docs/agent-guides/40-HYBRID-WORKFLOW.md` | Hybrid (local+remote) workflows |
| `docs/agent-guides/41-VALUE-SCORING.md` | Task value scoring |
| `docs/agent-guides/42-PATTERN-EXTRACTION.md` | Pattern extraction from sessions |
| `docs/agent-guides/44-FEDERATION-AUTOMATION.md` | Federation automation |
| `docs/agent-guides/45-PROGRESSIVE-DISCLOSURE.md` | Progressive disclosure system (v2.0) |
| `docs/agent-guides/46-SWITCHBOARD-PROFILES.md` | Switchboard profile catalog |
| `docs/agent-guides/47-AGENT-TOOL-CONTRACT.md` | Tool-first contract (canonical tool order) |
| `docs/agent-guides/48-WIKI-MAINTENANCE.md` | Wiki generation and maintenance |
| `docs/agent-guides/50-TOOL-SELECTION-MATRIX.md` | Tool selection matrix |
| `docs/agent-guides/60-CODE-QUALITY.md` | Code quality standards |
| `docs/agent-guides/61-WORKFLOW-PRACTICES.md` | Workflow best practices |
| `docs/agent-guides/62-MEMORY-SYSTEM.md` | Memory system design and usage |
| `docs/agent-guides/90-COMPREHENSIVE-ANALYSIS.md` | Full harness analysis |

---

## Architecture

| Doc | Topic |
|-----|-------|
| `docs/architecture/AI-STACK-ARCHITECTURE.md` | Full stack architecture |
| `docs/architecture/REQUEST-ROUTING-FLOW.md` | Request routing end-to-end |
| `docs/architecture/role-matrix.md` | Agent role SSOT |
| `docs/architecture/canonical-kernel-declaration.md` | Hardware limits, physical constraints |
| `docs/architecture/local-agent-agentic-capabilities.md` | Local agent capabilities |
| `docs/architecture/local-agent-task-eligibility.md` | Task routing eligibility matrix |
| `docs/architecture/memory-system-design.md` | Memory system architecture |
| `docs/architecture/routing-profile-inventory.md` | Routing profile inventory |
| `docs/architecture/RELATIONAL-GRAPH.md` | Service relationship graph |

---

## Operator Reference

| Doc | Topic |
|-----|-------|
| `docs/operations/OPERATOR-RUNBOOK.md` | Day-to-day operations runbook |
| `docs/operations/reference/QUICK-REFERENCE.md` | Quick reference card |

---

## Agent Policy Files (Per-Agent)

| Agent | File |
|-------|------|
| Claude Code | `.claude/CLAUDE.md` (symlinked from `CLAUDE.md`) |
| Gemini CLI | `.agent/GEMINI.md` |
| Codex CLI | `.agent/CODEX.md` |
| Local/Qwen3 | `.agent/LOCAL-AGENT.md` |
| All agents | `.agent/WORKFLOW-CANON.md` |

---

## Skill Index

All available skills (lazy-load patterns for agents):

- **Full index**: `.agent/SKILL_INDEX.md`
- **Discovery**: `aq-skill-suggest "<task description>"`
- **Key skills**: `wiki-navigation`, `understand-anything`, `system-dev`, `nixos-system`, `apparmor-rules`

---

## Historical / Archived

Older docs that have been superseded or deprecated:

- `docs/agent-guides/99-CLAUDE-DETAILS-LEGACY.md` — superseded by CLAUDE.md
- `docs/agent-guides/50-STRANDS-INTEGRATION.md` — Strands not in use
- `docs/architecture/GOOGLE-ADK-PARITY-MATRIX-2026-03.md` — historical snapshot
- `docs/architecture/PHASE-8-ARCHITECTURE-ASSESSMENT.md` — historical snapshot

For complete archive inventory: `.agent/archive/`

---

*Note: Some older links in docs/ may point to moved or renamed files. The wiki sections at
`.understand-anything/wiki/` are the authoritative subsystem navigation layer.*
