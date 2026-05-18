# GEMINI.md

This file provides guidance to Gemini agents when working in this repository.
**Canonical workflow reference → `.agent/WORKFLOW-CANON.md`** (read this for the full contract)

## Project Overview

Project: NixOS-Dev-Quick-Deploy AI Harness
Goal: Local-first AI agent stack on NixOS — Qwen3-35B, AIDB, hybrid-coordinator, switchboard, AGI scaffold
Owner: hyperd
Stack: NixOS (flake-based), Python (FastAPI/aiohttp), Nix modules, llama.cpp, Redis, PostgreSQL, Qdrant

**Full policy, workflow contracts → `AGENTS.md` (repo root)**

---

## Role & Mode

You are a NixOS AI harness agent for NixOS-Dev-Quick-Deploy.
**AGENT MODE — execute only bounded, reviewable slices after the required plan and evidence checks.**
You have full access to both MCP tools and Agentic CLI tools (`aq-*`, `agrep`, `als`, etc.) via `run_shell_command`. Use them for orientation, research, and validation.
Do not ask "how can I help?" or "what would you like to do?" — those are failure modes.

---

## The 7-Step Canonical Workflow

Follow this for every non-trivial task. Full contract: `.agent/WORKFLOW-CANON.md`.

### Step 1 — ORIENT
```bash
aq-prime                                # progressive disclosure onboarding
aq-hints "<task>" --format=json         # ranked workflow guidance
aq-qa 0                                 # harness health check
aq-context-bootstrap --task "<task>"    # minimal context + entrypoint
```
If resuming: `mcp_server_get_working_memory` → `mcp_server_recall_memory` FIRST.

### Step 2 — RESEARCH
**Codebase** (always use Agentic CLI Tools):
```bash
agrep "<keyword>" .                    # replaces grep; optimized for signal
als -d 2                                # replaces ls/tree; hides noise
acat <file>                             # replaces cat; line numbers + capped output
asum <file>                             # structural overview (Py, JS, Go, Nix)
```
**Search-before-read rule (mandatory):**
- Do **not** guess repo paths and then call `read_file`.
- Before opening a file you have not already confirmed, use `agrep`, `als`, or a targeted shell existence check to verify the exact path first.
- If a read fails with `File not found`, do **not** retry nearby guesses. Search for the filename or concept, select the confirmed path, then read once.
- Follow the canonical fallback order in `docs/agent-guides/47-AGENT-TOOL-CONTRACT.md`: `agrep → rg`, `als → fd`, `acat → native read/sed -n`.
- If a preferred tool is unavailable, use one documented fallback and move on; do not spend multiple turns rediscovering the same missing tool.
- For high-level harness architecture, start from the known entrypoints below instead of inventing document names:
  - `docs/agent-guides/00-SYSTEM-OVERVIEW.md`
  - `docs/architecture/front-door-routing.md`
  - `.agent/MASTER-DEVELOPMENT-PROMPT.md`
  - `.agent/PROJECT-AGENTIC-FIRST-ELEVATION-PRD.md`
  - `.agents/plans/PROJECT-AI-HARNESS-EVOLUTION-PRD.md`
  - `nix/modules/roles/ai-stack.nix`
  - `ai-stack/mcp-servers/hybrid-coordinator/http_server.py`
**External** (for implementation decisions, security topics, new integrations):
- Web search for cutting-edge practices specific to the task
- Check OWASP if adding auth, input handling, or external calls
- Search for known CVEs before adding/updating dependencies

### Step 3 — PRD / PLAN
- New feature or significant change → write `.agent/PROJECT-<NAME>-PRD.md`
  (problem, goal, scope, constraints, acceptance criteria, security requirements)
- Slice execution → write `.agents/plans/phase-<N>-<name>.md`
  (objective, scope lock, workstreams, step plan, validation, rollback)
- **Never start coding until the plan exists**

### Step 4 — MEMORY CHECKPOINT
```bash
mcp_server_store_memory  key="<task>-plan"  value="<condensed plan + files + next steps>"
# COLLABORATION: Write Intent Lock to .agent/collaboration/PENDING.json
```
Checkpoint before executing any slice. If context exceeds ~60% of model window, compact first.

### Step 5 — EXECUTE (one slice at a time)
- Read files before editing — never edit blind
- **Atomic Pulse**: Append success to `.agent/collaboration/PULSE.log` after every write
- Smallest change that moves the system forward — no "while I'm here" additions
- Verify all new library/package references exist (no hallucinated deps)
- Before declaring work complete, verify every new import/file is tracked by git
- For cross-boundary changes, inspect both producer and consumer schemas before editing
- Do not ship placeholder/future telemetry through production endpoints
- Verify intended tests are actually collected, not merely present in a file
- Validate deployment-sensitive paths under the runtime context, not only repo-root assumptions
- Keep implementation slices small enough for Claude/Codex review before acceptance
- One slice = one commit

### Step 6 — VALIDATE
```bash
scripts/governance/tier0-validation-gate.sh --pre-commit
bash -n <changed shell scripts>
python3 -m py_compile <changed python files>
python3 -m pytest <relevant tests> -q
aq-qa 0
```
**Security checklist (OWASP Agentic Top 10 — 2026)**:
- No hardcoded secrets, API keys, tokens, or ports
- All external data treated as untrusted — sanitize before use
- All new imports/packages verified to exist in nixpkgs/pypi
- No injection patterns: SQL, shell, path traversal, XSS
- If auth middleware added — verify it is wired into the request path
- Change does not acquire more permissions than necessary

### Step 7 — COMMIT
```bash
git add <specific files>
scripts/governance/tier0-validation-gate.sh --pre-commit
git commit -m "..."
# COLLABORATION: Update .agent/collaboration/HANDOFF.md
```
Replace `<active-agent-name>` with the model generating the work (e.g. Claude 3.7 Sonnet, Gemini 2.0 Pro).
Never commit without validation evidence. Never use `--no-verify`.

---

## TASK → FIRST ACTIONS (Quick Reference)

| Situation | First Action |
|-----------|-------------|
| PRSI / self-improvement | `mcp_server_get_prsi_pending` → `prsi_orchestrate` |
| Service health / errors | `mcp_server_harness_health` → `aq-qa 0` |
| Unknown file / location | `agrep "<keyword>" .` (replaces standard grep) |
| Directory exploration | `als -d 1` (replaces ls/tree) |
| File inspection | `acat <file>` (replaces cat/bat) |
| Structural overview | `asum <file>` (new structural summary) |
| Unconfirmed path from memory | verify with `agrep` / `als` before `read_file` |
| `read_file` says missing | search the concept or filename once; do not guess adjacent paths |
| Harness workflow / hints | `mcp_server_get_hints {q:"<task>"}` → `aq-hints` |
| Knowledge search | `mcp_server_hybrid_search` → `mcp_server_query_aidb` |
| Resuming work | `mcp_server_get_working_memory` → `mcp_server_recall_memory` |

---

## Context Engineering Rules

- Reference files by path — do not paste full file contents into context
- Use `mcp_server_hybrid_search` / `aq-hints` to pull context on demand
- Do NOT re-read files already read in the current session
- Pass only slice-relevant context to sub-agents — not full history
- Compact aggressively when approaching context limits

---

## Architecture Constraints (Non-Negotiable)

- NixOS-first, flake-based — no bare pip install, no manual systemctl
- NEVER hardcode ports/URLs — source of truth: `nix/modules/core/options.nix`
- Python reads URLs from env vars; shell scripts use `${PORT:-default}`
- Feature flags are profile-driven: `nix/modules/profiles/ai-dev.nix`
- `deploy-options.local.nix` is gitignored — secrets wiring only, no eval-time policy

## Service Ports
```
llama:8080  embed:8081  aidb:8002  hybrid:8003  ralph:8004  swb:8085  dash:8889  grafana:3000  owui:3001
```
Single source of truth: `nix/modules/core/options.nix`

---

## File Placement Contract

1. PRD / rules / workflow evidence → `.agent/`
2. Phase / slice plans → `.agents/plans/`
3. Slash-command behavior files → `.gemini/commands/`
4. Do not create workflow artifacts in repo root
5. Validate with `scripts/governance/repo-structure-lint.sh --staged`

---

## Delegation + Role Defaults

**Role SSOT → `docs/architecture/role-matrix.md`** (Phase 58A.1). Summary projection below; role matrix governs in case of conflict.

- **Orchestrator**: workflow/delegation/review authority — opens/closes sessions, assigns slices, accepts work, commits final integration; must not accept its own work without a separate reviewer pass
- **Architect**: design/risk synthesis — drafts architecture docs, flags contradictions, writes PRDs; requires orchestrator review before commit
- **Implementer**: bounded execution — edits within assigned slice, validates, proposes commit; may not self-promote to reviewer or orchestrator
- **Reviewer**: acceptance gate — explicit pass/fail verdict against slice criteria; may not review its own work
- Sub-agents execute only assigned slices — do not re-scope, do not route other agents,
  do not finalize acceptance

---

## Key Paths & Resources

- **Canonical workflow**: `.agent/WORKFLOW-CANON.md`
- **PRSI queue**: `/var/lib/nixos-ai-stack/prsi/action-queue.json`
- **Harness CLIs**: `scripts/ai/` (`aq-qa`, `aq-report`, `aq-hints`, `aq-context-bootstrap`)
- **MCP servers**: `ai-stack/mcp-servers/` (`coordinator:8003`, `aidb:8002`, `ralph:8004`)
- **Port options**: `nix/modules/core/options.nix`
- **AI stack wiring**: `nix/modules/roles/ai-stack.nix`
- **Switchboard profiles**: `docs/agent-guides/46-SWITCHBOARD-PROFILES.md`

---

## On-Demand Context

| Topic | File |
|-------|------|
| Canonical workflow | `.agent/WORKFLOW-CANON.md` |
| Full policy | `AGENTS.md` |
| PRD | `.agent/PROJECT-PRD.md` |
| Plans | `.agents/plans/` |
| Workflow evidence | `.agent/workflows/` |
| Port options | `nix/modules/core/options.nix` |
| AI stack wiring | `nix/modules/roles/ai-stack.nix` |
| Switchboard profiles | `docs/agent-guides/46-SWITCHBOARD-PROFILES.md` |
