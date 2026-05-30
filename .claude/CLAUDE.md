# CLAUDE.md

This file provides guidance to Claude Code when working in this repository.

## Project Overview

Project: NixOS-Dev-Quick-Deploy AI Harness
Goal: Local-first AI agent stack on NixOS — locally hosted LLM (currently Qwen3-35B), AIDB, hybrid-coordinator, switchboard, AGI scaffold
Owner: hyperd
Stack: NixOS (flake-based), Python (FastAPI/aiohttp), Nix modules, llama.cpp, Redis, PostgreSQL, Qdrant

**Full policy, workflow contracts, and agent guidance → `AGENTS.md` (repo root)**

## Slash Commands

```bash
/prime                                      # session-zero onboarding + harness orient
/create-prd .agent/PROJECT-PRD.md          # scaffold a new PRD
/plan-feature "objective"                  # create phased feature plan
/execute .agents/plans/phase-template.md  # execute a phase plan
/commit                                    # guided commit with validation gates
/explore-harness                           # interactive harness capability tour
```

## Session Start (Every Session)

```bash
aq-resume                         # FIRST: check for active task state after compaction
aq-prime                          # progressive disclosure onboarding
aq-session-start --task "<task>"  # mandatory context hydration
```

**After compaction / 401 failure recovery**: `aq-resume` outputs the last-known objective,
phase, todo snapshot, and uncommitted changes. Read it before doing anything else.

**When starting a new task**: immediately write/update `.agent/collaboration/RESUME.json`
with the current objective, phase, and todo snapshot. This is the compaction anchor point.

## Key Commands

```bash
aq-prime                                              # onboard / orient
aq-session-start                                      # mandatory hydration
aq-qa 0                                               # health check
aq-report                                             # full system report
aq-insights                                           # Qwen3 analysis of latest aq-report snapshot
aq-commit-facts                                       # extract institutional memory
scripts/governance/tier0-validation-gate.sh --pre-commit  # required before every commit
```

## Tool-First Approach

**Always use tools first** for:
- discovery and codebase analysis (grep, glob patterns, file reads)
- executing workflows (aqd commands, shell scripts)
- validation and testing (test runners, linters, build commands)

Use the canonical low-friction order in `docs/agent-guides/47-AGENT-TOOL-CONTRACT.md`:
- search: `agrep`, then `rg` — **never raw `grep` in shell commands**
- path discovery: `als`, then `fd` — **never raw `ls` or `find` in shell commands**
- bounded reads: `acat`, then native read tools or `sed -n` — **never raw `cat` in shell commands**
- do not retry an unchanged failed tool call without a changed hypothesis

**Agentic CLI wrappers are mandatory in Bash tool calls.** These wrappers add context injection, audit logging, and rate-limit guardrails. Bypassing them degrades harness observability.

Use direct implementation only after:
- problem scope is clear from tool output
- validation plan is documented
- AI-layer guidance is understood

## File Placement Contract

1. PRD/rules/workflow evidence → `.agent/`
2. Slash-command behavior files → `.claude/commands/`
3. Phase/slice plans → `.agents/plans/`
4. Do not create workflow artifacts in repo root
5. Validate with `scripts/governance/repo-structure-lint.sh --staged`

## Behavioral Rules (Canonical — all agents)

| # | Rule | Contract |
|---|------|----------|
| 1 | **CONVERSATIONAL GUARD** | No unsolicited features, refactors, or cleanups. One slice, one concern. |
| 2 | **HARNESS-FIRST** | Query aq-hints / `/query` / AIDB before reading raw files. Tools before assumptions. |
| 3 | **COMMIT FORMAT** | `type(scope): description` + `Co-Authored-By: <agent> <noreply@domain>` |
| 4 | **LANE SELECTION** | Prefer local inference for bounded tasks; remote only when task value justifies cost. |
| 5 | **CONTEXT LIMITS** | Compact aggressively near context ceiling. Sub-agents receive slice-relevant context only. |
| 6 | **RETRY BUDGET** | Max 3 retries on any failing op. 3rd failure → stop and report to orchestrator. |
| 7 | **SHELL SAFETY** | No injection patterns. Sanitize external input. Never bypass tool whitelists. |
| 8 | **PRD GATE** | No coding without a written plan. Log plan to PULSE.log before touching any file. |
| 8a | **ATOMIC PULSE** | Append one line to `.agent/collaboration/PULSE.log` after every successful write/commit: `[ISO-timestamp] [agent] [action]: [file-or-scope] — [outcome]`. Never skip this step. |
| 8b | **ATOMIC RESUME** | Write `.agent/collaboration/RESUME.json` when starting a new user task AND after each completed todo item. Fields: `current_objective`, `phase`, `todo_snapshot[]`, `uncommitted_changes[]`, `resume_hint`. This is the compaction anchor — survives 401 summarization failures. |
| 9 | **MEMORY DISCIPLINE** | Write completed-task facts to MemoryBroker. Read HANDOFF.md on session resume. |
| 10 | **SECURITY GATE** | OWASP check before commit. No hardcoded secrets, ports, tokens, or credentials. |
| 11 | **ISSUE LOGGING** | Any discovered error, friction, misconfiguration, or system limitation — fixed now or deferred — MUST be recorded in `memory/issues-backlog.md`: status, scope, root cause, file+line, severity, action. Update MEMORY.md index. Never silently discard a found issue. |

## Delegation + Role Defaults

**Role SSOT → `docs/architecture/role-matrix.md`** (Phase 58A.1). All role text below is a summary projection; the role matrix governs in case of conflict.

- Default mode: orchestrator/reviewer first, direct implementation second.
- Roles are defined by kernel responsibilities, not model identity:
  - `orchestrator`: workflow/delegation/review authority — opens/closes sessions, assigns slices, accepts work, commits final integration
  - `architect`: design/risk synthesis — drafts architecture docs, flags contradictions, writes PRDs; requires orchestrator review before commit
  - `implementer`: bounded execution — edits within assigned slice, validates, proposes commit; may not self-promote to reviewer
  - `reviewer`: acceptance gate — explicit pass/fail verdict against slice criteria; may not review its own work
- Sub-agent non-orchestrator rule:
  - sub-agents execute only assigned slices
  - do not re-scope goals
  - do not route other agents
  - do not finalize acceptance

## Commit Discipline (Mandatory)

Full operating sequence before any commit:
1. **Live test** changes in the running system — catch runtime errors and friction
2. **Fix** any issues found
3. **Update docs**: HANDOFF.md + any changed agent .md files + AGENTS.md if workflow changed
4. **Seed RAG** with new bug/fix patterns (`error-solutions`, `best-practices`, `skills-patterns`)
5. **Gate**: `scripts/governance/tier0-validation-gate.sh --pre-commit`
6. **Commit**

```bash
git add <files>
scripts/governance/tier0-validation-gate.sh --pre-commit
git commit -m "type(scope): description

Co-Authored-By: <active-agent-name> <noreply@anthropic.com>"
```

- Replace `<active-agent-name>` with the model/agent that generated the work (e.g. the model shown in your current session).
- Never commit without live testing + doc update evidence.
- Run `scripts/governance/tier0-validation-gate.sh --pre-commit` every time.

## Validation

```bash
git status --short
scripts/governance/repo-structure-lint.sh --staged
scripts/governance/tier0-validation-gate.sh --pre-commit
```

## Context Engineering Rules

- Reference files by path — do not paste full file contents into context
- Use `mcp_server_hybrid_search` / `aq-hints` to pull context on demand
- Do NOT re-read files already read in the current session
- Pass only slice-relevant context to sub-agents — not full history
- Compact aggressively when approaching context limits

## Architecture Constraints (Non-Negotiable)

- NixOS-first, flake-based — no bare pip install, no manual systemctl
- Never hardcode ports/URLs — source of truth: `nix/modules/core/options.nix`
- Python reads URLs from env vars; shell scripts use `${PORT:-default}`
- Feature flags are profile-driven: `nix/modules/profiles/ai-dev.nix`
- `deploy-options.local.nix` is gitignored — secrets wiring only, no eval-time policy
- `enable_thinking: false` in EVERY llama.cpp request — current model thinking tokens cause empty responses; see `.agent/LOCAL-AGENT.md ## Current Model Config` for model-specific setting
- GPU layers ceiling = 12 (Renoir APU VRAM = 4 GB shared); never suggest n_gpu_layers > 12
- Total usable RAM = 27 GB; model UMBM = 22.5 GB model / 1.0 GB KV / 3.0 GB OS reserve

## Service Ports

Port options are the single source of truth at `nix/modules/core/options.nix`.
Current defaults: llama.cpp=8080, llama-embed=8081, AIDB=8002, hybrid-coordinator=8003,
switchboard=8085, cli-bridge=8089, dashboard=8889.
Never hardcode these values in Python or shell — always read from injected env vars.

## Agent Instruction Files

| Agent | File | Purpose |
|-------|------|---------|
| Claude Code | `CLAUDE.md` (this file) | Claude Code CLI + VSCode extension |
| Gemini CLI | `.agent/GEMINI.md` | Gemini CLI, delegate-to-gemini |
| Codex CLI | `.agent/CODEX.md` | Codex CLI, delegate-to-codex |
| Local Agent | `.agent/LOCAL-AGENT.md` | aq-agent-loop, delegate-to-local (model-agnostic; current: Qwen3-35B) |
| Canonical workflow | `.agent/WORKFLOW-CANON.md` | Shared 8-step contract for all agents |

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
| Role matrix SSOT | `docs/architecture/role-matrix.md` |
| Kernel declaration | `docs/architecture/canonical-kernel-declaration.md` |
| **Domain Instructions** | |
| osint-systems | `.agent/OSINT-SYSTEMS-INSTRUCTIONS.md` |
| trading-agents | `.agent/TRADING-AGENTS-INSTRUCTIONS.md` |
| mlops-engineering | `.agent/MLOPS-ENGINEERING-INSTRUCTIONS.md` |
| qa-automation | `.agent/QA-AUTOMATION-INSTRUCTIONS.md` |
| mobile-web | `.agent/MOBILE-WEB-INSTRUCTIONS.md` |
| security-systems | `.agent/SECURITY-SYSTEMS-INSTRUCTIONS.md` |
| systems-software | `.agent/SYSTEMS-SOFTWARE-INSTRUCTIONS.md` |
| gis-systems | `.agent/GIS-SYSTEMS-INSTRUCTIONS.md` |
| embedded-hardware | `.agent/EMBEDDED-HARDWARE-INSTRUCTIONS.md` |
| scientific-research | `.agent/SCIENTIFIC-RESEARCH-INSTRUCTIONS.md` |
